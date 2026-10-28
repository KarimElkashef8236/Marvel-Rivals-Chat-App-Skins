"""Get a hero mesh and its colour textures out of the game for the preview renderer (read only).

    import game
    prefix = game.unpack_mesh("Marvel/Content/Marvel/Characters/1037/1037001/Meshes/SK_1037_1037001", out)
    mesh = skm.load(prefix, newest=game.newest_export(asset))   # newest= is optional
    game.hero_textures(mesh, tex_dir, out)      # writes <TextureName>.png + slots.json into tex_dir
    img = game.decode(texture_prefix)            # largest mip the game ships, uint8 (H, W, C)

retoc unpacks the base containers (pakchunk*-Windows) into legacy files. It can't unpack the patch containers,
so newest_export() reads the newest copy of a package straight from whichever container has it (patches
first), which skm.load(newest=...) uses for the export data when it matches.

slots.json, per material slot: {"d": front colour texture, "back": colour texture of back faces (two sided
materials like Magneto's cape: Equip_03 outside, Equip_05 inside), "mask": opacity mask for alpha tested hair
cards, "hidden": true for slots without a colour texture (eye highlight shells and such), "material": MI}.
Edit it by hand if a slot needs something else, render.py reads it as it is.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bc1          # noqa: E402
import bc5          # noqa: E402
import bc7          # noqa: E402
import skm          # noqa: E402
import ue_texture   # noqa: E402
from paths import DEFAULT_PAKS   # noqa: E402

ROOT = os.path.dirname(SCRIPTS)
RETOC = os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")
BASE_CONTAINERS = ("pakchunkCharacter-Windows", "pakchunk0-Windows", "pakchunkCommon-Windows",
                   "pakchunkHQ-Windows")


def game_path(asset):
    """Marvel/Content/X -> /Game/X"""
    return "/Game/" + asset[len("Marvel/Content/"):] if asset.startswith("Marvel/Content/") else asset


def asset_path(game):
    """/Game/X -> Marvel/Content/X"""
    return "Marvel/Content/" + game[len("/Game/"):] if game.startswith("/Game/") else game


def _containers(paks):
    import magneto_mats
    return magneto_mats.game_containers(paks)


_cache = {}


def _open(utoc):
    import magneto_mats
    if utoc not in _cache:
        _cache[utoc] = magneto_mats.Container(utoc)
    return _cache[utoc]


def where(asset, paks=DEFAULT_PAKS):
    """containers that have the package, newest first (patches, then base containers)"""
    import cityhash
    pid = cityhash.pkg_id(game_path(asset))
    return [os.path.basename(u)[:-5] for u in _containers(paks) if _open(u).find(pid) is not None]


def newest_export(asset, paks=DEFAULT_PAKS):
    """(zen package bytes, container) of the copy the game loads, when that copy is in a patch container and
    has no bulk data of its own there (the .ubulk from the base container still applies). None otherwise."""
    import cityhash
    pid = cityhash.pkg_id(game_path(asset))
    for utoc in _containers(paks):
        c = _open(utoc)
        i = c.find(pid)
        if i is None:
            continue
        name = os.path.basename(utoc)[:-5]
        if not name.startswith("Patch_"):
            return None
        if c.find(pid, 2) is not None or c.find(pid, 3) is not None:
            print(f"  note: {name} has its own bulk data for {os.path.basename(asset)}, using the base copy")
            return None
        return c.read(i), name
    return None


def unpack(assets, out, paks=DEFAULT_PAKS, force=False):
    """retoc unpack packages (Marvel/Content/... without extension) from the base container that has them.
    -> {asset: legacy prefix}. Packages already unpacked in out are kept unless force."""
    todo, got = {}, {}
    for a in assets:
        a = asset_path(a)
        prefix = os.path.join(out, *a.split("/"))
        got[a] = prefix
        if os.path.exists(prefix + ".uasset") and not force:
            continue
        conts = [c for c in where(a, paks) if not c.startswith("Patch_")]
        if not conts:
            raise SystemExit(f"{a} isn't in a base container (retoc can't unpack patch containers)")
        todo.setdefault(conts[0], []).append(a)
    for cont, items in todo.items():
        filters = []
        for a in items:
            filters += ["--filter", f"../../../{a}.uasset"]
        subprocess.run([RETOC, "unpack", os.path.join(paks, cont + ".utoc"), *filters, "--output", out,
                        "--game-paks-dir", paks], check=True, stdout=subprocess.DEVNULL)
        for a in items:
            if not os.path.exists(got[a] + ".uasset"):
                raise SystemExit(f"{a} didn't come out of {cont}")
    return got


def unpack_mesh(asset, out, paks=DEFAULT_PAKS):
    return unpack([asset], out, paks)[asset_path(asset)]


# ---------------------------------------------------------------- textures
def _bc3(data, w, h):
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    blk = np.frombuffer(data, np.uint8, bw * bh * 16).reshape(-1, 16)
    alpha = np.clip(np.rint(bc5._bc4_decode(blk[:, :8])), 0, 255).astype(np.uint8)
    col = blk[:, 8:].copy()
    # BC3 colour blocks always use 4 colour mode: make c0 > c1 where it isn't (swap endpoints + remap indices)
    c0 = col[:, 0].astype(np.int32) | (col[:, 1].astype(np.int32) << 8)
    c1 = col[:, 2].astype(np.int32) | (col[:, 3].astype(np.int32) << 8)
    rgb = bc1.decode(col.tobytes(), bw * 4, bh * 4)
    bad = c0 <= c1
    if bad.any():
        e0, e1 = bc1._565(c0[bad]), bc1._565(c1[bad])
        pal = np.stack([e0, e1, (2 * e0 + e1) // 3, (e0 + 2 * e1) // 3], 1).astype(np.uint8)
        idx = col[bad, 4:8].copy().view("<u4")[:, 0].astype(np.int64)
        ii = (idx[:, None] >> (np.arange(16) * 2)) & 3
        px = pal[np.arange(len(pal))[:, None], ii].reshape(-1, 4, 4, 3)
        ys, xs = np.divmod(np.nonzero(bad)[0], bw)
        for k in range(len(ys)):
            rgb[ys[k] * 4:ys[k] * 4 + 4, xs[k] * 4:xs[k] * 4 + 4] = px[k]
    a = alpha.reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(bh * 4, bw * 4)
    return np.dstack([rgb, a])[:h, :w]


def decode_mip(pf, data, w, h):
    if pf == "PF_DXT1":
        return bc1.decode(data, w, h)
    if pf == "PF_DXT5":
        return _bc3(data, w, h)
    if pf == "PF_BC5":
        return bc5.decode(data, w, h)
    if pf == "PF_BC7":
        return bc7.decode(data, w, h)
    if pf == "PF_B8G8R8A8":
        return np.frombuffer(data, np.uint8, w * h * 4).reshape(h, w, 4)[..., [2, 1, 0, 3]]
    if pf == "PF_G8":
        return np.frombuffer(data, np.uint8, w * h).reshape(h, w)
    raise ValueError(f"can't decode {pf}")


def decode(prefix, max_size=None):
    """largest mip the unpacked files have (the optional 2048 mips aren't in any game container)"""
    pf, table = ue_texture.mips(prefix)
    for m in table:
        if m["where"] == "uptnl" and not os.path.exists(prefix + ".uptnl"):
            continue
        if max_size and max(m["w"], m["h"]) > max_size:
            continue
        return decode_mip(pf, ue_texture.read_mip(prefix, m), m["w"], m["h"])
    raise ValueError(f"{prefix}: no mip to decode")


def material_textures(prefix):
    """textures and parent material an MI package imports -> ([(name, /Game path)], [(parent, /Game path)])"""
    pkg = skm.Package(prefix)
    tex, parents = [], []
    for i, imp in enumerate(pkg.imports):
        if imp["cls"].startswith("Texture"):
            tex.append(pkg.import_path(-(i + 1)))
        elif imp["cls"] in ("Material", "MaterialInstanceConstant") and not imp["name"].startswith("Default__"):
            parents.append(pkg.import_path(-(i + 1)))
    return tex, parents


def _tag(name):
    """T_1037001_Equip_03_D -> ('1037001', 'Equip_03')"""
    m = re.match(r"(?:T|MI|M)_(?:EQPT_)?(\d+)_(.+?)(?:_(?:D|S|N|M|ORM|Ao|ID|E))?$", name, re.I)
    return (m.group(1), m.group(2)) if m else (None, name)


def slot_textures(material, textures):
    """pick the colour (front, back) and mask textures of one slot from what its MI imports"""
    cid, part = _tag(material)
    ds = [t for t in textures if re.search(r"_D$", t[0], re.I)]
    same = [t for t in ds if _tag(t[0])[0] == cid]
    front = next((t for t in same if _tag(t[0])[1].lower() == part.lower()), None) \
        or (same[0] if same else (ds[0] if ds else None))
    back = None
    if front is not None and front in same:
        others = [t for t in same if t != front]
        back = others[0] if others else None
    mask = None
    if re.search(r"hair|lash|brow|beard|fur", material, re.I):
        mask = next((t for t in textures if re.search(r"_M$", t[0], re.I) and _tag(t[0])[0] == cid), None)
    return front, back, mask


def hero_textures(mesh, tex_dir, out, paks=DEFAULT_PAKS, max_size=1024):
    """unpack the MIs and colour textures of every slot of mesh, decode them to tex_dir/<name>.png and
    write tex_dir/slots.json. -> the slots dict"""
    from PIL import Image
    os.makedirs(tex_dir, exist_ok=True)
    used = set(np.unique(mesh.tri_slot).tolist())
    mis = [asset_path(s["path"]) for i, s in enumerate(mesh.slots) if s["path"] and i in used]
    prefixes = unpack(mis, out, paks)
    slots, wanted = {}, {}
    for i, s in enumerate(mesh.slots):
        if not s["path"] or i not in used:     # no material, or LOD0 doesn't draw with this slot
            slots[s["name"]] = dict(material=s["material"], hidden=True)
            continue
        tex, parents = material_textures(prefixes[asset_path(s["path"])])
        front, back, mask = slot_textures(s["material"], tex)
        if front is None and parents and parents[0][0].startswith("MI_"):   # one level up for bare MIs
            p = unpack([parents[0][1]], out, paks)[asset_path(parents[0][1])]
            front, back, mask = slot_textures(s["material"], material_textures(p)[0])
        entry = dict(material=s["material"])
        for key, t in (("d", front), ("back", back), ("mask", mask)):
            if t is not None:
                entry[key] = t[0]
                wanted[t[0]] = asset_path(t[1])
        if front is None:
            entry["hidden"] = True
        slots[s["name"]] = entry
    texp = unpack(list(wanted.values()), out, paks)
    for name, a in wanted.items():
        img = decode(texp[a], max_size)
        Image.fromarray(img).save(os.path.join(tex_dir, name + ".png"))
    with open(os.path.join(tex_dir, "slots.json"), "w") as fh:
        json.dump(slots, fh, indent=1)
    return slots


def main():
    import argparse
    ap = argparse.ArgumentParser(description="unpack a hero mesh and decode its colour textures")
    ap.add_argument("mesh", help="Marvel/Content/.../SK_xxx (no extension)")
    ap.add_argument("--out", required=True, help="folder for the unpacked legacy files")
    ap.add_argument("--textures", required=True, help="folder for the decoded PNGs + slots.json")
    ap.add_argument("--game", default=DEFAULT_PAKS)
    args = ap.parse_args()
    prefix = unpack_mesh(args.mesh, args.out, args.game)
    mesh = skm.load(prefix)
    print(mesh)
    for k, v in hero_textures(mesh, args.textures, args.out, args.game).items():
        print(f"  {k}: {v}")
    print("containers with the mesh:", ", ".join(where(args.mesh, args.game)))


if __name__ == "__main__":
    main()
