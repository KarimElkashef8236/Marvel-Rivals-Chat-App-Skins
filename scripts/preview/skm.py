"""Read the LOD0 geometry of a cooked SkeletalMesh (or StaticMesh) from retoc-unpacked legacy files.

    import skm
    mesh = skm.load(r"work\\...\\Meshes\\SK_1037_1037001")       # path without .uasset
    mesh.positions   (V, 3) float32, Unreal units (cm), Z up. Heroes face +Y, their right hand is at -X
    mesh.normals     (V, 3) float32, unit length
    mesh.uvs         (V, n, 2) float32, every UV channel (channel 0 is the one the textures use)
    mesh.triangles   (T, 3) int64, vertex indices
    mesh.tri_slot    (T,) int64, material slot of every triangle
    mesh.slots       [dict(name, material, path)] per material slot: slot name, material instance name and
                     its package path (/Game/...), so the textures can be looked up
    mesh.sections    [dict(slot, first, triangles, base_vertex, vertices)] render sections of LOD0

Layout (UE 5.3, the way Marvel Rivals cooks it):
- the export data is the unversioned properties, then the native part: strip flags, imported bounds,
  the material array (FSkeletalMaterial: material, slot name, bSerializeImportedMaterialSlotName (+ name),
  UV channel data, plus a TArray<FName> of material tags the game added), the ref skeleton, then the render data.
- every LOD: strip flags, bIsLODCookedOut, bInlined, RequiredBones, RenderSections, ActiveBoneIndices,
  BuffersSize, then the vertex and index buffers. A streamed LOD (LOD0 usually) keeps them in the .ubulk
  (the export data has the index of its entry in the data resource table at the end of the .uasset), an inlined
  LOD has them right there in the .uexp.
- the buffers: FStripDataFlags, index buffer (index size 2 or 4, then element size, count, data), position
  buffer (stride, count, element size, count, float3), static mesh vertex buffer (strip flags, UV channels,
  count, full precision UVs, high precision tangents, tangents (TangentX + TangentZ as signed bytes or
  shorts, TangentZ is the normal), UVs (vertex major, float2 or half2)), then skin weights and the rest,
  which a preview doesn't need.

The material array and the render sections are found by their shape, not by skipping the properties (they
have no schema here), and every count is cross checked (index count = 3 x triangles, vertex counts of the
position and tangent buffers, index range of every section), so a layout change stops with an error instead
of returning garbage.

Static meshes: the material array (FStaticMaterial, no bSerializeImportedMaterialSlotName) sits at the end
of the export, LOD0 is FStaticMeshLODResources: sections (material, first index, triangles, min and max
vertex, 5 bools), MaxDeviation, bIsLODCookedOut, bInlined, then strip flags, position buffer, static mesh
vertex buffer, colour buffer and the index buffer (b32Bit, then the indices as bytes).
"""
import os
import re
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

SEPARATE, OPTIONAL = 0x100, 0x800


# ---------------------------------------------------------------- legacy package
def _fstring(b, o):
    n, = struct.unpack_from("<i", b, o)
    o += 4
    if n >= 0:
        return b[o:o + n - 1].decode("latin1"), o + n
    return b[o:o - 2 * n - 2].decode("utf-16-le"), o - 2 * n


