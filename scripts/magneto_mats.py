"""Discord blurple for the red glow on Discord Magneto's cape (default costume 1037001).

The in-match cape material (MI_1037001_Equip_03, parent M_Common_Cape1037_19_001) has a glow along the
cape edges: CapeEmi_Color times an edge mask (T_ClockMask_19_001_M) with a slow pulse. It is red. This moves
that colour (and the cape's EmissiveColor, also red) to the blurple hue at the same HDR brightness.
The purple EmissiveColor on the armour (MI_1037001_Equip_01) is left alone: that MI sets EmissiveStrength to 0
in match and in the lobby, so it never shows.

The cape MI is replaced by a patch (the Oct 22 one right now) and retoc can't unpack patch containers. So the edit
is made on the current copy like this: retoc unpacks the base copy (pakchunkCharacter) as a legacy package, the export
data of the newest copy is read straight from the patch container and put into that legacy package (the
header tables of both copies have to match exactly, otherwise it stops), then the colours are changed in place.

Other costumes whose cape MI has this one as parent (1037100, 1037101, 1037102, 1037500, 1037501) get the
blurple glow too, they don't set CapeEmi_Color themselves.

    python scripts/magneto_mats.py [--game <Paks dir>] [--out <raw folder>]

magneto_skin.py calls build(raw, game) before it packs the raw folder.
"""
import argparse
import glob
import os
import re
import shutil
import struct
import subprocess

import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

import cityhash
from paths import DEFAULT_PAKS
from rivalspak import AES_KEY, oodle_decompress

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RETOC = os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")
WORK = os.path.join(ROOT, "work", "magneto_mats")
BASE = "pakchunkCharacter-Windows"
TAG = b"\xc1\x83\x2a\x9e"

BLURPLE = np.array([0x58, 0x65, 0xF2]) / 255.0

# asset -> {vector param: value the game has now}. Only these move, and only if they still hold these values.
EDITS = {
    "Marvel/Content/Marvel/Characters/1037/1037001/Materials/MI_1037001_Equip_03": {
        "CapeEmi_Color": (0.578125, 0.0, 0.0, 0.0),
        "EmissiveColor": (1.0, 0.0, 0.0, 0.0),
    },
}


def _lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_blurple(c):
    """linear HDR colour -> Discord blurple (#5865F2) with the same peak value; alpha stays"""
    c = np.array(c, np.float64)
    tgt = _lin(BLURPLE) / _lin(BLURPLE).max()
    out = c.copy()
    out[:3] = tgt * c[:3].max()
    return tuple(float(x) for x in out)


