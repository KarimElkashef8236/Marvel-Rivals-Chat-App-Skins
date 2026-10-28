"""Build the optional green beams pak for WhatsApp Iron Man.

Applies ironman/beams_plan.json to the game's Iron Man VFX files (the normal kit, the team-up versions,
which live in the MarvelGAS plugin folder, and the Repulsor hit copies in Common/BulletFreeze):
 - npci:  Iron Man's default costume hero colour
 - mi:    colour params of the effect materials that Iron Man's effects really show (materials other heroes
          also use are left alone)
 - lut:   Niagara colour curves
 - atlas: the colour ramp rows Iron Man's materials read (rows other heroes read are left alone; where one of
          those is also an Iron Man row, its green version goes into a free row and mi_scalars points the Iron Man
          only material at it, 'copy_of')
 - vm:    the colours the Niagara scripts themselves set. Most beams get their colour this way: each effect
          picks a friendly colour or the enemy red, in the system script and again per particle. Only the
          constants the friendly colour is built from move; the new values are added to the script's literal
          table and just those operands point at them, so the enemy colours stay as they were. A few particle
          scripts read the hero colour collection, those reads become the green constant. The Repulsor impact
          flare switches from the blue row of a shared ramp to its green row ('set').
Only cyan/blue colours move to WhatsApp green (eased to about the same perceived brightness); enemy reds and
missile orange stay. Every edit checks the original first, so a game patch that changed a file stops the build
instead of breaking it. VFX lives outside /Game/Marvel/Characters, so the container is packed obfuscated.
Files a game patch changed (the plan lists them in patched_sources, with the patch container as their container) are
read from the newest patch container that carries them. retoc can't unpack straight from the patch containers, so
their chunks are copied byte for byte into a small container in the work folder and unpacked from there.

    python scripts/ironman_beams.py [--game <Paks dir>]
"""
import argparse
import glob
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess

import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

import cityhash
from paths import DEFAULT_PAKS
from rivalspak import AES_KEY, oodle_decompress, write_pak

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RETOC = os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")
WORK = os.path.join(ROOT, "work", "ironman_beams")
MOD = "IronWhatsappBeams"

WA_GREEN = np.array([0x25, 0xD3, 0x66]) / 255.0
LUM = np.array([0.2126, 0.7152, 0.0722])


