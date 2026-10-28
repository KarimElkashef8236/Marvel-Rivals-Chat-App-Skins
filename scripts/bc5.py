"""BC4 / BC5 (two channel, used for normal maps) decode and encode with numpy.

Encode uses each block's min and max as the endpoints (8 value mode), which keeps the error under 1/14 of the
block's range. Good enough for the few blocks a skin changes.
"""
import numpy as np


def _bc4_palette(a0, a1):
    a0, a1 = a0.astype(np.float32), a1.astype(np.float32)
    i = np.arange(1, 7, dtype=np.float32)
    eight = ((7 - i) * a0[:, None] + i * a1[:, None]) / 7
    j = np.arange(1, 5, dtype=np.float32)
    six = np.concatenate([((5 - j) * a0[:, None] + j * a1[:, None]) / 5,
                          np.zeros((len(a0), 1), np.float32), np.full((len(a0), 1), 255, np.float32)], 1)
    rest = np.where((a0 > a1)[:, None], eight, six)
    return np.concatenate([a0[:, None], a1[:, None], rest], 1)


def _bc4_decode(blk):
    """(n, 8) uint8 blocks -> (n, 16) float"""
    bits = np.zeros(len(blk), np.uint64)
    for k in range(6):
        bits |= blk[:, 2 + k].astype(np.uint64) << np.uint64(8 * k)
    idx = ((bits[:, None] >> (np.arange(16, dtype=np.uint64) * np.uint64(3))) & np.uint64(7)).astype(np.int64)
    return np.take_along_axis(_bc4_palette(blk[:, 0], blk[:, 1]), idx, 1)


def _bc4_encode(px):
    """(n, 16) float 0..255 -> (n, 8) uint8 blocks"""
    a0 = np.clip(np.rint(px.max(1)), 0, 255).astype(np.uint8)
    a1 = np.clip(np.rint(px.min(1)), 0, 255).astype(np.uint8)
    pal = _bc4_palette(a0, a1)
    idx = np.abs(px[:, :, None] - pal[:, None, :]).argmin(-1)
    idx = np.where((a0 == a1)[:, None], 0, idx).astype(np.uint64)
    bits = (idx << (np.arange(16, dtype=np.uint64) * np.uint64(3))).sum(1)
    out = np.zeros((len(px), 8), np.uint8)
    out[:, 0], out[:, 1] = a0, a1
    for k in range(6):
        out[:, 2 + k] = ((bits >> np.uint64(8 * k)) & np.uint64(255)).astype(np.uint8)
    return out


def decode(data, w, h):
    """-> h x w x 2 uint8 (red, green)"""
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    blk = np.frombuffer(data, np.uint8, bw * bh * 16).reshape(-1, 16)
    ch = [_bc4_decode(blk[:, 0:8]), _bc4_decode(blk[:, 8:16])]
    img = np.clip(np.rint(np.stack(ch, -1)), 0, 255).astype(np.uint8)
    return img.reshape(bh, bw, 4, 4, 2).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 2)[:h, :w]


def encode(img):
    """h x w x 2 uint8 -> BC5 bytes. Pads to whole 4x4 blocks."""
    h, w = img.shape[:2]
    ph, pw = max(4, (h + 3) // 4 * 4), max(4, (w + 3) // 4 * 4)
    x = np.pad(img[..., :2], ((0, ph - h), (0, pw - w), (0, 0)), mode="edge").astype(np.float32)
    px = x.reshape(ph // 4, 4, pw // 4, 4, 2).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 2)
    return np.concatenate([_bc4_encode(px[..., 0]), _bc4_encode(px[..., 1])], 1).tobytes()
