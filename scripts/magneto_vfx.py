"""Build the optional blurple effects pak for Discord Magneto.

Applies magneto/vfx_plan.json to Magneto's ability effects (the normal kit, the team-up versions in the MarvelGAS
plugin folder, and the glow on his rings, sword and cannon):
 - mi:            colour params of Magneto's effect materials (and the weapon glow)
 - mi_scalars:    material scalars (a colour ramp row), when a plan needs them
 - lut, lut_chan: Niagara colour curves
 - atlas:         colour ramp rows recoloured in place, and atlas_copy a blurple copy of a row into an empty row, when a
                  plan needs them (this one keeps its ramps in the Magneto-only atlas copies instead)
 - vm:            the colours the Niagara scripts set themselves. Only the constants the friendly colour is built
                  from move (new values go on the end of the script's literal table and just those operands point at
                  them), so enemies keep their red. Effects that never had an enemy colour turn blurple for everyone.
 - clones:        Magneto-only copies of materials other heroes, his lobby or his MVPs also use (Emma Frost's crystal
                  and flare materials, Iron Man's smoke, the rock and flare materials, the ring glow, ...), of the
                  colour atlases CurveAtlas_1037_13_301 (Sept patched) and CurveAtlas_1037_22_001 and of two frozen
                  cannonball meshes (a copied Niagara system would carry its own script edits in "vm"). The originals
                  stay vanilla; import_renames points Magneto's effects, materials and meshes at the copies.
The pak is colour-only, like the Iron Man beams: materials, colour atlases/curves, Niagara systems and the meshes that
carry a Magneto-only material. It never holds animation, montage, sequence, blueprint, ability, cue or table assets
(they change what a character does, and another hero's copy of an ability can play the same ones), and the build
stops if the plan names one or a written package turns out to be one. So an effect Magneto only reaches through a
montage that another hero shares (the Iron Bulwark burst NS_103741_Appear_01, hero 1065's copied shield) stays vanilla.
Purple, violet, blue, cyan and magenta go Discord blurple #5865F2 (same saturation and HDR level); reds, orange fire,
white-hot cores and grey metal stay. Metallic Chaos keeps Scarlet Witch's reds and hot pinks, Magnetic Resonance goes
blurple with its pale yellow turned Discord white. Enemies keep exactly what they saw: a colour stays vanilla wherever
enemies see their own colour through it (a material colour under their red particle, a particle colour every viewer
shares under a material that changes per viewer, a friendly-only colour of a material an IsEnemy binding switches to
enemy mode), friendly-only colours bound per viewer are compensated instead, and where enemies' particle is pure red
only the green and blue channels move ("discord_keep_r").

Most of these files are in the Oct patches now. retoc can't unpack straight from the patch containers, so the chunks of
the newest patch that carries each one (by build number), plus any bulk chunk that patch left in the base container,
are copied byte for byte into a small container in the work folder and unpacked from there. Every value the build
changes is checked against the original first, so a game update makes it stop instead of making a broken pak. It also stops if a package it writes is in any other built
or installed pak (skins, sounds, beams) or isn't a colour asset, and it reads the packed container back before copying
it to dist (every package under its own id, every import resolvable).
The effects live outside /Game/Marvel/Characters, so the container is packed obfuscated.

    python scripts/magneto_vfx.py [--game <Paks dir>]
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
from rivalspak import AES_KEY, Pak, oodle_decompress, write_pak

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RETOC = os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")
WORK = os.path.join(ROOT, "work", "magneto_vfx")
PLAN = os.path.join(ROOT, "magneto", "vfx_plan.json")
OUT = os.path.join(ROOT, "magneto", "dist", "optional-effects")
MOD = "DiscordMagnetoFX"
SKIN_TOC = os.path.join(ROOT, "magneto", "dist", "~mods", "DiscordMagneto_9999999_P.utoc")
BEAMS_PLAN = os.path.join(ROOT, "ironman", "beams_plan.json")

# ------------------------------------------------------------------------------------------------ colour maps
BLURPLE = np.array([0x58, 0x65, 0xF2]) / 255.0
DWHITE = np.array([0xF2, 0xF3, 0xF5]) / 255.0
LUM = np.array([0.2126, 0.7152, 0.0722])


def _lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _hsv(c):
    mx, mn = c.max(), c.min()
    d = mx - mn
    if d < 1e-9:
        return 0.0, 0.0
    if mx == c[0]:
        h = ((c[1] - c[2]) / d) % 6
    elif mx == c[1]:
        h = (c[2] - c[0]) / d + 2
    else:
        h = (c[0] - c[1]) / d + 4
    return h * 60.0, d / mx


def display_hue(c):
    """hue (degrees) of the display (sRGB, brightest channel normalised) version of a linear colour"""
    lin = np.clip(np.array(c[:3], float), 0, None)
    if lin.max() <= 1e-6:
        return None
    n = lin / lin.max()
    return _hsv(np.where(n <= 0.0031308, 12.92 * n, 1.055 * np.power(n, 1 / 2.4) - 0.055))[0]


def to_blurple(c, lo=(170, 186), hi=(327, 337), keep_luma=0.6, max_gain=3.0):
    """cyan..blue..violet..magenta (display hue lo..hi, smooth edges) -> Discord blurple with the same saturation and
    HDR level, eased back to about the same perceived brightness. Everything else stays."""
    c = np.array(c, float)
    rgb = np.clip(c[:3], 0, None)
    v, mn = rgb.max(), rgb.min()
    if v <= 1e-6:
        return c
    s = (v - mn) / v
    h = display_hue(rgb) or 0.0
    w = _smooth(h, lo[0], lo[1]) * (1 - _smooth(h, hi[0], hi[1])) * _smooth(s, 0.08, 0.16)
    if w <= 0:
        return c
    new = v * ((1 - s) + s * _lin(BLURPLE) / _lin(BLURPLE).max())
    lo_, ln = (rgb * LUM).sum(), (new * LUM).sum()
    g = new * np.clip(lo_ / ln if ln > 1e-9 else 1.0, 0.35, 1.0) ** keep_luma
    lg = (g * LUM).sum()
    if lg > max_gain * max(lo_, 1e-9):
        g = g * (max_gain * lo_ / lg)
    out = c.copy()
    out[:3] = rgb * (1 - w) + g * w
    return out


def to_resonance(c):
    """Magnetic Resonance scripts and curves: the pale yellow (display hue 38-112) goes Discord white at the same HDR
    level, and the blurple band starts at teal"""
    c = np.array(c, float)
    rgb = np.clip(c[:3], 0, None)
    v, mn = rgb.max(), rgb.min()
    if v > 1e-6:
        s = (v - mn) / v
        h = display_hue(rgb) or 0.0
        w = _smooth(h, 38, 48) * (1 - _smooth(h, 100, 112)) * _smooth(s, 0.08, 0.16)
        if w > 0:
            c = c.copy()
            c[:3] = rgb * (1 - w) + v * _lin(DWHITE) * w
    return to_blurple(c, lo=(140, 155))


def to_white(c):
    """Discord white #F2F3F5 at the colour's brightest channel level"""
    c = np.array(c, float)
    out = c.copy()
    out[:3] = np.clip(c[:3], 0, None).max() * _lin(DWHITE) / _lin(DWHITE).max()
    return out


