"""Small numpy software rasterizer: orthographic triangles -> per pixel triangle id, barycentrics and depth.

    tri, bary, depth = rasterize(xy, z, triangles, width, height, keep=None)

xy: (V, 2) pixel positions (x right, y down, pixel i covers [i, i + 1), sampled at its centre i + 0.5),
z: (V,) depth with bigger = closer to the camera. Orthographic, so barycentrics are linear on screen and exact.
tri: (H, W) int64 triangle index or -1, bary: (H, W, 3) float32, depth: (H, W) float32 (-inf where empty).
keep(tri_ids, bary) -> bool mask is called on the covered fragments before the depth test, which is how alpha
tested hair cards drop their see-through texels (they mustn't hide what's behind them).

Supersampling is the caller's job: rasterize at k times the size and average k x k blocks (downsample()).
"""
import numpy as np


def rasterize(xy, z, triangles, width, height, keep=None, budget=3_000_000):
    xy = np.asarray(xy, np.float64)
    z = np.asarray(z, np.float64)
    t = np.asarray(triangles, np.int64)
    v0, v1, v2 = xy[t[:, 0]], xy[t[:, 1]], xy[t[:, 2]]
    area = (v1[:, 0] - v0[:, 0]) * (v2[:, 1] - v0[:, 1]) - (v1[:, 1] - v0[:, 1]) * (v2[:, 0] - v0[:, 0])
    lo = np.minimum(np.minimum(v0, v1), v2)
    hi = np.maximum(np.maximum(v0, v1), v2)
    x0 = np.clip(np.ceil(lo[:, 0] - 0.5), 0, width).astype(np.int64)
    x1 = np.clip(np.floor(hi[:, 0] - 0.5), -1, width - 1).astype(np.int64)
    y0 = np.clip(np.ceil(lo[:, 1] - 0.5), 0, height).astype(np.int64)
    y1 = np.clip(np.floor(hi[:, 1] - 0.5), -1, height - 1).astype(np.int64)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    ok = (np.abs(area) > 1e-12) & (bw > 0) & (bh > 0)
    ids = np.nonzero(ok)[0]
    counts = (bw[ids] * bh[ids]).astype(np.int64)

    best_tri = np.full(width * height, -1, np.int64)
    best_z = np.full(width * height, -np.inf, np.float64)
    best_b = np.zeros((width * height, 3), np.float32)

    # chunks of triangles whose bounding boxes add up to about `budget` pixels
    csum = np.cumsum(counts)
    start = 0
    while start < len(ids):
        base = csum[start - 1] if start else 0
        end = int(np.searchsorted(csum, base + budget, side="right"))
        end = max(end, start + 1)
        ci, cc = ids[start:end], counts[start:end]
        start = end
        total = int(cc.sum())
        if total == 0:
            continue
        rep = np.repeat(np.arange(len(ci)), cc)
        offs = np.arange(total, dtype=np.int64) - np.repeat(np.cumsum(cc) - cc, cc)
        w = bw[ci][rep]
        px = x0[ci][rep] + offs % w
        py = y0[ci][rep] + offs // w
        tid = ci[rep]
        cx, cy = px + 0.5, py + 0.5
        a, b, c = v0[tid], v1[tid], v2[tid]
        inv = 1.0 / area[tid]
        b0 = ((b[:, 0] - cx) * (c[:, 1] - cy) - (b[:, 1] - cy) * (c[:, 0] - cx)) * inv
        b1 = ((c[:, 0] - cx) * (a[:, 1] - cy) - (c[:, 1] - cy) * (a[:, 0] - cx)) * inv
        b2 = 1.0 - b0 - b1
        inside = (b0 >= 0) & (b1 >= 0) & (b2 >= -1e-9)
        if not inside.any():
            continue
        tid, px, py = tid[inside], px[inside], py[inside]
        bb = np.stack([b0[inside], b1[inside], b2[inside]], 1).astype(np.float32)
        if keep is not None:
            k = keep(tid, bb)
            tid, px, py, bb = tid[k], px[k], py[k], bb[k]
            if not len(tid):
                continue
        tt = t[tid]
        fz = bb[:, 0] * z[tt[:, 0]] + bb[:, 1] * z[tt[:, 1]] + bb[:, 2] * z[tt[:, 2]]
        pid = py * width + px
        order = np.lexsort((-fz, pid))        # by pixel, closest first
        pid, fz, tid, bb = pid[order], fz[order], tid[order], bb[order]
        first = np.ones(len(pid), bool)
        first[1:] = pid[1:] != pid[:-1]
        pid, fz, tid, bb = pid[first], fz[first], tid[first], bb[first]
        win = fz > best_z[pid]
        pid = pid[win]
        best_z[pid], best_tri[pid], best_b[pid] = fz[win], tid[win], bb[win]

    return (best_tri.reshape(height, width), best_b.reshape(height, width, 3),
            best_z.astype(np.float32).reshape(height, width))


def downsample(img, k):
    """average k x k blocks (supersampling resolve). img: (H, W, ...) with H, W multiples of k"""
    if k == 1:
        return img
    h, w = img.shape[:2]
    return img.reshape(h // k, k, w // k, k, *img.shape[2:]).mean((1, 3))


def interpolate(attr, triangles, tri, bary):
    """per vertex attribute (V, ...) -> per pixel values for the covered pixels (mask = tri >= 0)"""
    m = tri >= 0
    tt = triangles[tri[m]]
    b = bary[m]
    a = attr[tt]                                   # (n, 3, ...)
    shape = (len(b), 3) + (1,) * (a.ndim - 2)
    return (a * b.reshape(shape)).sum(1), m


def blur(img, r):
    """separable box blur repeated 3 times (close to a gaussian), edges clamped"""
    if r < 1:
        return img
    out = img.astype(np.float32)
    for axis in (0, 1):
        for _ in range(3):
            pad = [(0, 0)] * out.ndim
            pad[axis] = (r + 1, r)
            p = np.pad(out, pad, mode="edge")
            c = np.cumsum(p, axis=axis, dtype=np.float64)
            n = out.shape[axis]
            hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
            lo = np.take(c, np.arange(0, n), axis=axis)
            out = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return out