class Package:
    """a legacy .uasset/.uexp(/.ubulk) as retoc writes it (UE 5.3, unversioned)"""

    def __init__(self, prefix):
        self.prefix = prefix
        self.uasset = open(prefix + ".uasset", "rb").read()
        self.uexp = open(prefix + ".uexp", "rb").read()
        ua = self.uasset
        ncv, = struct.unpack_from("<i", ua, 24)
        o = 28 + 20 * ncv + 4
        self.package_name, o = _fstring(ua, o)
        o += 4
        ncount, noff = struct.unpack_from("<ii", ua, o)
        ecount, eoff, icount, ioff, dep = struct.unpack_from("<iiiii", ua, o + 24)
        self.names, at = [], noff
        for _ in range(ncount):
            s, at = _fstring(ua, at)
            self.names.append(s)
            at += 4
        isz = (eoff - ioff) // icount if icount else 0
        self.imports = []
        for k in range(icount):
            _, _, cn, cnn, outer, on, onn = struct.unpack_from("<IIIIiII", ua, ioff + isz * k)
            self.imports.append(dict(cls=self.name(cn, cnn), outer=outer, name=self.name(on, onn)))
        esz = (dep - eoff) // ecount
        self.exports = []
        for k in range(ecount):
            ci, _, _, _, on, onn, _, size, off = struct.unpack_from("<iiiiIIIqq", ua, eoff + esz * k)
            self.exports.append(dict(cls=ci, name=self.name(on, onn), size=size, offset=off - len(ua)))
        self.resources = self._data_resources()

    def name(self, index, number=0):
        n = self.names[index]
        return f"{n}_{number - 1}" if number else n

    def import_path(self, index):
        """FPackageIndex of an import (negative) -> (object name, package path)"""
        imp = self.imports[-index - 1]
        outer = imp["outer"]
        while outer < 0 and self.imports[-outer - 1]["outer"] < 0:
            outer = self.imports[-outer - 1]["outer"]
        return imp["name"], (self.imports[-outer - 1]["name"] if outer < 0 else "")

    def class_name(self, index):
        if index < 0:
            return self.imports[-index - 1]["name"]
        return self.exports[index - 1]["name"] if index > 0 else ""

    def export_data(self, export):
        return self.uexp[export["offset"]:export["offset"] + export["size"]]

    def _data_resources(self):
        """UE 5.2+ data resource table at the end of the header: version 1, count, 44 byte entries"""
        ua = self.uasset
        for n in range(1, 256):
            off = len(ua) - 8 - 44 * n
            if off < 0:
                break
            ver, cnt = struct.unpack_from("<Ii", ua, off)
            if ver == 1 and cnt == n:
                return [dict(zip(("flags", "offset", "dup", "size", "raw", "outer", "lbf"),
                                 struct.unpack_from("<IqqqqiI", ua, off + 8 + 44 * k))) for k in range(n)]
        return []

    def bulk(self, index):
        """payload of a data resource that lives in a separate file (.ubulk or .uptnl)"""
        r = self.resources[index]
        if r["lbf"] & OPTIONAL:
            ext = "uptnl"
        elif r["lbf"] & SEPARATE:
            ext = "ubulk"
        else:
            raise ValueError(f"data resource {index} isn't in a separate file (flags {r['lbf']:#x})")
        path = f"{self.prefix}.{ext}"
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} (data resource {index}) is missing")
        with open(path, "rb") as fh:
            fh.seek(r["offset"])
            data = fh.read(r["size"])
        if len(data) != r["size"]:
            raise ValueError(f"{path}: short read for data resource {index}")
        return data


# ---------------------------------------------------------------- reading helpers
class Reader:
    def __init__(self, b, o=0):
        self.b, self.o = b, o

    def u8(self):
        v = self.b[self.o]
        self.o += 1
        return v

    def u16(self):
        v, = struct.unpack_from("<H", self.b, self.o)
        self.o += 2
        return v

    def u32(self):
        v, = struct.unpack_from("<I", self.b, self.o)
        self.o += 4
        return v

    def i32(self):
        v, = struct.unpack_from("<i", self.b, self.o)
        self.o += 4
        return v

    def f32(self):
        v, = struct.unpack_from("<f", self.b, self.o)
        self.o += 4
        return v

    def bool32(self):
        v = self.u32()
        if v > 1:
            raise ValueError(f"bool32 {v} at {self.o - 4}")
        return bool(v)

    def skip(self, n):
        self.o += n
        if self.o > len(self.b):
            raise ValueError("read past the end")

    def array(self, item_size, limit=1 << 28):
        """TArray of fixed size items -> (count, bytes)"""
        n = self.u32()
        if n > limit:
            raise ValueError(f"array count {n}")
        d = self.b[self.o:self.o + n * item_size]
        self.skip(n * item_size)
        return n, d

    def bulk_array(self, dtype, expect_size=None):
        """TResourceArray BulkSerialize: element size, count, data"""
        es, n = self.i32(), self.i32()
        if es <= 0 or n < 0 or (expect_size and es != expect_size):
            raise ValueError(f"bulk array: element size {es}, count {n}")
        raw = self.b[self.o:self.o + es * n]
        self.skip(es * n)
        if dtype is None:
            return es, n, raw
        return es, n, np.frombuffer(raw, dtype)