def to_blurple_keep_red(c):
    """blurple green and blue, vanilla red: for a material that enemies see through a pure red (r, 0, 0) particle
    colour, so the product they see stays exactly vanilla"""
    out = to_blurple(c)
    out[0] = np.array(c, float)[0]
    return out


MAPS = {
    "discord": to_blurple,
    "resonance": to_resonance,
    "mr": lambda c: to_blurple(c, lo=(150, 165)),     # Magnetic Resonance materials: cyan all the way
    "mc": lambda c: to_blurple(c, hi=(315, 325)),     # Metallic Chaos: Scarlet Witch's hot pinks stay
    "white": to_white,
    "discord_keep_r": to_blurple_keep_red,
}


def map_rows(raw, dt, name, pre_tint=None):
    """float RGBA rows through a map; with pre_tint K the curve is multiplied by the constant K on its way to the
    screen, so new = map(K x old) / K (channels where K is 0 keep their value)"""
    a = np.frombuffer(bytes(raw), dt).astype(np.float64).reshape(-1, 4)
    f = MAPS[name]
    if pre_tint is None:
        out = np.array([f(r) for r in a])
    else:
        k = np.array(list(pre_tint) + [1.0], np.float64)
        out = np.array([f(r) for r in a * k]) / np.where(k != 0, k, 1.0)
        out = np.where(k != 0, out, a)
    return out.astype(dt).tobytes()


# ------------------------------------------------------------------------------------------------ small helpers
def sha1(b):
    return hashlib.sha1(bytes(b)).hexdigest()


def file_rel(asset):
    """/Game/X -> Marvel/Content/X, /MarvelGAS/X -> Marvel/Plugins/MarvelGAS/Content/X"""
    if asset.startswith("/MarvelGAS/"):
        return "Marvel/Plugins/MarvelGAS/Content/" + asset[len("/MarvelGAS/"):]
    return "Marvel/Content/" + asset[len("/Game/"):]


def short(asset):
    return asset.split("/")[-1]


def stop(msg):
    raise SystemExit(msg)


def changed(asset):
    stop(f"{asset} changed since the plan was made (a game patch?), rebuild the plan")


# ------------------------------------------------------------------------------------------------ IoStore reading
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


def package_ids(utoc):
    """the package ids a container has export data for (just the TOC's chunk id table)"""
    with open(utoc, "rb") as f:
        head = f.read(144)
        if head[:16] != MAGIC:
            return set()
        n = struct.unpack_from("<I", head, 24)[0]
        ids = f.read(12 * n)
    return {int.from_bytes(ids[12 * i:12 * i + 8], "little") for i in range(n) if ids[12 * i + 11] == 1}


def patch_version(name):
    """Patch_-Windows_1.1.3913745_P -> (1, 1, 3913745), so patches sort by build number and not as text"""
    m = re.search(r"_(\d+(?:\.\d+)*)_P$", name)
    if not m:
        stop(f"can't read the build number of {name}")
    return tuple(int(x) for x in m.group(1).split("."))


