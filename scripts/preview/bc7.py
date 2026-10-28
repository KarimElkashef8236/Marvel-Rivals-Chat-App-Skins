"""BC7 decode with numpy (all 8 modes), for previews of textures the game stores as PF_BC7.

    rgba = decode(data, w, h)     # -> h x w x 4 uint8

Blocks are grouped by mode and each group is decoded with array ops. Follows the D3D11 BC7 format spec
(partition and anchor tables below are the spec's; _check() verifies the anchors sit in their subsets).
"""
import numpy as np

# mode: subsets, partition bits, rotation bits, index selection bit, colour bits, alpha bits,
#       endpoint p-bits, shared p-bits, index bits, second index bits
MODES = [(3, 4, 0, 0, 4, 0, 1, 0, 3, 0), (2, 6, 0, 0, 6, 0, 0, 1, 3, 0), (3, 6, 0, 0, 5, 0, 0, 0, 2, 0),
         (2, 6, 0, 0, 7, 0, 1, 0, 2, 0), (1, 0, 2, 1, 5, 6, 0, 0, 2, 3), (1, 0, 2, 0, 7, 8, 0, 0, 2, 2),
         (1, 0, 0, 0, 7, 7, 1, 0, 4, 0), (2, 6, 0, 0, 5, 5, 1, 0, 2, 0)]

WEIGHTS = {2: [0, 21, 43, 64], 3: [0, 9, 18, 27, 37, 46, 55, 64],
           4: [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64]}

P2 = """
0011001100110011 0001000100010001 0111011101110111 0001001100110111 0000000100010011 0011011101111111 0001001101111111 0000000100110111
0000000000010011 0011011111111111 0000000101111111 0000000000010111 0001011111111111 0000000011111111 0000111111111111 0000000000001111
0000100011101111 0111000100000000 0000000010001110 0111001100010000 0011000100000000 0000100011001110 0000000010001100 0111001100110001
0011000100010000 0000100010001100 0110011001100110 0011011001101100 0001011111101000 0000111111110000 0111000110001110 0011100110011100
0101010101010101 0000111100001111 0101101001011010 0011001111001100 0011110000111100 0101010110101010 0110100101101001 0101101010100101
0111001111001110 0001001111001000 0011001001001100 0011101111011100 0110100110010110 0011110011000011 0110011010011001 0000011001100000
0100111001000000 0010011100100000 0000001001110010 0000010011100100 0110110010010011 0011011011001001 0110001110011100 0011100111000110
0110110011001001 0110001100111001 0111111010000001 0001100011100111 0000111100110011 0011001111110000 0010001011101110 0100010001110111
"""
P3 = """
0011001102212222 0001001122112221 0000200122112211 0222002200110111 0000000011221122 0011001100220022 0022002211111111 0011001122112211
0000000011112222 0000111111112222 0000111122222222 0012001200120012 0112011201120112 0122012201220122 0011011211221222 0011200122002220
0001001101121122 0111001120012200 0000112211221122 0022002200221111 0111011102220222 0001000122212221 0000001101220122 0000110022102210
0122012200110000 0012001211222222 0110122112210110 0000011012211221 0022110211020022 0110011020022222 0011012201220011 0000200022112221
0000000211221222 0222002200120011 0011001200220222 0120012001200120 0000111122220000 0120120120120120 0120201212010120 0011220011220011
0011112222000011 0101010122222222 0000000021212121 0022112200221122 0022001100220011 0220122102201221 0101222222220101 0000212121212121
0101010101012222 0222011102220111 0002111200021112 0000211221122112 0222011101110222 0002111211120002 0110011001102222 0000000021122112
0110011022222222 0022001100110022 0022112211220022 0000000000002112 0002000100020001 0222122202221222 0101222222222222 0111201122012220
"""
ANCHOR2 = [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2,
           2, 15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2,
           2, 15]
ANCHOR3A = [3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15,
            8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12,
            3, 3]
ANCHOR3B = [15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15,
            15, 10, 8, 15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15,
            15, 15, 3, 15, 15, 8]

PART = {1: np.zeros((64, 16), np.int64),
        2: np.array([[int(c) for c in w] for w in P2.split()], np.int64),
        3: np.array([[int(c) for c in w] for w in P3.split()], np.int64)}
ANCHORS = {1: np.zeros((64, 3), np.int64),
           2: np.array([[0, a, 0] for a in ANCHOR2], np.int64),
           3: np.array([[0, a, b] for a, b in zip(ANCHOR3A, ANCHOR3B)], np.int64)}


def _check():
    for n in (2, 3):
        p, a = PART[n], ANCHORS[n]
        assert p.shape == (64, 16)
        for s in range(1, n):
            assert (p[np.arange(64), a[:, s]] == s).all(), f"anchor table {n}/{s}"
        assert (p[:, 0] == 0).all()


_check()


