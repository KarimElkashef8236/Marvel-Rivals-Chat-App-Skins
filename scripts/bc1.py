"""DXT1 / BC1 decode and encode with numpy (PCA fit + least squares endpoint refinement)."""
import numpy as np


def _565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.int32)


def _to565(e):
    e = np.clip(np.rint(e), 0, 255).astype(np.int32)
    return (((e[..., 0] * 31 + 127) // 255) << 11) | (((e[..., 1] * 63 + 127) // 255) << 5) | ((e[..., 2] * 31 + 127) // 255)


def decode(data, w, h):
    """-> h x w x 3 uint8"""
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    blk = np.frombuffer(data, np.uint8, bw * bh * 8).reshape(-1, 8)
    c0 = blk[:, 0].astype(np.int32) | (blk[:, 1].astype(np.int32) << 8)
    c1 = blk[:, 2].astype(np.int32) | (blk[:, 3].astype(np.int32) << 8)
    idx = blk[:, 4:8].copy().view("<u4")[:, 0].astype(np.int64)
    e0, e1 = _565(c0), _565(c1)
    four = (c0 > c1)[:, None]
    pal = np.stack([e0, e1, np.where(four, (2 * e0 + e1) // 3, (e0 + e1) // 2),
                    np.where(four, (e0 + 2 * e1) // 3, 0)], 1)
    ii = (idx[:, None] >> (np.arange(16) * 2)) & 3
    rgb = pal[np.arange(len(blk))[:, None], ii].astype(np.uint8)
    return rgb.reshape(bh, bw, 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 3)[:h, :w]


def encode(img, iters=3):
    """h x w x 3 uint8 -> BC1 bytes (opaque 4 colour mode). Pads to whole 4x4 blocks."""
    h, w = img.shape[:2]
    ph, pw = max(4, (h + 3) // 4 * 4), max(4, (w + 3) // 4 * 4)
    x = np.pad(img[..., :3], ((0, ph - h), (0, pw - w), (0, 0)), mode="edge").astype(np.float64)
    px = x.reshape(ph // 4, 4, pw // 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3)
    n = len(px)
    mean = px.mean(1)
    d = px - mean[:, None]
    cov = np.einsum("nki,nkj->nij", d, d)
    v = np.tile([0.577, 0.577, 0.577], (n, 1)) + 0.01 * (px.max(1) - px.min(1))
    for _ in range(8):
        v = np.einsum("nij,nj->ni", cov, v)
        nv = np.linalg.norm(v, axis=1, keepdims=True)
        v = np.where(nv > 1e-9, v / np.maximum(nv, 1e-12), 0.577)
    t = np.einsum("nki,ni->nk", d, v)
    e0, e1 = mean + t.max(1)[:, None] * v, mean + t.min(1)[:, None] * v
    w4 = np.array([0.0, 1.0, 1 / 3, 2 / 3])  # weight of e1 for palette index 0..3

    def palette(a, b):
        c0, c1 = _to565(a), _to565(b)
        q0, q1 = _565(c0).astype(np.float64), _565(c1).astype(np.float64)
        return c0, c1, np.stack([q0, q1, (2 * q0 + q1) // 3, (q0 + 2 * q1) // 3], 1)

    def assign(pal):
        dist = ((px[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)
        ii = dist.argmin(-1)
        return ii, np.take_along_axis(dist, ii[..., None], -1)[..., 0].sum(1)

    bc0, bc1, pal = palette(e0, e1)
    bi, berr = assign(pal)
    for _ in range(iters):
        b = w4[bi]
        a = 1 - b
        aa, bb, ab = (a * a).sum(1), (b * b).sum(1), (a * b).sum(1)
        ax, bx = (a[..., None] * px).sum(1), (b[..., None] * px).sum(1)
        det = aa * bb - ab * ab
        ok = np.abs(det) > 1e-8
        sd = np.where(ok, det, 1.0)[:, None]
        n0 = np.where(ok[:, None], (bb[:, None] * ax - ab[:, None] * bx) / sd, e0)
        n1 = np.where(ok[:, None], (aa[:, None] * bx - ab[:, None] * ax) / sd, e1)
        c0, c1, pal = palette(n0, n1)
        ii, err = assign(pal)
        better = err < berr
        bc0, bc1 = np.where(better, c0, bc0), np.where(better, c1, bc1)
        bi, berr = np.where(better[:, None], ii, bi), np.where(better, err, berr)
        e0, e1 = np.where(better[:, None], n0, e0), np.where(better[:, None], n1, e1)
    swap = bc0 < bc1  # 4 colour mode needs c0 > c1
    c0, c1 = np.where(swap, bc1, bc0), np.where(swap, bc0, bc1)
    ii = np.where(swap[:, None], np.array([1, 0, 3, 2])[bi], bi)
    ii = np.where((c0 == c1)[:, None], 0, ii)
    bits = (ii.astype(np.uint64) << (np.arange(16, dtype=np.uint64) * 2)).sum(1).astype(np.uint32)
    out = np.zeros((n, 8), np.uint8)
    out[:, 0], out[:, 1], out[:, 2], out[:, 3] = c0 & 255, c0 >> 8, c1 & 255, c1 >> 8
    out[:, 4:8] = bits.view(np.uint8).reshape(n, 4)
    return out.tobytes()


def psnr(a, b):
    mse = ((a.astype(np.float64) - b.astype(np.float64)) ** 2).mean()
    return float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)