class Game:
    def __init__(self, paks):
        self.paks = paks
        self.names = sorted(os.path.basename(u)[:-5] for u in glob.glob(os.path.join(paks, "*.utoc")))
        self.patches = sorted((n for n in self.names if n.startswith("Patch")), key=patch_version, reverse=True)   # newest first
        if not self.patches:
            stop("no Patch_ containers in the Paks folder, this plan needs the patches up to 1.1.3962284")
        self._t, self._h, self._b = {}, {}, {}

    def toc(self, name):
        if name not in self._t:
            self._t[name] = Toc(os.path.join(self.paks, name + ".utoc"))
        return self._t[name]

    def header(self, name):
        if name not in self._h:
            self._h[name] = self.toc(name).header()
        return self._h[name]

    def base_names(self):
        return [n for n in self.names if not n.startswith("Patch")]

    def bulk_chunks(self, name):
        """{chunk id: index} of a container's bulk data chunks (BulkData, OptionalBulkData, MemoryMappedBulkData)"""
        if name not in self._b:
            self._b[name] = {c: i for i, c in enumerate(self.toc(name).chunk_ids) if c[11] in (2, 3, 4)}
        return self._b[name]

    def patch_copy(self, asset):
        """[(patch container, zen bytes)] of every patch container that carries the package, newest first"""
        key = file_rel(asset) + ".uasset"
        return [(c, self.toc(c).read(self.toc(c).files[key])) for c in self.patches if key in self.toc(c).files]

    def gather(self, assets):
        """the newest patch copy of each package: every chunk byte for byte, plus its store entry. Every patch
        container's header lists every package of the game, so the store entry is the newest header's (the one the
        game uses); older headers can still hold an older entry of a package a later patch changed.
        A patch can carry only the export chunk of a package and leave its bulk data where it was (the Oct 16 patch
        does that with the ring mesh): the game then reads that bulk chunk from the next container that has it, so
        it's taken from there too."""
        chunks, packages = [], []
        for asset in assets:
            key = file_rel(asset) + ".uasset"
            c = next(c for c in self.patches if key in self.toc(c).files)
            t = self.toc(c)
            pid = int.from_bytes(t.chunk_ids[t.files[key]][:8], "little")
            if pid != cityhash.pkg_id(asset):
                stop(f"{asset}: the patch chunk isn't the package id of its path")
            stem, named = key[:-len(".uasset")], set()
            for ext in (".uasset", ".ubulk", ".uptnl", ".m.ubulk"):
                if stem + ext in t.files:
                    i = t.files[stem + ext]
                    chunks.append((stem + ext, t.chunk_ids[i], t.read(i), t.metas[i]))
                    named.add(i)
            if any(int.from_bytes(cc[:8], "little") == pid and i not in named for i, cc in enumerate(t.chunk_ids)):
                stop(f"{asset}: the package has a chunk this build doesn't know")
            for ext, kind in ((".ubulk", 2), (".uptnl", 3), (".m.ubulk", 4)):
                if stem + ext in t.files:
                    continue
                cid = struct.pack("<Q", pid) + b"\0\0\0" + bytes([kind])
                for other in self.patches[self.patches.index(c) + 1:] + self.base_names():
                    i = self.bulk_chunks(other).get(cid)
                    if i is not None:
                        o = self.toc(other)
                        chunks.append((stem + ext, cid, o.read(i), o.metas[i]))
                        break
            ents = [self.header(p)[pid] for p in self.patches if pid in self.header(p)]
            if not ents or pid not in self.header(c) or self.header(c)[pid][0] != ents[0][0]:
                stop(f"{asset}: the newest patch header and the patch that carries it ({c}) disagree about its imports")
            packages.append((pid, ents[0][0], ents[0][1]))
        return chunks, packages


# ------------------------------------------------------------------------------------------------ guards
def written_assets(plan):
    out = {e["asset"] for k in ("mi", "mi_scalars", "lut", "lut_chan", "atlas", "atlas_copy", "vm", "import_renames") for e in plan[k]}
    return out | {c["to"] for c in plan["clones"]}


# The pak is colour-only (like the Iron Man beams). The asset of every package it holds has to be one of these, and no
# export in it may be an animation / montage / sequence / blueprint / ability / cue / table (a Niagara system's own
# data interfaces are part of the effect, whatever they read).
COLOUR_CLASSES = {"MaterialInstanceConstant", "NiagaraSystem", "CurveLinearColorAtlas", "CurveLinearColor",
                  "StaticMesh", "SkeletalMesh", "Texture2D"}
NOT_COLOUR = re.compile(r"Anim|Montage|Sequence|BlendSpace|PoseAsset|Blueprint|GeneratedClass|Ability|GameplayEffect|"
                        r"GameplayCue|DataTable|CurveTable|StringTable|^AN_", re.I)
NOT_COLOUR_PATH = re.compile(r"/(Animations?|Abilit(y|ies)|Cues?|Blueprints?|DataTables?|Sequences?)/|Montage|Table$|"
                             r"_BP$|/(LS|GA|GE|AN|ABP|BS|BP|DT)_", re.I)