# ---------------------------------------------------------------- material array
def find_materials(pkg, d, static=False):
    """the material array (FSkeletalMaterial, or FStaticMaterial with static=True, which has no
    bSerializeImportedMaterialSlotName) -> (offset after it, [slot dicts])"""
    mat_imports = {-(i + 1) for i, imp in enumerate(pkg.imports)
                   if "Material" in imp["cls"] or (imp["cls"] == "Object" and "Material" in imp["name"])}
    nn = len(pkg.names)

    def entry(r):
        mi = r.i32()
        if mi != 0 and mi not in mat_imports:
            raise ValueError("not a material")
        ni, nnum = r.u32(), r.u32()
        if ni >= nn:
            raise ValueError("bad slot name")
        if not static and r.bool32():
            if r.u32() >= nn:
                raise ValueError("bad imported slot name")
            r.u32()
        r.bool32()      # UV channel data: initialized
        r.bool32()      # override densities
        r.skip(16)      # 4 UV densities
        start = r.o
        try:            # the game's material tags: TArray<FName>
            cnt = r.u32()
            if cnt > 32:
                raise ValueError
            for _ in range(cnt):
                if r.u32() >= nn:
                    raise ValueError
                r.u32()
        except (ValueError, struct.error):
            r.o = start
        mat, path = pkg.import_path(mi) if mi else ("", "")
        return dict(name=pkg.name(ni, nnum), material=mat, path=path)

    pat = re.compile(b"|".join(re.escape(struct.pack("<i", m)) for m in sorted(mat_imports)) or b"^$")
    for m in pat.finditer(d):
        k = m.start()
        if k < 4:
            continue
        n, = struct.unpack_from("<I", d, k - 4)
        if not 0 < n < 256:
            continue
        r = Reader(d, k)
        try:
            slots = [entry(r) for _ in range(n)]
        except (ValueError, struct.error, IndexError):
            continue
        return r.o, slots
    raise ValueError("material array not found")


# ---------------------------------------------------------------- skeletal mesh
def _skel_section(r):
    """FSkelMeshRenderSection"""
    r.u16()                                   # strip flags
    s = dict(slot=r.u16(), first=r.u32(), triangles=r.u32())
    r.bool32()                                # bRecomputeTangent
    r.u8()                                    # RecomputeTangentsVertexMaskChannel
    r.bool32()                                # bCastShadow
    r.bool32()                                # bVisibleInRayTracing
    s["base_vertex"] = r.u32()
    for _ in range(r.u32()):                  # ClothMappingDataLODs: TArray<TArray<FMeshToMeshVertData>>
        r.array(64, 1 << 22)
    r.array(2, 1 << 16)                       # BoneMap
    s["vertices"] = r.u32()
    r.u32()                                   # MaxBoneInfluences
    r.u16()                                   # CorrespondClothAssetIndex
    r.skip(20)                                # ClothingData: asset guid + lod index
    r.array(4)                                # DuplicatedVerticesBuffer: DupVertData
    r.array(8)                                #                           DupVertIndexData
    s["disabled"] = r.bool32()
    if s["slot"] > 255 or s["triangles"] > 1 << 24 or s["vertices"] > 1 << 24:
        raise ValueError("not a section")
    return s