def _expand(v, bits):
    """n bit endpoint -> 8 bits (shift up, fill the low bits with the top ones)"""
    v = v << (8 - bits)
    return v | (v >> bits)


def _decode_mode(blk, mode):
    ns, pb, rb, isb, cb, ab, epb, spb, ib, ib2 = MODES[mode]
    n = len(blk)
    lo = blk[:, :8].copy().view("<u8")[:, 0]
    hi = blk[:, 8:].copy().view("<u8")[:, 0]
    pos = np.full(n, mode + 1, np.int64)

    def take(nbits):
        """read nbits at each block's own position"""
        if np.isscalar(nbits):
            nbits = np.full(n, nbits, np.int64)
        v = np.zeros(n, np.int64)
        for b in range(int(nbits.max()) if len(nbits) else 0):
            p = pos + b
            bit = np.where(p < 64, (lo >> np.minimum(p, 63).astype(np.uint64)) & np.uint64(1),
                           (hi >> np.clip(p - 64, 0, 63).astype(np.uint64)) & np.uint64(1)).astype(np.int64)
            v |= np.where(b < nbits, bit << b, 0)
        pos[:] = pos + nbits
        return v

    part = take(pb) if pb else np.zeros(n, np.int64)
    rot = take(rb) if rb else np.zeros(n, np.int64)
    sel = take(isb) if isb else np.zeros(n, np.int64)
    ne = 2 * ns
    ep = np.zeros((n, ne, 4), np.int64)
    for c in range(3):
        for e in range(ne):
            ep[:, e, c] = take(cb)
    if ab:
        for e in range(ne):
            ep[:, e, 3] = take(ab)
    if epb:
        p = np.stack([take(1) for _ in range(ne)], 1)
    elif spb:
        sp = np.stack([take(1) for _ in range(ns)], 1)
        p = np.repeat(sp, 2, 1)
    else:
        p = None
    if p is not None:
        ep[..., :3] = (ep[..., :3] << 1) | p[..., None]
        if ab:
            ep[..., 3] = (ep[..., 3] << 1) | p
        cbits, abits = cb + 1, (ab + 1 if ab else 0)
    else:
        cbits, abits = cb, ab
    ep[..., :3] = _expand(ep[..., :3], cbits)
    if ab:
        ep[..., 3] = _expand(ep[..., 3], abits)
    else:
        ep[..., 3] = 255

    subset = PART[ns][part]                       # (n, 16)
    anchors = ANCHORS[ns][part]                   # (n, 3)
    idx = np.zeros((n, 16), np.int64)
    for i in range(16):
        anc = np.zeros(n, bool)
        for s in range(ns):
            anc |= anchors[:, s] == i
        idx[:, i] = take(np.where(anc, ib - 1, ib))
    if ib2:
        idx2 = np.zeros((n, 16), np.int64)
        for i in range(16):
            idx2[:, i] = take(ib2 - 1 if i == 0 else ib2)

    e0 = np.take_along_axis(ep, (2 * subset)[..., None].repeat(4, -1), 1)       # (n, 16, 4)
    e1 = np.take_along_axis(ep, (2 * subset + 1)[..., None].repeat(4, -1), 1)
    if ib2:
        w1 = np.array(WEIGHTS[ib])
        w2 = np.array(WEIGHTS[ib2])
        cw = np.where(sel[:, None] == 1, w2[idx2], w1[idx])
        aw = np.where(sel[:, None] == 1, w1[idx], w2[idx2])
    else:
        cw = aw = np.array(WEIGHTS[ib])[idx]
    out = np.empty((n, 16, 4), np.int64)
    out[..., :3] = ((64 - cw[..., None]) * e0[..., :3] + cw[..., None] * e1[..., :3] + 32) >> 6
    out[..., 3] = ((64 - aw) * e0[..., 3] + aw * e1[..., 3] + 32) >> 6
    if rb:
        for r_, ch in ((1, 0), (2, 1), (3, 2)):
            m = rot == r_
            if m.any():
                a = out[m, :, 3].copy()
                out[m, :, 3] = out[m, :, ch]
                out[m, :, ch] = a
    return out


def decode(data, w, h):
    """-> h x w x 4 uint8"""
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    blk = np.frombuffer(data, np.uint8, bw * bh * 16).reshape(-1, 16)
    first = blk[:, 0].astype(np.int64)
    mode = np.full(len(blk), 8, np.int64)          # 8 = reserved (all zero mode bits): black, alpha 0
    for m in range(7, -1, -1):
        mode = np.where((first >> m) & 1, m, mode)
    out = np.zeros((len(blk), 16, 4), np.int64)
    for m in range(8):
        sel = mode == m
        if sel.any():
            out[sel] = _decode_mode(blk[sel], m)
    img = np.clip(out, 0, 255).astype(np.uint8).reshape(bh, bw, 4, 4, 4)
    return img.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)[:h, :w]