def export_classes(uasset):
    """[(export name, class name, package of the class, outer index)] from a legacy .uasset's name, import and export
    maps. A class that is an export of the package itself comes back with the package '<this package>'."""
    d = open(uasset, "rb").read()
    o = 24                                              # tag and the five version ints
    o += 4 + 20 * struct.unpack_from("<i", d, o)[0]     # custom versions
    o += 4                                              # total header size
    n = struct.unpack_from("<i", d, o)[0]
    o += 4 + (n if n >= 0 else -2 * n)                  # package name
    o += 4                                              # package flags
    name_count, name_off = struct.unpack_from("<ii", d, o)
    o += 8 + 8 + 8                                      # names, soft object paths, gatherable text
    exp_count, exp_off, imp_count, imp_off, dep_off = struct.unpack_from("<5i", d, o)
    names, p = [], name_off
    for _ in range(name_count):
        n = struct.unpack_from("<i", d, p)[0]
        p += 4
        names.append(d[p:p + n - 1].decode("latin1") if n >= 0 else d[p:p - 2 * n - 2].decode("utf-16-le"))
        p += (n if n >= 0 else -2 * n) + 4              # the string and its hash

    def fname(i, num):
        return names[i] if num == 0 else "%s_%d" % (names[i], num - 1)

    isz = (exp_off - imp_off) // imp_count if imp_count else 0
    imps = [struct.unpack_from("<7i", d, imp_off + i * isz) for i in range(imp_count)]
    esz = (dep_off - exp_off) // exp_count
    out = []
    for i in range(exp_count):
        ci, _, _, outer, on, onn = struct.unpack_from("<6i", d, exp_off + i * esz)
        if ci < 0:                                      # an import: its object name is the class, its outer the package
            _, _, _, _, cls_outer, cn, cnn = imps[-ci - 1]
            pkg = fname(*imps[-cls_outer - 1][5:7]) if cls_outer < 0 else "?"
            out.append((fname(on, onn), fname(cn, cnn), pkg, outer))
        else:
            cls = fname(*struct.unpack_from("<ii", d, exp_off + (ci - 1) * esz + 16)) if ci > 0 else "?"
            out.append((fname(on, onn), cls, "<this package>", outer))
    return out


def check_colour_only(raw):
    """every package about to be packed is a colour asset (see COLOUR_CLASSES / NOT_COLOUR); returns their count"""
    n = 0
    for f in sorted(glob.glob(os.path.join(raw, "**", "*.uasset"), recursive=True)):
        rel = os.path.relpath(f, raw).replace("\\", "/")[:-len(".uasset")]
        ex = export_classes(f)
        stem = rel.rsplit("/", 1)[-1]
        main = [c for name, c, _, outer in ex if name in (stem, stem + "_C") and outer == 0]   # _C: a blueprint
        if len(main) != 1 or main[0] not in COLOUR_CLASSES:
            stop(f"{rel} is a {main or '(no asset export)'}, not a colour asset: this pak is colour-only")
        for name, c, pkg, _ in ex:
            if not pkg.startswith("/Script/"):
                stop(f"{rel}: {name} is a {c} of {pkg} (a blueprint class): this pak is colour-only")
            if not c.startswith("Niagara") and NOT_COLOUR.search(c):
                stop(f"{rel}: {name} is a {c}: this pak is colour-only")
        n += 1
    return n


def check_game(plan, game):
    """stop before building from stale files, and make sure the copies' names are still free"""
    bad = sorted(a for a in written_assets(plan) | {c["asset"] for c in plan["clones"]} if NOT_COLOUR_PATH.search(a))
    if bad:
        stop(f"the plan names animation / montage / ability / cue / table assets, this pak is colour-only: {bad[:5]}")
    ids = {n: package_ids(os.path.join(game.paks, n + ".utoc")) for n in game.names}
    patched_ids = set().union(*[ids[p] for p in game.patches])
    shadowed = {s["asset"]: s for s in plan["shadowed_base"]}
    for a in plan["containers"]:
        if cityhash.pkg_id(a) in patched_ids and a not in shadowed:
            stop(f"{a} is in a patch container now, so the plan is out of date: rebuild the plan")
    for s in plan["shadowed_base"]:
        got = game.patch_copy(s["asset"])
        if [c for c, _ in got] != s["patch_containers"] or sha1(got[0][1]) != s["patch_zen_sha1"]:
            stop(f"{s['asset']} changed in a patch, the Magneto-only copy made from the base file would be stale: rebuild the plan")
    for p in plan["patched_sources"]:
        got = game.patch_copy(p["asset"])
        if not got or got[0][0] != p["container"] or sha1(got[0][1]) != p["zen_sha1"]:
            changed(p["asset"])
    every = set().union(*ids.values())
    for p in game.patches:                  # the patch headers list every package of the game
        every |= set(game.header(p))
    for c in plan["clones"]:
        if cityhash.pkg_id(c["to"]) in every:
            stop(f"{c['to']} exists in the game now, pick another name for the copy of {c['asset']}")
    mine = written_assets(plan)
    for need in (BEAMS_PLAN, SKIN_TOC):
        if not os.path.exists(need):
            stop(f"{need} is missing: build the skin (and keep the Iron Man beams plan) first, this pak has to be checked against them")
    im = json.load(open(BEAMS_PLAN, encoding="utf-8"))   # the Iron Man beams pak has to keep working next to this one
    theirs = set(im["containers"]) | {c["to"] for c in im.get("clones", [])}
    if mine & theirs:
        stop(f"these are in the Iron Man beams plan too: {sorted(mine & theirs)}")
    # and so do the skins, sounds and beams, installed or built: no path, package or copy id of ours in any of them
    my_paths = {file_rel(a) for a in mine}
    my_ids = {cityhash.pkg_id(a) for a in mine}
    others = set(glob.glob(os.path.join(game.paks, "~mods", "*.utoc")) + glob.glob(os.path.join(game.paks, "~mods", "*.pak")))
    for d in ("dist", os.path.join("ironman", "dist"), os.path.join("magneto", "dist")):
        others |= set(glob.glob(os.path.join(ROOT, d, "*", "*.utoc")) + glob.glob(os.path.join(ROOT, d, "*", "*.pak")))
    others = sorted(o for o in others if not os.path.basename(o).startswith(MOD + "_"))
    for o in others:
        if o.endswith(".utoc"):
            t = Toc(o)
            paths = {k.rsplit(".", 1)[0] if not k.endswith(".m.ubulk") else k[:-len(".m.ubulk")] for k in t.files}
            try:
                ids = package_ids(o) | set(t.header())
            except (IndexError, ValueError):
                stop(f"{o}: can't read its container header")
        else:
            p = Pak(o)
            paths = {("Marvel/" + k.split("Marvel/", 1)[1] if "Marvel/" in k else k).rsplit(".", 1)[0] for k in set(p.files) | p.no_location}
            ids = set()
        hit = sorted((my_paths & paths) | {a for a in mine if cityhash.pkg_id(a) in ids})
        if hit:
            stop(f"{os.path.basename(o)} has these already: {hit[:10]}")
    if len(my_ids) != len(mine) or len({cityhash.pkg_id(c["to"]) for c in plan["clones"]}) != len(plan["clones"]):
        stop("two packages of this pak have the same package id")