def skeletal_lods(d):
    """every LOD header in the export data: [dict(start, sections, end)] in file order (LOD0 first)"""
    out, k = [], 0
    # section count, then the first section: strip flags, slot, first index 0
    for m in re.finditer(rb"(?s)(?=[\x01-\x7f]\x00\x00\x00[\x00\x01]\x00..\x00\x00\x00\x00)", d):
        p = m.start()
        if p < k:
            continue
        n, = struct.unpack_from("<I", d, p)
        r = Reader(d, p + 4)
        try:
            secs = []
            for _ in range(n):
                s = _skel_section(r)
                if secs and s["first"] != secs[-1]["first"] + 3 * secs[-1]["triangles"]:
                    raise ValueError("not a chain")
                secs.append(s)
            nab, _ = r.array(2, 1 << 16)      # ActiveBoneIndices
            buffers_size = r.u32()
        except (ValueError, struct.error, IndexError):
            continue
        out.append(dict(start=p, sections=secs, after=r.o, buffers_size=buffers_size,
                        inlined=_inlined_flag(d, p)))
        k = r.o
    return out


def _inlined_flag(d, p):
    """bInlined sits before RequiredBones (TArray<uint16>) which sits right before the section array"""
    for c in range(0, 4096):
        q = p - 4 - 2 * c
        if q < 10:
            break
        if struct.unpack_from("<I", d, q)[0] == c:
            cooked_out, inlined = struct.unpack_from("<II", d, q - 8)
            if cooked_out in (0, 1) and inlined in (0, 1):
                return bool(inlined)
    return None


def _skel_buffers(b, o, n_indices):
    """FSkeletalMeshLODRenderData::SerializeStreamedData up to the UVs"""
    r = Reader(b, o)
    r.u16()                                   # strip flags
    dts = r.u8()
    if dts not in (2, 4):
        raise ValueError(f"index size {dts}")
    _, n, idx = r.bulk_array("<u2" if dts == 2 else "<u4", dts)
    if n != n_indices:
        raise ValueError(f"{n} indices, the sections want {n_indices}")
    stride, nv = r.u32(), r.u32()
    _, n, pos = r.bulk_array("<f4", 12)
    if stride != 12 or n != nv:
        raise ValueError(f"position buffer: stride {stride}, {nv} vs {n} vertices")
    tex = _static_vertex_buffer(r, nv)
    return idx.astype(np.int64), pos.reshape(-1, 3), tex


def _static_vertex_buffer(r, nv):
    """FStaticMeshVertexBuffer -> dict(normals, tangents, uvs)"""
    r.u16()                                   # strip flags
    ntc, n = r.u32(), r.u32()
    full_uv, hi_tan = r.bool32(), r.bool32()
    if n != nv or not 0 < ntc <= 8:
        raise ValueError(f"vertex buffer: {ntc} UV channels, {n} vs {nv} vertices")
    es, n, raw = r.bulk_array(None, 16 if hi_tan else 8)
    if n != nv:
        raise ValueError("tangent count")
    if hi_tan:
        t = np.frombuffer(raw, "<i2").reshape(nv, 2, 4).astype(np.float32) / 32767.0
    else:
        t = np.frombuffer(raw, np.int8).reshape(nv, 2, 4).astype(np.float32) / 127.0
    es, n, raw = r.bulk_array(None, 8 if full_uv else 4)
    if n != nv * ntc:
        raise ValueError(f"UV count {n}, expected {nv} x {ntc}")
    uv = np.frombuffer(raw, "<f4" if full_uv else "<f2").astype(np.float32).reshape(nv, ntc, 2)
    nrm = t[:, 1, :3]
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-6)
    return dict(normals=nrm.astype(np.float32), tangents=t[:, 0, :3].copy(), sign=t[:, 1, 3].copy(), uvs=uv,
                end=r.o)


class Mesh:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return (f"<Mesh {self.name}: {len(self.positions)} vertices, {len(self.triangles)} triangles, "
                f"{len(self.slots)} slots>")

    def slot_index(self, name):
        for i, s in enumerate(self.slots):
            if name in (s["name"], s["material"]):
                return i
        raise KeyError(name)