def _lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _hue(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn + 1e-12
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    return np.where(mx - mn < 1e-9, 0, h % 1.0)


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def recolor_lin(c, keep_luma=0.6, max_gain=3.0):
    """linear HDR colours: cyan/blue -> WhatsApp green with the same saturation, eased back towards the
    original perceived brightness so the green doesn't blow out (and never more than max_gain times as bright:
    deep blues have very little luminance). Colours near the edge of the blue range and the greyish ones are
    blended in gradually, so there are no hard seams. Violet (hue above about 255) stays violet."""
    c = np.array(c, np.float64)
    rgb = c[..., :3]
    v, mn = rgb.max(-1), rgb.min(-1)
    s = np.where(v > 1e-6, (v - mn) / np.maximum(v, 1e-6), 0)
    h = _hue(rgb) * 360
    w = _smooth(h, 138, 150) * (1 - _smooth(h, 252, 260)) * _smooth(s, 0.08, 0.16)
    tgt = _lin(WA_GREEN) / _lin(WA_GREEN).max()
    new = v[..., None] * ((1 - s)[..., None] + s[..., None] * tgt)
    lo, ln = (rgb * LUM).sum(-1), (new * LUM).sum(-1)
    k = np.clip(np.where(ln > 1e-9, lo / np.maximum(ln, 1e-9), 1.0), 0.35, 1.0) ** keep_luma
    g = new * k[..., None]
    lg = (g * LUM).sum(-1)
    cap = np.where(lg > max_gain * np.maximum(lo, 0), max_gain * np.maximum(lo, 0) / np.maximum(lg, 1e-12), 1.0)
    out = c.copy()
    out[..., :3] = rgb + w[..., None] * (g * cap[..., None] - rgb)
    return out


def file_rel(asset):
    """/Game/X -> Marvel/Content/X, /MarvelGAS/X -> Marvel/Plugins/MarvelGAS/Content/X"""
    if asset.startswith("/MarvelGAS/"):
        return "Marvel/Plugins/MarvelGAS/Content/" + asset[len("/MarvelGAS/"):]
    return "Marvel/Content/" + asset[len("/Game/"):]


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def game_package_ids(paks):
    """{container: set of package ids} for every IoStore container of the game (not ~mods)"""
    out = {}
    for u in glob.glob(os.path.join(paks, "*.utoc")):
        with open(u, "rb") as f:
            head = f.read(144)
            if head[:16] != b"-==--==--==--==-":
                continue
            n = struct.unpack_from("<I", head, 24)[0]
            ids = f.read(12 * n)
        out[os.path.basename(u)[:-5]] = {int.from_bytes(ids[12 * i:12 * i + 8], "little") for i in range(n) if ids[12 * i + 11] == 1}
    return out


def newest_first(patches):
    """patch container names, newest game version first (Patch_-Windows_1.1.3913745_P before 1.1.3892207)"""
    def ver(n):
        m = re.search(r"(\d+(?:\.\d+)+)", n)
        return tuple(int(x) for x in m.group(1).split(".")) if m else ()
    return sorted(patches, key=lambda n: (ver(n), n), reverse=True)


# ------------------------------------------------------------------ patch containers (read, and copy into a carrier)
MAGIC = b"-==--==--==--==-"
NONE = 0xFFFFFFFF


def _aes(b):
    d = Cipher(algorithms.AES(AES_KEY), modes.ECB()).decryptor()
    return d.update(b) + d.finalize()


def _fstr(s):
    n = struct.unpack("<i", s.read(4))[0]
    if n == 0:
        return ""
    if n < 0:
        return s.read(-n * 2).decode("utf-16-le").rstrip("\0")
    return s.read(n).decode("utf-8", "replace").rstrip("\0")


class Toc:
    """reads an IoStore .utoc/.ucas (TOC v5: AES, Oodle, directory index, chunk metas)"""

    def __init__(self, utoc):
        self.ucas = utoc[:-5] + ".ucas"
        d = open(utoc, "rb").read()
        if d[:16] != MAGIC:
            raise ValueError(utoc + ": not an IoStore TOC")
        self.ver = d[16]
        _, self.n, self.nblk, _, self.ncm, cmlen, self.block_size, self.dir_size, _ = struct.unpack_from("<9I", d, 20)
        self.flags = d[80]
        seeds, nohash = struct.unpack_from("<I", d, 84)[0], struct.unpack_from("<I", d, 96)[0]
        o = 144
        self.chunk_ids = [d[o + 12 * i:o + 12 * i + 12] for i in range(self.n)]
        o += 12 * self.n
        ol = np.frombuffer(d, np.uint8, self.n * 10, o).reshape(-1, 10).astype(np.uint64)
        o += 10 * self.n
        offs, lens = np.zeros(self.n, np.uint64), np.zeros(self.n, np.uint64)
        for k in range(5):
            offs = (offs << np.uint64(8)) | ol[:, k]
            lens = (lens << np.uint64(8)) | ol[:, 5 + k]
        self.offsets, self.lengths = [int(x) for x in offs], [int(x) for x in lens]
        if self.ver >= 4:
            o += 4 * seeds
        if self.ver >= 5:
            o += 4 * nohash
        self._blocks = (d, o)
        o += 12 * self.nblk
        self.methods = [d[o + i * cmlen:o + (i + 1) * cmlen].rstrip(b"\0").decode() for i in range(self.ncm)]
        o += self.ncm * cmlen
        if self.flags & 4:
            hs = struct.unpack_from("<I", d, o)[0]
            o += 4 + 2 * hs + 20 * self.nblk
        raw = d[o:o + self.dir_size]
        o += self.dir_size
        self.metas = [d[o + 33 * i:o + 33 * i + 33] for i in range(self.n)]
        self.files = {}
        if self.flags & 8 and self.dir_size:
            try:
                self._parse_dir(raw)
            except Exception:
                self.files = {}
                self._parse_dir(_aes(raw))
        self._fh = None

    def _parse_dir(self, buf):
        s = io.BytesIO(buf)
        mount = _fstr(s)
        dirs = [struct.unpack("<4I", s.read(16)) for _ in range(struct.unpack("<i", s.read(4))[0])]
        files = [struct.unpack("<3I", s.read(12)) for _ in range(struct.unpack("<i", s.read(4))[0])]
        strs = [_fstr(s) for _ in range(struct.unpack("<i", s.read(4))[0])]
        stack = [(0, [])]
        while stack:
            di, path = stack.pop()
            name, child, _, ff = dirs[di]
            if name != NONE:
                path = path + [strs[name]]
            fi = ff
            while fi != NONE:
                fn, nxt, ud = files[fi]
                self.files[(mount + "/".join(path + [strs[fn]])).replace("../../../", "")] = ud
                fi = nxt
            c = child
            while c != NONE:
                stack.append((c, path))
                c = dirs[c][2]

    def read(self, idx):
        if self._fh is None:
            self._fh = open(self.ucas, "rb")
        off, ln = self.offsets[idx], self.lengths[idx]
        first = off // self.block_size
        last = (off + ln - 1) // self.block_size if ln else first
        out = bytearray()
        d0, o0 = self._blocks
        for bi in range(first, last + 1):
            x = d0[o0 + 12 * bi:o0 + 12 * bi + 12]
            cs, us, m = int.from_bytes(x[5:8], "little"), int.from_bytes(x[8:11], "little"), x[11]
            self._fh.seek(int.from_bytes(x[0:5], "little"))
            rd = self._fh.read((cs + 15) & ~15 if self.flags & 2 else cs)
            if self.flags & 2:
                rd = _aes(rd)
            rd = rd[:cs]
            if m == 0:
                out += rd[:us]
            elif self.methods[m - 1].lower() == "oodle":
                out += oodle_decompress(rd, us)
            else:
                raise ValueError("unexpected compression " + self.methods[m - 1])
        start = off - first * self.block_size
        return bytes(out[start:start + ln])

    def header(self):
        """the container header's store entries: {package id: (imported package ids, shader map hashes)}"""
        i = [k for k, c in enumerate(self.chunk_ids) if c[11] == 6][0]
        b = self.read(i)
        sig, ver, _, n = struct.unpack_from("<IIQi", b, 0)
        if sig != 0x496F436E or ver != 3:
            raise ValueError("unexpected container header")
        pids = struct.unpack_from("<%dQ" % n, b, 20)
        o = 20 + 8 * n
        nb = struct.unpack_from("<i", b, o)[0]
        se = b[o + 4:o + 4 + nb]
        entries = {}
        for i, pid in enumerate(pids):
            e = 16 * i
            ni, oi, ns, os_ = struct.unpack_from("<IIII", se, e)
            imps = list(struct.unpack_from("<%dQ" % ni, se, e + oi)) if ni else []
            entries[pid] = (imps, [se[e + 8 + os_ + 20 * k:e + 8 + os_ + 20 * k + 20] for k in range(ns)])
        return entries


def _build_container_header(cid, packages):
    n = len(packages)
    head, tail = io.BytesIO(), io.BytesIO()
    for i, (_, imps, shs) in enumerate(packages):
        e = 16 * i
        io_off = 16 * n + tail.tell()
        tail.write(struct.pack("<%dQ" % len(imps), *imps))
        sh_off = 16 * n + tail.tell()
        for h in shs:
            tail.write(h)
        head.write(struct.pack("<II", len(imps), (io_off - e) if imps else 0))
        head.write(struct.pack("<II", len(shs), (sh_off - (e + 8)) if shs else 0))
    se = head.getvalue() + tail.getvalue()
    out = struct.pack("<IIQi", 0x496F436E, 3, cid, n) + struct.pack("<%dQ" % n, *[p[0] for p in packages])
    out += struct.pack("<i", len(se)) + se
    out += struct.pack("<ii", 0, 0) + struct.pack("<I", 0) + struct.pack("<ii", 0, 0)
    return out


def _fstring(s):
    b = s.encode("ascii") + b"\0"
    return struct.pack("<i", len(b)) + b


def _build_directory_index(mount, paths):
    strs, sidx = [], {}

    def si(s):
        if s not in sidx:
            sidx[s] = len(strs)
            strs.append(s)
        return sidx[s]

    dirs, files, kids = [[NONE, NONE, NONE, NONE]], [], {0: {}}
    for p in sorted(paths):
        parts, d = p.split("/"), 0
        for comp in parts[:-1]:
            if comp not in kids[d]:
                nd = len(dirs)
                dirs.append([si(comp), NONE, dirs[d][1], NONE])
                dirs[d][1] = nd
                kids[nd], kids[d][comp] = {}, nd
            d = kids[d][comp]
        files.append([si(parts[-1]), dirs[d][3], paths[p]])
        dirs[d][3] = len(files) - 1
    out = _fstring(mount)
    out += struct.pack("<i", len(dirs)) + b"".join(struct.pack("<4I", *x) for x in dirs)
    out += struct.pack("<i", len(files)) + b"".join(struct.pack("<3I", *x) for x in files)
    out += struct.pack("<i", len(strs)) + b"".join(_fstring(s) for s in strs)
    return out


def write_carrier(out_dir, name, chunks, header_packages, block=0x10000):
    """a small uncompressed, unencrypted, indexed IoStore container holding the given chunks byte for byte, so retoc
    can unpack them like any other container. chunks: [(path, chunk id, data, meta)]"""
    os.makedirs(out_dir, exist_ok=True)
    cid = cityhash.city64(name.lower().encode("utf-16-le"))
    hdr = _build_container_header(cid, header_packages)
    allc = list(chunks) + [(None, struct.pack("<Q", cid) + b"\0\0\0" + bytes([6]), hdr, b"\0" * 33)]
    ucas = io.BytesIO()
    ids, ol, blocks, metas, paths = [], [], [], [], {}
    uoff = 0
    for i, (p, chid, data, meta) in enumerate(allc):
        ids.append(chid)
        ol.append(uoff.to_bytes(5, "big") + len(data).to_bytes(5, "big"))
        for k in range(0, len(data), block):
            part = data[k:k + block]
            blocks.append(ucas.tell().to_bytes(5, "little") + len(part).to_bytes(3, "little") + len(part).to_bytes(3, "little") + b"\0")
            ucas.write(part)
        uoff += (len(data) + block - 1) // block * block
        metas.append(meta[:32] + b"\0")
        if p:
            paths[p] = i
    dirx = _build_directory_index("../../../", paths)
    h = bytearray(144)
    h[0:16] = MAGIC
    h[16] = 5
    struct.pack_into("<9I", h, 20, 144, len(allc), len(blocks), 12, 0, 32, block, len(dirx), 1)
    struct.pack_into("<Q", h, 56, cid)
    h[80] = 8
    struct.pack_into("<Q", h, 88, 0xFFFFFFFFFFFFFFFF)
    open(os.path.join(out_dir, name + ".utoc"), "wb").write(bytes(h) + b"".join(ids) + b"".join(ol) + b"".join(blocks) + dirx + b"".join(metas))
    open(os.path.join(out_dir, name + ".ucas"), "wb").write(ucas.getvalue())
    write_pak(os.path.join(out_dir, name + ".pak"), {}, compress=False, encrypt_files=False)
    return os.path.join(out_dir, name + ".utoc")


def gather(toc, assets):
    """every chunk of each package byte for byte from one (patch) container, plus its store entry from that
    container's header (a patch header lists every package of the game)"""
    chunks, packages, hdr = [], [], toc.header()
    for asset in assets:
        key = file_rel(asset) + ".uasset"
        if key not in toc.files:
            raise SystemExit(f"{asset} isn't in the patch container the plan says")
        pid = int.from_bytes(toc.chunk_ids[toc.files[key]][:8], "little")
        if pid != cityhash.pkg_id(asset):
            raise SystemExit(f"{asset}: the patch chunk isn't the package id of its path")
        stem, named = key[:-len(".uasset")], set()
        for ext in (".uasset", ".ubulk", ".uptnl", ".m.ubulk"):
            if stem + ext in toc.files:
                i = toc.files[stem + ext]
                chunks.append((stem + ext, toc.chunk_ids[i], toc.read(i), toc.metas[i]))
                named.add(i)
        if any(int.from_bytes(c[:8], "little") == pid and i not in named for i, c in enumerate(toc.chunk_ids)):
            raise SystemExit(f"{asset}: the package has a chunk this build doesn't know")
        if pid not in hdr:
            raise SystemExit(f"{asset}: no store entry in the patch container header")
        packages.append((pid, hdr[pid][0], hdr[pid][1]))
    return chunks, packages


def check_game(plan, paks):
    """stop before building from stale files: every asset has to come from the newest container that carries it
    (the newest patch container for the ones a patch changed, which the plan lists in patched_sources with that
    container), and a patched asset has to be byte for byte the patch copy the plan was made from. Also make sure
    the names of the Iron Man only copies are still free."""
    ids = game_package_ids(paks)
    patches = newest_first([k for k in ids if k.startswith("Patch")])
    every = set().union(*ids.values())
    srcs = {p["asset"]: p for p in plan.get("patched_sources", [])}
    for a in sorted(set(plan["containers"]) | {c["asset"] for c in plan.get("clones", [])}):
        newest = next((p for p in patches if cityhash.pkg_id(a) in ids[p]), None)
        want = plan["containers"].get(a)
        if newest and want != newest:
            raise SystemExit(f"{a} is in {newest} now, so the plan is out of date: rebuild the plan")
        if not newest and (a in srcs or str(want).startswith("Patch")):
            raise SystemExit(f"{a} isn't in a patch container any more, so the plan is out of date: rebuild the plan")
        if newest and a not in srcs:
            raise SystemExit(f"{a} comes from {newest} but isn't in the plan's patched_sources: rebuild the plan")
    tocs = {}
    for a, p in srcs.items():
        if plan["containers"].get(a) != p["container"]:
            raise SystemExit(f"{a}: patched_sources and containers disagree, rebuild the plan")
        t = tocs.setdefault(p["container"], Toc(os.path.join(paks, p["container"] + ".utoc")))
        key = file_rel(a) + ".uasset"
        if key not in t.files or sha1(t.read(t.files[key])) != p["zen_sha1"]:
            raise SystemExit(f"{a} changed in {p['container']} since the plan was made, rebuild the plan")
    for c in plan.get("clones", []):
        if cityhash.pkg_id(c["to"]) in every:
            raise SystemExit(f"{c['to']} exists in the game now, pick another name for the copy of {c['asset']}")


def apply_vm(rec, uexp, uasset):
    """point the friendly colour operands of each script at new literals; grows the literal tables and fixes
    the export sizes/offsets and BulkDataStartOffset in the .uasset. uexp/uasset are bytearrays."""
    inserts = []
    for sc in rec["scripts"]:
        at, n, base = sc["lit_at"], sc["lit_count"], sc["lit_base"]
        if struct.unpack_from("<i", uexp, at - 4)[0] != n:
            raise SystemExit(f"{rec['asset']} {sc['name']}: literal table isn't where the plan says")
        lits = [bytes(uexp[at + 4 * k:at + 4 * k + 4]) for k in range(n // 4)]
        added = []
        for col in sc["colours"]:
            old = np.array(col["old"], np.float64)
            new = np.array(col["set"], np.float64) if "set" in col else recolor_lin(old)
            for op in col["operands"]:
                cur = struct.unpack_from("<H", uexp, op["uexp_offset"])[0]
                if cur != op["old_operand"]:
                    raise SystemExit(f"{rec['asset']} {sc['name']} {col['var']}: operand changed (a game patch?)")
                if "param" not in op:   # parameter reads (the hero colour) have no literal to check
                    ob = bytes.fromhex(op["old_literal"]) if "old_literal" in op else \
                        struct.pack("<f", float(old[op["comp"]]) / op["scale"])
                    k = (op["old_operand"] - base) // 4
                    if not 0 <= k < len(lits) or lits[k] != ob:
                        raise SystemExit(f"{rec['asset']} {sc['name']} {col['var']}: literal changed (a game patch?)")
                elif "types_at" not in op and op["old_operand"] >= base:
                    raise SystemExit(f"{rec['asset']} {sc['name']} {col['var']}: expected a parameter read")
                nb = struct.pack("<f", float(new[op["comp"]]) / op["scale"])
                if nb in lits:
                    slot = lits.index(nb)
                else:
                    if nb not in added:
                        added.append(nb)
                    slot = len(lits) + added.index(nb)
                off = base + 4 * slot
                if off > 0xFFFF:
                    raise SystemExit(f"{rec['asset']}: constant offset overflow")
                if "types_at" in op:   # an input read that becomes a constant: set that operand's constant bit
                    if uexp[op["types_at"]] >> op["bit"] & 1:
                        raise SystemExit(f"{rec['asset']} {sc['name']} {col['var']}: operand already constant")
                    uexp[op["types_at"]] |= 1 << op["bit"]
                struct.pack_into("<H", uexp, op["uexp_offset"], off)
        if added:
            inserts.append((at + n, at - 4, b"".join(added)))
    th, eo, es = rec["total_header"], rec["export_off"], rec["export_size"]
    for pos, cnt_at, data in sorted(inserts, reverse=True):
        k = len(data)
        struct.pack_into("<i", uexp, cnt_at, struct.unpack_from("<i", uexp, cnt_at)[0] + k)
        uexp[pos:pos] = data
        grown = 0
        for i in range(rec["export_count"]):
            b = eo + i * es
            size, off = struct.unpack_from("<qq", uasset, b + 28)
            if off - th <= pos < off - th + size:
                struct.pack_into("<q", uasset, b + 28, size + k)
                grown += 1
            elif off - th >= pos:
                struct.pack_into("<q", uasset, b + 36, off + k)
        if grown != 1:
            raise SystemExit(f"{rec['asset']}: literal table isn't inside one export")
        b = rec["bulk_start_at"]
        struct.pack_into("<q", uasset, b, struct.unpack_from("<q", uasset, b)[0] + k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS)
    args = ap.parse_args()
    plan = json.load(open(os.path.join(ROOT, "ironman", "beams_plan.json"), encoding="utf-8"))
    check_game(plan, args.game)
    shutil.rmtree(WORK, ignore_errors=True)
    src, raw = os.path.join(WORK, "game"), os.path.join(WORK, MOD)
    by_container = {}
    for asset, cont in plan["containers"].items():
        by_container.setdefault(cont, []).append(asset)
    for cont, assets in by_container.items():
        if cont.startswith("Patch"):        # retoc can't unpack these, see below
            continue
        for i in range(0, len(assets), 100):
            filters = []
            for a in assets[i:i + 100]:
                filters += ["--filter", "../../../" + file_rel(a) + ".uasset"]
            subprocess.run([RETOC, "unpack", os.path.join(args.game, cont + ".utoc"), *filters, "--output", src,
                            "--game-paks-dir", args.game], check=True, stdout=subprocess.DEVNULL)
    # the files a patch changed: their chunks copied byte for byte into a small container, unpacked from there
    by_patch = {}
    for p in plan.get("patched_sources", []):
        by_patch.setdefault(p["container"], []).append(p["asset"])
    for k, (cont, assets) in enumerate(sorted(by_patch.items())):
        chunks, packages = gather(Toc(os.path.join(args.game, cont + ".utoc")), assets)
        carrier = write_carrier(os.path.join(WORK, "carrier"), f"IronMan_PatchSrc{k}_P", chunks, packages)
        subprocess.run([RETOC, "unpack", carrier, "--output", src, "--game-paks-dir", args.game], check=True,
                       stdout=subprocess.DEVNULL)

    def path(asset, root):
        return os.path.join(root, *file_rel(asset).split("/"))

    for p in plan.get("patched_sources", []):
        f = path(p["asset"], src)
        if not os.path.exists(f + ".uexp"):
            raise SystemExit(f"{p['asset']} didn't come out of {p['container']}")
        if sha1(open(f + ".uasset", "rb").read()) != p["uasset_sha1"] or sha1(open(f + ".uexp", "rb").read()) != p["uexp_sha1"]:
            raise SystemExit(f"{p['asset']}: retoc gave different files from the patch than when the plan was made")

    uexps, uassets = {}, {}

    def uexp(asset):
        if asset not in uexps:
            f = path(asset, src)
            if not os.path.exists(f + ".uexp"):
                raise SystemExit(f"{asset} didn't come out of the game files")
            uexps[asset] = bytearray(open(f + ".uexp", "rb").read())
            uassets[asset] = bytearray(open(f + ".uasset", "rb").read())
        return uexps[asset]

    # whole-file checks for the scripts and repointed effects first, before anything in them changes
    for rec in plan.get("vm", []):
        b = uexp(rec["asset"])
        if sha1(b) != rec["uexp_sha1"] or sha1(uassets[rec["asset"]]) != rec["uasset_sha1"]:
            raise SystemExit(f"{rec['asset']} changed since the plan was made (a game patch?), rebuild the plan")
    for rec in plan.get("import_renames", []):
        uexp(rec["asset"])
        if sha1(uassets[rec["asset"]]) != rec["uasset_sha1"]:
            raise SystemExit(f"{rec['asset']} changed since the plan was made (a game patch?), rebuild the plan")

    def check_range(e, b):
        if sha1(b[e["uexp_offset"]:e["uexp_offset"] + e["length"]]) != e["sha1"]:
            raise SystemExit(f"{e['asset']} changed since the plan was made (a game patch?), rebuild the plan")

    def check_old(e, b, where):
        """the colour has to be the plan's original: exactly its bytes where the plan has them ('old_hex')"""
        cur = struct.unpack_from("<4f", b, e["uexp_offset"])
        exact = "old_hex" not in e or bytes(b[e["uexp_offset"]:e["uexp_offset"] + 16]).hex() == e["old_hex"]
        if not exact or not np.allclose(cur, e["old"], atol=1e-3):
            raise SystemExit(f"{where} {e['param']}: expected {e['old']}, found {cur} (a game patch?)")

    counts = dict(npci=0, mi=0, lut=0, atlas=0, vm=0)
    for kind in ("npci", "mi"):
        for e in plan[kind]:
            b = uexp(e["asset"])
            check_old(e, b, e["asset"])
            struct.pack_into("<4f", b, e["uexp_offset"], *recolor_lin(np.array(e["old"])))
            counts[kind] += 1
    for e in plan.get("mi_scalars", []):   # e.g. a colour ramp row: read a row the mod turned green
        b = uexp(e["asset"])
        if struct.unpack_from("<f", b, e["uexp_offset"])[0] != e["old"]:
            raise SystemExit(f"{e['asset']} {e['param']}: expected {e['old']} (a game patch?)")
        struct.pack_into("<f", b, e["uexp_offset"], e["new"])
        counts["mi"] += 1
    for kind, dt in (("lut", "<f4"), ("atlas", "<f2")):
        for e in plan[kind]:
            b = uexp(e["asset"])
            check_range(e, b)
            cp = e.get("copy_of")   # a free ramp row that gets the green version of a row other effects read too
            if cp:                  # (that row stays as it is, and the Iron Man material reads this one instead)
                check_range(dict(cp, asset=e["asset"], length=e["length"]), b)
            o = (cp or e)["uexp_offset"]
            a = np.frombuffer(bytes(b[o:o + e["length"]]), dt).astype(np.float64)
            b[e["uexp_offset"]:e["uexp_offset"] + e["length"]] = recolor_lin(a.reshape(-1, 4)).astype(dt).tobytes()
            counts[kind] += 1
    # grey colour curves an effect tints per channel with no spare constant for one channel: tint the curve
    for e in plan.get("lut_tint", []):
        b = uexp(e["asset"])
        check_range(e, b)
        k = np.array(e["tint_from"], np.float64)
        f = np.where(k != 0, recolor_lin(k) / np.where(k != 0, k, 1.0), 1.0)
        f[3] = 1.0
        a = np.frombuffer(bytes(b[e["uexp_offset"]:e["uexp_offset"] + e["length"]]), "<f4").astype(np.float64).reshape(-1, 4)
        b[e["uexp_offset"]:e["uexp_offset"] + e["length"]] = (a * f).astype("<f4").tobytes()
        counts["lut_tint"] = counts.get("lut_tint", 0) + 1
    # the script edits grow the files, so they go last (every offset above is in the original layout)
    for rec in plan.get("vm", []):
        apply_vm(rec, uexp(rec["asset"]), uassets[rec["asset"]])
        counts["vm"] += sum(len(sc["colours"]) for sc in rec["scripts"])
    # Iron Man only copies of materials other heroes share: same package under a new name of the same length
    # (a new FName number, or 001 -> 0W1), recoloured; the original stays vanilla for everyone else
    for c in plan.get("clones", []):
        s = path(c["asset"], src)
        ua, ue = bytearray(open(s + ".uasset", "rb").read()), bytearray(open(s + ".uexp", "rb").read())
        if sha1(ua) != c["uasset_sha1"] or sha1(ue) != c["uexp_sha1"]:
            raise SystemExit(f"{c['asset']} changed since the plan was made (a game patch?), rebuild the plan")
        for old, new in c["strings"]:
            o, n = old.encode(), new.encode()
            if len(o) != len(n) or ua.count(o) < 1:
                raise SystemExit(f"{c['asset']}: name {old!r} not found")
            ua = bytearray(bytes(ua).replace(o, n))
        if c["mode"] == "number":
            if struct.unpack_from("<i", ua, c["export_number_at"])[0] != c["old_number"]:
                raise SystemExit(f"{c['asset']}: export name isn't where the plan says")
            struct.pack_into("<i", ua, c["export_number_at"], c["new_number"])
        for e in c["mi"]:
            check_old(e, ue, c["asset"])
            struct.pack_into("<4f", ue, e["uexp_offset"], *recolor_lin(np.array(e["old"])))
        for e in c.get("scalars", []):
            if struct.unpack_from("<f", ue, e["uexp_offset"])[0] != e["old"]:
                raise SystemExit(f"{c['asset']} {e['param']}: expected {e['old']} (a game patch?)")
            struct.pack_into("<f", ue, e["uexp_offset"], e["new"])
        d = path(c["to"], raw)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        open(d + ".uasset", "wb").write(ua)
        open(d + ".uexp", "wb").write(ue)
        if os.path.exists(s + ".ubulk"):
            shutil.copyfile(s + ".ubulk", d + ".ubulk")
        counts["clones"] = counts.get("clones", 0) + 1
    for rec in plan.get("import_renames", []):
        ua = uassets[rec["asset"]]
        for h in rec["numbers"]:
            if struct.unpack_from("<i", ua, h["number_at"])[0] != h["old"]:
                raise SystemExit(f"{rec['asset']}: import isn't where the plan says")
            struct.pack_into("<i", ua, h["number_at"], h["new"])
        for old, new in rec["strings"]:
            o, n = old.encode(), new.encode()
            if len(o) != len(n) or bytes(ua).count(o) < 2:
                raise SystemExit(f"{rec['asset']}: name {old!r} not found")
            ua[:] = bytes(ua).replace(o, n)
        counts["repointed"] = counts.get("repointed", 0) + 1
    for asset, b in uexps.items():
        s, d = path(asset, src), path(asset, raw)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        grew = len(b) - os.path.getsize(s + ".uexp")
        if grew and not any(r["asset"] == asset for r in plan.get("vm", [])):
            raise SystemExit(f"{asset} changed size")
        open(d + ".uasset", "wb").write(uassets[asset])
        for ext in ("ubulk",):
            if os.path.exists(f"{s}.{ext}"):
                shutil.copyfile(f"{s}.{ext}", f"{d}.{ext}")
        open(d + ".uexp", "wb").write(b)
    print("edits:", counts, "files:", len(uexps))
    out = os.path.join(ROOT, "ironman", "dist", "optional-beams")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, f"{MOD}_9999999_P.*")):
        os.remove(f)
    subprocess.run([RETOC, "pack", raw, "--output", out, "--obfuscate", "--game-paks-dir", args.game], check=True,
                   stdout=subprocess.DEVNULL)
    print(f"wrote {out}\\{MOD}_9999999_P.pak/.utoc/.ucas")


if __name__ == "__main__":
    main()