# ------------------------------------------------------------------------------------------------ unpacking
def unpack(plan, game, src):
    by_container = {}
    for asset, cont in plan["containers"].items():
        by_container.setdefault(cont, []).append(asset)
    for cont, assets in sorted(by_container.items()):
        for i in range(0, len(assets), 100):
            filters = []
            for a in assets[i:i + 100]:
                filters += ["--filter", "../../../" + file_rel(a) + ".uasset"]
            # --full-iostore-check resolves every import against the whole game; without it retoc gives imports
            # from other containers an extra name, and some materials come back with the wrong header size
            subprocess.run([RETOC, "unpack", os.path.join(game.paks, cont + ".utoc"), *filters, "--output", src,
                            "--game-paks-dir", game.paks, "--full-iostore-check"], check=True, stdout=subprocess.DEVNULL)
    if plan["patched_sources"]:
        chunks, packages = game.gather([p["asset"] for p in plan["patched_sources"]])
        carrier = write_carrier(os.path.join(WORK, "carrier"), "Magneto_PatchSrc_P", chunks, packages)
        subprocess.run([RETOC, "unpack", carrier, "--output", src, "--game-paks-dir", game.paks, "--full-iostore-check"],
                       check=True, stdout=subprocess.DEVNULL)


# ------------------------------------------------------------------------------------------------ scripts
def colour_new(col):
    old = np.array(col["old"], np.float64)
    if "set" in col:
        new = np.array(col["set"], np.float64)
    else:
        new = MAPS[col["map"]](old)
        for s, i in col.get("mean", []):     # a fixed zero channel that now reads its neighbour's register
            new[s] = new[i] = (new[s] + new[i]) / 2
    if not np.allclose(new, col["expect"], atol=1e-5):
        stop(f"the colour maths doesn't match the plan for {col['var']} ({new} vs {col['expect']})")
    return old, new