def _assemble(name, slots, sections, idx, pos, tex, extra):
    tri = idx.reshape(-1, 3)
    tri_slot = np.full(len(tri), -1, np.int64)
    for s in sections:
        a = s["first"] // 3
        tri_slot[a:a + s["triangles"]] = s["slot"]
        lo, hi = s.get("base_vertex", 0), s.get("base_vertex", 0) + s.get("vertices", len(pos))
        t = tri[a:a + s["triangles"]]
        if len(t) and (t.min() < lo or t.max() >= hi):
            raise ValueError(f"section {s} uses vertices outside [{lo}, {hi})")
        if s["slot"] >= len(slots):
            raise ValueError(f"section uses slot {s['slot']}, there are {len(slots)}")
    if (tri_slot < 0).any():
        raise ValueError("triangles not covered by a section")
    if tri.max() >= len(pos):
        raise ValueError("index out of range")
    return Mesh(name=name, positions=pos.astype(np.float32), normals=tex["normals"], tangents=tex["tangents"],
                uvs=tex["uvs"], triangles=tri, tri_slot=tri_slot, slots=slots, sections=sections, **extra)


def _mesh_export(pkg):
    for want in ("SkeletalMesh", "StaticMesh"):
        for e in pkg.exports:
            if pkg.class_name(e["cls"]) == want:
                return want, e
    raise ValueError(f"{pkg.prefix}: no SkeletalMesh or StaticMesh export")


def load(prefix, newest=None):
    """LOD0 of the mesh in prefix(.uasset/.uexp/.ubulk).

    newest: optional (zen package bytes, container name) of a newer copy of the same package (from a patch
    container, see game.newest_export). When its name map matches the legacy files, its export data is used
    instead (the bulk data still comes from the .ubulk)."""
    pkg = Package(prefix)
    kind, exp = _mesh_export(pkg)
    d = pkg.export_data(exp)
    source = os.path.basename(prefix)
    if newest is not None:
        d, source = _graft(pkg, exp, d, *newest)
    _, slots = find_materials(pkg, d, static=kind == "StaticMesh")
    if kind == "StaticMesh":
        return _load_static(pkg, d, slots, exp, source)
    lods = skeletal_lods(d)
    if not lods:
        raise ValueError(f"{prefix}: no LOD render sections found")
    lod = lods[0]
    n_idx = 3 * sum(s["triangles"] for s in lod["sections"])
    r = Reader(d, lod["after"])
    inlined = lod["inlined"]
    if inlined is None:      # no flag found: inline data starts with strip flags + index size 2/4
        inlined = d[r.o + 2] in (2, 4) and struct.unpack_from("<i", d, r.o + 3)[0] == d[r.o + 2]
    if inlined:
        idx, pos, tex = _skel_buffers(d, r.o, n_idx)
        where = "inline"
    else:
        res = r.i32()
        if not 0 <= res < len(pkg.resources):
            raise ValueError(f"data resource index {res} (there are {len(pkg.resources)})")
        blob = pkg.bulk(res)
        if len(blob) != lod["buffers_size"]:
            raise ValueError(f"LOD0 bulk is {len(blob)} bytes, the header says {lod['buffers_size']}")
        idx, pos, tex = _skel_buffers(blob, 0, n_idx)
        where = f"data resource {res}"
    return _assemble(exp["name"], slots, lod["sections"], idx, pos, tex,
                     dict(kind=kind, lods=len(lods), lod0=where, source=source))


# ---------------------------------------------------------------- static mesh
def _static_sections(d, nslots):
    """FStaticMeshLODResources section arrays (MaterialIndex, FirstIndex, NumTriangles, MinVertexIndex,
    MaxVertexIndex, then bool flags) found by shape -> yields (offset after the array, sections) candidates,
    LOD0 first. The number of flag bools depends on the engine version (5 in UE 5.3)."""
    # section count, MaterialIndex, FirstIndex 0
    for m in re.finditer(rb"(?s)(?=[\x01-\x7f]\x00\x00\x00[\x00-\x7f]\x00\x00\x00\x00\x00\x00\x00)", d):
        k = m.start()
        n, mat, first = struct.unpack_from("<Iii", d, k)
        if not 0 < n < 128 or first != 0 or not 0 <= mat < nslots:
            continue
        for tail in (20, 24, 16, 28):
            q, secs = k + 4, []
            try:
                for _ in range(n):
                    mat, first, ntri, vmin, vmax = struct.unpack_from("<iIIII", d, q)
                    flags = struct.unpack_from(f"<{tail // 4}I", d, q + 20)
                    if not 0 <= mat < nslots or vmax < vmin or ntri == 0 or any(x > 1 for x in flags):
                        raise ValueError
                    if secs and first != secs[-1]["first"] + 3 * secs[-1]["triangles"]:
                        raise ValueError
                    secs.append(dict(slot=mat, first=first, triangles=ntri, base_vertex=vmin,
                                     vertices=vmax - vmin + 1))
                    q += 20 + tail
            except (ValueError, struct.error):
                continue
            yield q, secs


