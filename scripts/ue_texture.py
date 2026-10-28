"""Read and rewrite the mip pixels of a cooked Texture2D (legacy uasset/uexp/ubulk from retoc unpack).

Only the pixel payloads change, every header byte stays as the game cooked it, so the texture
keeps the game's current property layout and size info.
"""
import os
import struct

INLINE, SEPARATE, OPTIONAL = 0x40, 0x100, 0x800


def _data_resources(uasset):
    # UE5.2+ data resource table sits at the end of the legacy header: version 1, count, 44 byte entries
    for n in range(1, 64):
        off = len(uasset) - 8 - 44 * n
        if off < 0:
            break
        ver, cnt = struct.unpack_from("<Ii", uasset, off)
        if ver == 1 and cnt == n:
            return [dict(zip(("flags", "offset", "dup", "size", "raw", "outer", "lbf"),
                             struct.unpack_from("<IqqqqiI", uasset, off + 8 + 44 * k))) for k in range(n)]
    raise ValueError("no data resource table")


def mips(prefix):
    """-> (pixel format, [dict(index, w, h, where, offset, size)]), where is 'uexp', 'ubulk' or 'uptnl'"""
    uasset = open(prefix + ".uasset", "rb").read()
    uexp = open(prefix + ".uexp", "rb").read()
    res = _data_resources(uasset)
    for pf in (b"PF_DXT1", b"PF_DXT5", b"PF_BC5", b"PF_BC7", b"PF_B8G8R8A8", b"PF_G8"):
        k = uexp.find(struct.pack("<i", len(pf) + 1) + pf + b"\0")
        if k >= 0:
            break
    else:
        raise ValueError(f"{prefix}: pixel format not found")
    packed = struct.unpack_from("<I", uexp, k - 4)[0]
    p = k + 4 + len(pf) + 1 + (8 if packed & 0x80000000 else 0)
    first, count = struct.unpack_from("<ii", uexp, p)
    p += 8
    out = []
    for i in range(count):
        r = res[struct.unpack_from("<i", uexp, p)[0]]
        p += 4
        if r["lbf"] & OPTIONAL:
            where, off = "uptnl", r["offset"]
        elif r["lbf"] & SEPARATE:
            where, off = "ubulk", r["offset"]
        else:
            where, off = "uexp", p
            p += r["size"]
        w, h, _ = struct.unpack_from("<iii", uexp, p)
        p += 12
        out.append(dict(index=i, w=w, h=h, where=where, offset=off, size=r["size"]))
    return pf.decode(), out


def read_mip(prefix, m):
    with open(f"{prefix}.{m['where']}", "rb") as fh:
        fh.seek(m["offset"])
        return fh.read(m["size"])


def write(src_prefix, dst_prefix, payloads):
    """copy a texture to dst_prefix, replacing mip payloads {mip index: bytes} (same sizes)"""
    _, table = mips(src_prefix)
    os.makedirs(os.path.dirname(dst_prefix), exist_ok=True)
    files = {ext: bytearray(open(f"{src_prefix}.{ext}", "rb").read())
             for ext in ("uasset", "uexp", "ubulk") if os.path.exists(f"{src_prefix}.{ext}")}
    for m in table:
        if m["index"] not in payloads:
            continue
        data = payloads[m["index"]]
        if len(data) != m["size"] or m["where"] == "uptnl":
            raise ValueError(f"mip {m['index']}: can't write {len(data)} bytes into {m['where']} ({m['size']})")
        files[m["where"]][m["offset"]:m["offset"] + len(data)] = data
    for ext, b in files.items():
        open(f"{dst_prefix}.{ext}", "wb").write(b)