def apply_vm(rec, uexp, uasset):
    """point the friendly colour operands of each script at new literals (or, for a fixed zero channel, at the
    register its neighbour channel reads); grows the literal tables and fixes the export sizes/offsets and
    BulkDataStartOffset in the .uasset. uexp/uasset are bytearrays."""
    where = f"{short(rec['asset'])}"
    inserts = []
    for sc in rec["scripts"]:
        at, n, base = sc["lit_at"], sc["lit_count"], sc["lit_base"]
        if struct.unpack_from("<i", uexp, at - 4)[0] != n:
            stop(f"{where} {sc['name']}: literal table isn't where the plan says")
        lits = [bytes(uexp[at + 4 * k:at + 4 * k + 4]) for k in range(n // 4)]
        added = []
        for col in sc["colours"]:
            old, new = colour_new(col)
            for op in col["operands"]:
                if struct.unpack_from("<H", uexp, op["uexp_offset"])[0] != op["old_operand"]:
                    stop(f"{where} {sc['name']} {col['var']}: operand changed (a game patch?)")
                reads_register = op.get("to_const") or "param" in op
                if not reads_register:
                    ob = bytes.fromhex(op["old_literal"]) if "old_literal" in op else struct.pack("<f", float(old[op["comp"]]) / op["scale"])
                    k = (op["old_operand"] - base) // 4
                    if not 0 <= k < len(lits) or lits[k] != ob:
                        stop(f"{where} {sc['name']} {col['var']}: literal changed (a game patch?)")
                if "to_register" in op:
                    if not uexp[op["types_at"]] >> op["bit"] & 1:
                        stop(f"{where} {sc['name']} {col['var']}: the zero channel isn't a constant")
                    if struct.unpack_from("<H", uexp, op["neighbour_operand_at"])[0] != op["to_register"] or uexp[op["neighbour_types_at"]] & 1:
                        stop(f"{where} {sc['name']} {col['var']}: the neighbour channel doesn't read that register")
                    uexp[op["types_at"]] &= ~(1 << op["bit"]) & 0xFF
                    struct.pack_into("<H", uexp, op["uexp_offset"], op["to_register"])
                    continue
                nb = struct.pack("<f", op["set"] if "set" in op else float(new[op["comp"]]) / op["scale"])
                if nb in lits:
                    slot = lits.index(nb)
                else:
                    if nb not in added:
                        added.append(nb)
                    slot = len(lits) + added.index(nb)
                off = base + 4 * slot
                if off > 0xFFFF:
                    stop(f"{where}: constant offset overflow")
                if "types_at" in op:            # a register read that becomes a constant: set its constant bit
                    if uexp[op["types_at"]] >> op["bit"] & 1:
                        stop(f"{where} {sc['name']} {col['var']}: operand already constant")
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
            stop(f"{where}: literal table isn't inside one export")
        b = rec["bulk_start_at"]
        struct.pack_into("<q", uasset, b, struct.unpack_from("<q", uasset, b)[0] + k)


# ------------------------------------------------------------------------------------------------ the build
def set_colour(b, e, where):
    """the colour's four float32s have to be exactly the plan's original bytes; the new colour is mapped from them"""
    o = e["uexp_offset"]
    cur = bytes(b[o:o + 16])
    if cur.hex() != e["old_hex"]:
        stop(f"{where} {e['param']}: expected {e['old']}, found {list(struct.unpack('<4f', cur))} (a game patch?)")
    new = MAPS[e["map"]](np.frombuffer(cur, "<f4").astype(np.float64))
    if not np.allclose(new, e["new"], rtol=0, atol=1e-9):
        stop(f"{where} {e['param']}: the colour maths doesn't match the plan")
    struct.pack_into("<4f", b, o, *new)


def set_scalar(b, e, where):
    if struct.unpack_from("<f", b, e["uexp_offset"])[0] != e["old"]:
        stop(f"{where} {e['param']}: expected {e['old']} (a game patch?)")
    struct.pack_into("<f", b, e["uexp_offset"], e["new"])


def set_range(b, off, n, old_sha1, new, new_sha1, where):
    if sha1(b[off:off + n]) != old_sha1:
        changed(where)
    if len(new) != n or sha1(new) != new_sha1:
        stop(f"{where}: the colour maths doesn't match the plan (bytes at {off})")
    b[off:off + n] = new


def _pkg_name(ua):
    """the package name FString of a legacy .uasset summary (the first /Game/ or /MarvelGAS/ FString)"""
    m = re.search(rb"(?s)(....)(/(?:Game|MarvelGAS)/[ -~]+?)\0", bytes(ua[:512]))
    if not m or struct.unpack("<i", m.group(1))[0] != len(m.group(2)) + 1:
        return None
    return m.group(2).decode()


def check_copy_name(ua, c):
    """after the renames a copy has to be the package it's written as: summary package name, and no trace of the
    original's path or (for a renamed copy) its name"""
    if _pkg_name(ua) != c["to"]:
        stop(f"{c['to']}: the copy's package name is {_pkg_name(ua)!r} (plan says {c['to']})")
    if (c["asset"] + "\0").encode() in ua:
        stop(f"{c['to']}: the copy still names {c['asset']}")
    if c["mode"] == "string":
        if (short(c["asset"]) + "\0").encode() in ua or (short(c["to"]) + "\0").encode() not in ua:
            stop(f"{c['to']}: the object name wasn't renamed")
    elif struct.unpack_from("<i", ua, c["export_number_at"])[0] != c["new_number"] or \
            not c["to"].endswith("_%d" % (c["new_number"] - 1)):
        stop(f"{c['to']}: the export's name number doesn't give the copy's name")


def apply(plan, src, raw):
    def path(asset, root):
        return os.path.join(root, *file_rel(asset).split("/"))

    uexps, uassets = {}, {}

    def uexp(asset):
        if asset not in uexps:
            f = path(asset, src)
            if not os.path.exists(f + ".uexp"):
                stop(f"{asset} didn't come out of the game files")
            uexps[asset] = bytearray(open(f + ".uexp", "rb").read())
            uassets[asset] = bytearray(open(f + ".uasset", "rb").read())
        return uexps[asset]

    # whole-file checks first, before anything in them changes
    for p in plan["patched_sources"]:
        f = path(p["asset"], src)
        if sha1(open(f + ".uasset", "rb").read()) != p["uasset_sha1"] or sha1(open(f + ".uexp", "rb").read()) != p["uexp_sha1"]:
            stop(f"{p['asset']}: retoc gave different files from the patch than when the plan was made")
        bulk = ".ubulk" in p.get("chunks", [])
        if bulk != os.path.exists(f + ".ubulk") or (bulk and sha1(open(f + ".ubulk", "rb").read()) != p["ubulk_sha1"]):
            stop(f"{p['asset']}: its bulk data isn't what the plan was made with")
    for rec in plan["vm"]:
        b = uexp(rec["asset"])
        if sha1(b) != rec["uexp_sha1"] or sha1(uassets[rec["asset"]]) != rec["uasset_sha1"]:
            changed(rec["asset"])
    for rec in plan["import_renames"]:
        uexp(rec["asset"])
        if sha1(uassets[rec["asset"]]) != rec["uasset_sha1"]:
            changed(rec["asset"])

    counts = {}

    def count(k, n=1):
        counts[k] = counts.get(k, 0) + n

    for e in plan["mi"]:
        set_colour(uexp(e["asset"]), e, short(e["asset"]))
        count("mi")
    for e in plan["mi_scalars"]:
        set_scalar(uexp(e["asset"]), e, short(e["asset"]))
        count("mi_scalars")
    for e in plan["lut"]:
        b = uexp(e["asset"])
        o, n = e["uexp_offset"], e["length"]
        set_range(b, o, n, e["sha1"], map_rows(b[o:o + n], "<f4", e["map"], e.get("pre_tint")), e["new_sha1"], e["asset"])
        count("lut")
    for e in plan["lut_chan"]:      # per channel factor (a GPU emitter whose tint has a channel wired to zero)
        b = uexp(e["asset"])
        o, n = e["uexp_offset"], e["length"]
        new = (np.frombuffer(bytes(b[o:o + n]), "<f4").astype(np.float64).reshape(-1, 4) * np.array(e["scale"])).astype("<f4").tobytes()
        set_range(b, o, n, e["sha1"], new, e["new_sha1"], e["asset"])
        count("lut_chan")
    # atlas row copies read the vanilla source row, so they go before the rows recoloured in place
    for e in plan["atlas_copy"]:
        b = uexp(e["asset"])
        s0, d0, n = e["src_uexp_offset"], e["dst_uexp_offset"], e["length"]
        if sha1(b[s0:s0 + n]) != e["src_sha1"]:
            changed(e["asset"])
        set_range(b, d0, n, e["dst_sha1"], map_rows(b[s0:s0 + n], "<f2", e["map"]), e["new_sha1"], e["asset"])
        count("atlas_copy")
    for e in plan["atlas"]:
        b = uexp(e["asset"])
        o, n = e["uexp_offset"], e["length"]
        set_range(b, o, n, e["sha1"], map_rows(b[o:o + n], "<f2", e["map"]), e["new_sha1"], e["asset"])
        count("atlas")
    # the script edits grow the files, so they go last (every offset above is in the original layout)
    for rec in plan["vm"]:
        apply_vm(rec, uexp(rec["asset"]), uassets[rec["asset"]])
        count("vm colours", sum(len(sc["colours"]) for sc in rec["scripts"]))
    # Magneto-only copies: the same package under a new name of the same length (a new FName number, or
    # 001 -> 0W1), recoloured; the original stays vanilla for everyone else
    for c in plan["clones"]:
        s = path(c["asset"], src)
        ua, ue = bytearray(open(s + ".uasset", "rb").read()), bytearray(open(s + ".uexp", "rb").read())
        if sha1(ua) != c["uasset_sha1"] or sha1(ue) != c["uexp_sha1"]:
            changed(c["asset"])
        if "vm" in c:                           # a copied Niagara system: its script colours move onto the copy
            if c["vm"]["asset"] != c["asset"] or c["vm"]["uasset_sha1"] != c["uasset_sha1"] or c["vm"]["uexp_sha1"] != c["uexp_sha1"]:
                stop(f"{c['to']}: the script edits aren't for {c['asset']}")
            apply_vm(c["vm"], ue, ua)
            count("vm colours", sum(len(sc["colours"]) for sc in c["vm"]["scripts"]))
        for old, new in c["strings"]:
            o, n = old.encode(), new.encode()
            if len(o) != len(n) or ua.count(o) < 1:
                stop(f"{c['asset']}: name {old!r} not found")
            ua = bytearray(bytes(ua).replace(o, n))
        if c["mode"] == "number":
            if struct.unpack_from("<i", ua, c["export_number_at"])[0] != c["old_number"]:
                stop(f"{c['asset']}: export name isn't where the plan says")
            struct.pack_into("<i", ua, c["export_number_at"], c["new_number"])
        for h in c.get("numbers", []):          # the copy itself imports another copy (a new FName number)
            if struct.unpack_from("<i", ua, h["number_at"])[0] != h["old"]:
                stop(f"{c['asset']}: import isn't where the plan says")
            struct.pack_into("<i", ua, h["number_at"], h["new"])
        for e in c["mi"]:
            set_colour(ue, e, short(c["to"]))
        for e in c.get("scalars", []):
            set_scalar(ue, e, short(c["to"]))
        for e in c.get("atlas_rows") or []:
            o, n = e["uexp_offset"], e["length"]
            set_range(ue, o, n, e["sha1"], map_rows(ue[o:o + n], "<f2", c["map"]), e["new_sha1"], f"{c['asset']} row {e['row']}")
        check_copy_name(ua, c)
        d = path(c["to"], raw)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        open(d + ".uasset", "wb").write(ua)
        open(d + ".uexp", "wb").write(ue)
        if os.path.exists(s + ".ubulk"):
            shutil.copyfile(s + ".ubulk", d + ".ubulk")
        count("copies")
    for rec in plan["import_renames"]:
        ua = uassets[rec["asset"]]
        for h in rec["numbers"]:
            if struct.unpack_from("<i", ua, h["number_at"])[0] != h["old"]:
                stop(f"{rec['asset']}: import isn't where the plan says")
            struct.pack_into("<i", ua, h["number_at"], h["new"])
        for old, new in rec["strings"]:
            o, n = old.encode(), new.encode()
            if len(o) != len(n) or bytes(ua).count(o) != 2:
                stop(f"{rec['asset']}: name {old!r} isn't there twice (import and package)")
            ua[:] = bytes(ua).replace(o, n)
        count("repointed")
    # every edit except the script ones overwrites bytes in place; a size change means something went wrong
    vm_assets = {r["asset"] for r in plan["vm"]}
    for asset, b in uexps.items():
        s, d = path(asset, src), path(asset, raw)
        if len(uassets[asset]) != os.path.getsize(s + ".uasset") or (len(b) != os.path.getsize(s + ".uexp") and asset not in vm_assets):
            stop(f"{asset} changed size")
        os.makedirs(os.path.dirname(d), exist_ok=True)
        open(d + ".uasset", "wb").write(uassets[asset])
        open(d + ".uexp", "wb").write(b)
        if os.path.exists(s + ".ubulk"):
            shutil.copyfile(s + ".ubulk", d + ".ubulk")
    wrote = {os.path.relpath(f, raw).replace("\\", "/")[:-len(".uasset")] for f in glob.glob(os.path.join(raw, "**", "*.uasset"), recursive=True)}
    want = {file_rel(a) for a in written_assets(plan)}
    if wrote != want:
        stop(f"wrote {sorted(wrote ^ want)[:5]} which the plan doesn't list (or missed them)")
    return counts, len(wrote)


def check_output(plan, game, utoc):
    """read the packed container back: exactly the planned packages, each under its own package id, and every
    import of every package resolves to a package of this pak or of the game"""
    t = Toc(utoc)
    want = {file_rel(a) + ".uasset": a for a in written_assets(plan)}
    got = {k for k in t.files if k.endswith(".uasset")}
    if got != set(want):
        stop(f"the packed container has {sorted(got ^ set(want))[:5]} which the plan doesn't list (or misses them)")
    mine = {}
    for k, a in want.items():
        pid = int.from_bytes(t.chunk_ids[t.files[k]][:8], "little")
        if pid != cityhash.pkg_id(a):
            stop(f"{a}: packed under package id {pid:x}, its path gives {cityhash.pkg_id(a):x}")
        mine[pid] = a
    every = set()
    for n in game.names:
        every |= package_ids(os.path.join(game.paks, n + ".utoc"))
    for p in game.patches:
        every |= set(game.header(p))
    hdr = t.header()
    if set(hdr) != set(mine):
        stop("the container header doesn't list exactly the packed packages")
    for pid, (imps, _) in hdr.items():
        bad = [i for i in imps if i not in mine and i not in every]
        if bad:
            stop(f"{mine[pid]} imports packages that exist nowhere: {[hex(i) for i in bad]}")
    return len(mine), sum(len(v[0]) for v in hdr.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS, help="the game's Content\\Paks folder")
    args = ap.parse_args()
    if not os.path.exists(os.path.join(args.game, "pakchunk0-Windows.utoc")):
        stop(f"that's not the game's Paks folder: {args.game} (use --game)")
    plan = json.load(open(PLAN, encoding="utf-8"))
    game = Game(args.game)
    check_game(plan, game)
    shutil.rmtree(WORK, ignore_errors=True)
    src, raw = os.path.join(WORK, "game"), os.path.join(WORK, MOD)
    unpack(plan, game, src)
    counts, nfiles = apply(plan, src, raw)
    print("edits:", counts, "packages:", nfiles)
    print(f"colour-only: {check_colour_only(raw)} packages, all materials / colour atlases / Niagara systems / meshes")
    packed = os.path.join(WORK, "packed")      # packed and read back here first; dist only gets a checked pak
    subprocess.run([RETOC, "pack", raw, "--output", packed, "--obfuscate", "--game-paks-dir", args.game], check=True,
                   stdout=subprocess.DEVNULL)
    made = sorted(glob.glob(os.path.join(packed, f"{MOD}_9999999_P.*")))
    if len(made) != 3:
        stop(f"retoc didn't write the pak/utoc/ucas: {made}")
    npk, nimp = check_output(plan, game, os.path.join(packed, f"{MOD}_9999999_P.utoc"))
    print(f"read back: {npk} packages, all {nimp} imports resolve")
    os.makedirs(OUT, exist_ok=True)
    for f in glob.glob(os.path.join(OUT, f"{MOD}_9999999_P.*")):
        os.remove(f)
    for f in made:
        shutil.copyfile(f, os.path.join(OUT, os.path.basename(f)))
    print(f"wrote {OUT}\\{MOD}_9999999_P.pak/.utoc/.ucas ({sum(os.path.getsize(f) for f in made) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