class Container:
    """one of the game's IoStore containers (.utoc + .ucas), read only"""

    def __init__(self, utoc):
        self.path = utoc
        d = open(utoc, "rb").read()
        if d[:16] != b"-==--==--==--==-":
            raise ValueError(f"{utoc}: not an IoStore toc")
        ver = d[16]
        hsz, n, nblk, _, nmeth, mlen, self.block, _, parts = struct.unpack_from("<9I", d, 20)
        self.flags = d[80]
        seeds, = struct.unpack_from("<I", d, 84)
        self.partition, = struct.unpack_from("<Q", d, 88)
        nohash, = struct.unpack_from("<I", d, 96)
        o = hsz
        self.ids = d[o:o + 12 * n]
        o += 12 * n
        self.offlen = d[o:o + 10 * n]
        o += 10 * n
        if ver >= 4:
            o += 4 * seeds
        if ver >= 5:
            o += 4 * nohash
        self.blocks = d[o:o + 12 * nblk]
        o += 12 * nblk
        self.methods = [d[o + i * mlen:o + (i + 1) * mlen].rstrip(b"\0").decode().lower() for i in range(nmeth)]
        self.ucas = [utoc[:-5] + ".ucas"] + [f"{utoc[:-5]}_s{i}.ucas" for i in range(1, parts)]

    def find(self, package_id, chunk_type=1):
        """index of a package's chunk (1 = export data), or None"""
        want = struct.pack("<Q", package_id)
        k = self.ids.find(want)
        while k >= 0:
            if k % 12 == 0 and self.ids[k + 11] == chunk_type and self.ids[k + 8:k + 10] == b"\0\0":
                return k // 12
            k = self.ids.find(want, k + 1)
        return None

    def read(self, i):
        e = self.offlen[10 * i:10 * i + 10]
        off, size = int.from_bytes(e[:5], "big"), int.from_bytes(e[5:], "big")
        out = bytearray()
        for b in range(off // self.block, (off + size - 1) // self.block + 1):
            r = self.blocks[12 * b:12 * b + 12]
            at, cs, us, m = int.from_bytes(r[:5], "little"), int.from_bytes(r[5:8], "little"), \
                int.from_bytes(r[8:11], "little"), r[11]
            part, at = (at // self.partition, at % self.partition) if self.partition else (0, at)
            with open(self.ucas[part], "rb") as f:
                f.seek(at)
                raw = f.read((cs + 15) & ~15 if self.flags & 2 else cs)
            if self.flags & 2:
                d = Cipher(algorithms.AES(AES_KEY), modes.ECB()).decryptor()
                raw = d.update(raw) + d.finalize()
            raw = raw[:cs]
            if m == 0:
                out += raw[:us]
            elif self.methods[m - 1] == "oodle":
                out += oodle_decompress(raw, us)
            else:
                raise ValueError(f"{self.path}: compression {self.methods[m - 1]}")
        start = off - (off // self.block) * self.block
        return bytes(out[start:start + size])


def _name_batch(b, o):
    n, = struct.unpack_from("<I", b, o)
    o += 4
    if n == 0:
        return [], o
    o += 4 + 8 + 8 * n
    lens = b[o:o + 2 * n]
    o += 2 * n
    out = []
    for i in range(n):
        ln = ((lens[2 * i] & 0x7F) << 8) | lens[2 * i + 1]
        if lens[2 * i] & 0x80:
            out.append(b[o:o + 2 * ln].decode("utf-16-le"))
            o += 2 * ln
        else:
            out.append(b[o:o + ln].decode("latin1"))
            o += ln
    return out, o


def zen_package(b):
    """a zen package (UE 5.3, unversioned) -> names, import map, export map rows, export data"""
    hv, hsz = struct.unpack_from("<II", b, 0)
    if hv:
        raise ValueError("versioned zen package")
    imap, emap, ebe = struct.unpack_from("<iii", b, 28)
    names, _ = _name_batch(b, 52)
    imports = list(struct.unpack_from(f"<{(emap - imap) // 8}Q", b, imap))
    exports = []
    for o in range(emap, ebe, 72):
        soff, ssize = struct.unpack_from("<QQ", b, o)
        exports.append(dict(offset=soff, size=ssize, rest=b[o + 16:o + 72]))
    # export data follows the header, the package ends with the same 4 byte tag as a .uexp
    return dict(names=names, imports=imports, exports=exports, header_size=hsz, data=b[hsz:len(b) - 4], tail=b[-4:])


def game_containers(paks):
    """patch containers newest first, then the base containers"""
    def ver(p):
        m = re.search(r"Patch_-Windows_([\d.]+)_P\.utoc$", p)
        return tuple(int(x) for x in m.group(1).split("."))
    patches = sorted(glob.glob(os.path.join(paks, "Patch_-Windows_*_P.utoc")), key=ver, reverse=True)
    return patches + sorted(glob.glob(os.path.join(paks, "pakchunk*-Windows.utoc")))


def game_path(asset):
    """Marvel/Content/X -> /Game/X"""
    return "/Game/" + asset[len("Marvel/Content/"):]


def newest_zen(asset, paks, containers=None):
    """-> (zen package bytes, container name) of the copy the game loads"""
    pid = cityhash.pkg_id(game_path(asset))
    for utoc in containers or game_containers(paks):
        c = Container(utoc)
        i = c.find(pid)
        if i is not None:
            return c.read(i), os.path.basename(utoc)[:-5]
    raise SystemExit(f"{asset} isn't in the game")


def _bulk_start_at(uasset, total):
    hits = [k for k in range(0, min(len(uasset), 4096) - 8) if struct.unpack_from("<q", uasset, k)[0] == total - 4]
    if len(hits) != 1:
        raise SystemExit(f"BulkDataStartOffset not found in the legacy header ({hits})")
    return hits[0]


def _legacy_names(uasset):
    """name map of a legacy .uasset (retoc to-legacy layout)"""
    o = 24
    ncv, = struct.unpack_from("<i", uasset, o)
    o += 4 + 20 * ncv + 4
    ln, = struct.unpack_from("<i", uasset, o)
    o += 4 + (ln if ln >= 0 else -2 * ln) + 4
    count, at = struct.unpack_from("<ii", uasset, o)
    out = []
    for _ in range(count):
        ln, = struct.unpack_from("<i", uasset, at)
        at += 4
        if ln >= 0:
            out.append(uasset[at:at + ln - 1].decode("latin1"))
            at += ln
        else:
            out.append(uasset[at:at - 2 * ln - 2].decode("utf-16-le"))
            at += -2 * ln
        at += 4
    return out, o


def _legacy_exports(uasset, names_at):
    """(export table offset, entry size, count) of a legacy .uasset"""
    o = names_at + 8 + 8 + 8
    count, off, icount, ioff, depends = struct.unpack_from("<iiiii", uasset, o)
    return off, (depends - off) // count, count


def current_legacy(asset, paks, work):
    """the copy of a single-export package the game loads now, as a legacy uasset/uexp pair.
    -> (uasset bytearray, uexp bytearray, names, container)"""
    newest, cont = newest_zen(asset, paks)
    src = os.path.join(work, "base")
    shutil.rmtree(src, ignore_errors=True)
    subprocess.run([RETOC, "unpack", os.path.join(paks, BASE + ".utoc"), "--filter", f"../../../{asset}.uasset",
                    "--output", src, "--game-paks-dir", paks], check=True, stdout=subprocess.DEVNULL)
    f = os.path.join(src, *asset.split("/"))
    if not os.path.exists(f + ".uexp"):
        raise SystemExit(f"{asset} didn't come out of {BASE}")
    uasset = bytearray(open(f + ".uasset", "rb").read())
    uexp = bytearray(open(f + ".uexp", "rb").read())
    new = zen_package(newest)
    if cont == BASE:
        base = new
    else:
        base = zen_package(newest_zen(asset, paks, [os.path.join(paks, BASE + ".utoc")])[0])
    names, names_at = _legacy_names(uasset)
    eoff, esz, ecount = _legacy_exports(uasset, names_at)
    # retoc keeps the export bytes and the name order, it only adds names at the end
    if len(base["exports"]) != 1 or ecount != 1 or bytes(uexp[:-4]) != base["data"] or uexp[-4:] != TAG \
            or base["exports"][0]["size"] != len(base["data"]):
        raise SystemExit(f"{asset}: the legacy copy doesn't match the game's base copy, can't graft")
    if names[:len(base["names"])] != base["names"]:
        raise SystemExit(f"{asset}: name order changed in the legacy copy, can't graft")
    if cont != BASE:
        same = (new["names"] == base["names"] and new["imports"] == base["imports"]
                and [e["rest"] for e in new["exports"]] == [e["rest"] for e in base["exports"]])
        if not same or len(new["data"]) != new["exports"][0]["size"] or new["tail"] != TAG:
            raise SystemExit(f"{asset}: the {cont} copy has different header tables than the base copy, "
                             "the patch data can't go into the base header safely")
        at = _bulk_start_at(uasset, len(uasset) + len(uexp))
        uexp = bytearray(new["data"] + TAG)
        struct.pack_into("<q", uasset, eoff + 28, len(new["data"]))
        struct.pack_into("<q", uasset, at, len(uasset) + len(uexp) - 4)
    return uasset, uexp, new["names"], cont


def find_vector(uexp, names, param):
    """uexp offset of an MI's VectorParameterValues entry value (linear colour, 4 floats).
    Entry layout: struct header 00 07, ParameterInfo header 00 07, Name (index, number), Association 2 (global),
    Index -1, then the value."""
    if param not in names:
        raise SystemExit(f"{param} isn't in the package")
    end = uexp.find(b"FMaterialShaderMapContent")   # the properties come before the shader map
    key = b"\x00\x07\x00\x07" + struct.pack("<II", names.index(param), 0) + b"\x02\xff\xff\xff\xff"
    hits = [m.start() + len(key) for m in re.finditer(re.escape(key), bytes(uexp[:end if end > 0 else len(uexp)]))]
    if len(hits) != 1:
        raise SystemExit(f"{param}: found {len(hits)} vector entries, expected 1")
    return hits[0]


def edit(uexp, names, param, old, new):
    at = find_vector(uexp, names, param)
    cur = struct.unpack_from("<4f", uexp, at)
    if not np.allclose(cur, old, atol=1e-4):
        raise SystemExit(f"{param}: expected {old}, found {cur} (a game patch?)")
    struct.pack_into("<4f", uexp, at, *new)
    return at


def build(raw, paks=DEFAULT_PAKS, work=WORK, edits=EDITS):
    """write the recoloured MIs into the raw folder (legacy layout, packed later with the skin).
    -> [(asset, container it came from, [(param, old, new)])]"""
    out = []
    for asset, params in edits.items():
        ua, ue, names, cont = current_legacy(asset, paks, os.path.join(work, os.path.basename(asset)))
        done = []
        for param, old in params.items():
            new = to_blurple(old)
            edit(ue, names, param, old, new)
            done.append((param, old, new))
        d = os.path.join(raw, *asset.split("/"))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        open(d + ".uasset", "wb").write(ua)
        open(d + ".uexp", "wb").write(ue)
        out.append((asset, cont, done))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS)
    ap.add_argument("--out", default=os.path.join(WORK, "raw"), help="raw folder to write the edited MIs into")
    args = ap.parse_args()
    for asset, cont, done in build(args.out, args.game):
        print(f"{os.path.basename(asset)} (from {cont}):")
        for param, old, new in done:
            print(f"  {param}: {tuple(round(x, 4) for x in old)} -> {tuple(round(x, 4) for x in new)}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