def _static_buffers(b, o, n_indices):
    """FStaticMeshLODResources::SerializeBuffers: strip flags, positions, vertex buffer, colours, indices"""
    r = Reader(b, o)
    r.u16()
    stride, nv = r.u32(), r.u32()
    _, n, pos = r.bulk_array("<f4", 12)
    if stride != 12 or n != nv:
        raise ValueError("position buffer")
    tex = _static_vertex_buffer(r, nv)
    r.u16()                                   # colour buffer: strip flags
    cstride, cn = r.u32(), r.u32()
    if cn:
        r.bulk_array(None, cstride)
    is32 = r.bool32()
    _, nbytes, raw = r.bulk_array(None, 1)
    idx = np.frombuffer(raw, "<u4" if is32 else "<u2").astype(np.int64)
    if len(idx) != n_indices:
        raise ValueError(f"{len(idx)} indices, the sections want {n_indices}")
    return idx, pos.reshape(-1, 3), tex


def _load_static(pkg, d, slots, exp, source):
    errors = []
    for q, secs in _static_sections(d, len(slots)):
        n_idx = 3 * sum(s["triangles"] for s in secs)
        r = Reader(d, q)
        try:
            r.f32()                               # MaxDeviation
            cooked_out, inlined = r.bool32(), r.bool32()
            if cooked_out:
                raise ValueError("LOD0 is cooked out")
            if inlined:
                idx, pos, tex = _static_buffers(d, r.o, n_idx)
                where = "inline"
            else:
                res = r.i32()
                if not 0 <= res < len(pkg.resources):
                    raise ValueError(f"data resource index {res}")
                idx, pos, tex = _static_buffers(pkg.bulk(res), 0, n_idx)
                where = f"data resource {res}"
            return _assemble(exp["name"], slots, secs, idx, pos, tex,
                             dict(kind="StaticMesh", lods=None, lod0=where, source=source))
        except (ValueError, struct.error, IndexError) as e:
            errors.append(f"{q}: {e}")
    raise ValueError("static mesh LOD0 not found" + (f" ({'; '.join(errors[:3])})" if errors else ""))


# ---------------------------------------------------------------- newer copy from a patch container
def _graft(pkg, exp, d, zen, container):
    import magneto_mats
    z = magneto_mats.zen_package(zen)
    if z["names"] != pkg.names[:len(z["names"])] or len(z["exports"]) != len(pkg.exports):
        raise ValueError(f"the {container} copy has a different name map or export list, can't use it")
    i = pkg.exports.index(exp)
    e = z["exports"][i]
    new = z["data"][e["offset"]:e["offset"] + e["size"]]
    if len(new) != e["size"]:
        raise ValueError(f"{container}: short export data")
    return new, f"{os.path.basename(pkg.prefix)} (export data from {container})"


def main():
    import argparse
    ap = argparse.ArgumentParser(description="print what skm.load finds in a mesh")
    ap.add_argument("prefix", help="legacy mesh path without .uasset")
    args = ap.parse_args()
    m = load(args.prefix)
    print(m, f"LOD0 from {m.lod0}, {m.lods} LODs")
    lo, hi = m.positions.min(0), m.positions.max(0)
    print(f"bounds {lo.round(1)} .. {hi.round(1)}, {m.uvs.shape[1]} UV channels")
    for i, s in enumerate(m.slots):
        n = int((m.tri_slot == i).sum())
        print(f"  slot {i:2d} {s['name']:<28} {s['material']:<28} {n:6d} triangles")


if __name__ == "__main__":
    main()
