"""Check that Discord Magneto still looks Discord from far away.

Magneto's default mesh (SK_1037_1037001) has 4 LODs. LOD2 (used below 12.5% screen size) and LOD3 (below 10%)
are reduced copies that still draw with the normal materials (MI_1037001_Body, Equip_01..04, Head, Eyes_01,
Hair_01/02), so the recoloured T_1037001_* textures cover him at any distance. The merged material
MI_1037001_LOD2_MAT and its atlas (Textures/Merge_Texture/T_1037001_LOD2_*) are only listed as material slot 12:
no LOD section and no LODMaterialMap uses that slot (LOD3's map is all -1, keep the section's own slot), and no UV
set of any LOD lands on the atlas. So the atlas never shows and the skin leaves it alone. (Other Magneto costumes
like 1037500 do draw their LOD2 with a merged atlas.)

A game patch could re-cook the mesh, so check() compares the mesh package with the one this was worked out on
and lists which material slots each LOD's sections use now.

    python scripts/magneto_lod.py [--game <Paks dir>]
"""
import argparse
import hashlib
import re
import struct

import magneto_mats
from paths import DEFAULT_PAKS

MESH = "Marvel/Content/Marvel/Characters/1037/1037001/Meshes/SK_1037_1037001"
SHA1 = "7435f914ae5149b11e0b67f5494f61b05cc6ee4f"   # zen package in Patch_-Windows_1.1.3939753_P, game 1.1.3962284
MERGED_SLOT = 12
LOD_SLOTS = [list(range(12)), list(range(12)), [0, 1, 2, 3, 4, 7, 9, 10, 11], [0, 1, 2, 3, 4, 7, 9, 10, 11]]


def _section(d, p):
    """one FSkelMeshRenderSection of a cooked LOD -> (material index, base index, triangles), end"""
    mat, base, ntri = struct.unpack_from("<HII", d, p + 2)
    p += 2 + 14 + 1 + 16
    ncloth = struct.unpack_from("<I", d, p - 4)[0]
    if ncloth:
        raise ValueError("cloth mapping")
    nb, = struct.unpack_from("<I", d, p)
    p += 4 + 2 * nb + 8 + 2 + 20
    nd, = struct.unpack_from("<I", d, p)
    p += 4 + 4 * nd
    ni, = struct.unpack_from("<I", d, p)
    p += 4 + 8 * ni + 4
    return (mat, base, ntri), p


def lod_sections(d):
    """material slot of every render section, per LOD, found by scanning the mesh export data"""
    lods = []
    for m in re.finditer(re.escape(b"\x01\x00"), d):
        p = m.start() - 4
        if p < 0 or struct.unpack_from("<I", d, p + 8)[0] != 0:   # count, strip flags, slot, first index 0
            continue
        n, = struct.unpack_from("<I", d, p)
        if not 0 < n < 64:
            continue
        try:
            q, secs = p + 4, []
            for _ in range(n):
                s, q = _section(d, q)
                if secs and s[1] != secs[-1][1] + 3 * secs[-1][2]:
                    raise ValueError("not a chain")
                secs.append(s)
        except (ValueError, struct.error):
            continue
        lods.append([s[0] for s in secs])
    return lods


def check(paks=DEFAULT_PAKS):
    """-> (ok, message). ok means the far-away LOD still draws with the recoloured textures."""
    b, cont = magneto_mats.newest_zen(MESH, paks)
    if hashlib.sha1(b).hexdigest() == SHA1:
        return True, "Magneto's mesh is unchanged, his far LOD draws with the normal (recoloured) textures"
    lods = lod_sections(magneto_mats.zen_package(b)["data"])
    merged = any(MERGED_SLOT in s for s in lods)
    return False, (f"SK_1037_1037001 changed in {cont}. Section slots per LOD now: {lods}"
                   f"{' (one uses the merged slot!)' if merged else ''}. If a LOD draws with MI_1037001_LOD2_MAT "
                   "now, he turns vanilla from far away until the T_1037001_LOD2_* atlas gets recoloured too.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS)
    args = ap.parse_args()
    ok, msg = check(args.game)
    print(("ok: " if ok else "check this: ") + msg)


if __name__ == "__main__":
    main()
