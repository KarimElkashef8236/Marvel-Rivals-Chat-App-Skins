"""Tiny PNG read/write (8 bit RGB/RGBA, no interlace) so the build doesn't need PIL."""
import struct
import zlib

import numpy as np


def write(path, img):
    img = np.ascontiguousarray(img, dtype=np.uint8)
    h, w = img.shape[:2]
    ch = 1 if img.ndim == 2 else img.shape[2]
    ctype = {1: 0, 3: 2, 4: 6}[ch]
    raw = b"".join(b"\0" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def read(path):
    b = open(path, "rb").read()
    pos, idat, hdr = 8, b"", None
    while pos < len(b):
        n, tag = struct.unpack_from(">I4s", b, pos)
        data = b[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", data)
        elif tag == b"IDAT":
            idat += data
        pos += 12 + n
    w, h, depth, ctype = hdr[:4]
    if depth != 8 or hdr[6]:
        raise ValueError(f"{path}: only 8 bit non interlaced png")
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + w * ch)
    out = np.zeros((h, w * ch), np.int32)
    prev = np.zeros(w * ch, np.int32)
    for y in range(h):
        f, line = raw[y, 0], raw[y, 1:].astype(np.int32)
        cur = np.zeros_like(line)
        if f == 0:
            cur = line
        elif f == 2:
            cur = (line + prev) & 255
        else:
            for x in range(len(line)):
                a = cur[x - ch] if x >= ch else 0
                c = prev[x - ch] if x >= ch else 0
                if f == 1:
                    p = a
                elif f == 3:
                    p = (a + prev[x]) >> 1
                else:
                    pa, pb, pc = abs(prev[x] - c), abs(a - c), abs(a + prev[x] - 2 * c)
                    p = a if pa <= pb and pa <= pc else (prev[x] if pb <= pc else c)
                cur[x] = (line[x] + p) & 255
        out[y] = prev = cur
    return out.reshape(h, w, ch).astype(np.uint8)
