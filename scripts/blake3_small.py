"""BLAKE3 for inputs up to 1024 bytes (one chunk). Enough for hashing pak paths."""
import struct

IV = [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19]
PERM = [2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8]
CHUNK_START, CHUNK_END, ROOT = 1, 2, 8
M32 = 0xFFFFFFFF

def _rotr(x, n):
    return ((x >> n) | (x << (32 - n))) & M32

def _g(s, a, b, c, d, mx, my):
    s[a] = (s[a] + s[b] + mx) & M32; s[d] = _rotr(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & M32;      s[b] = _rotr(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b] + my) & M32; s[d] = _rotr(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & M32;      s[b] = _rotr(s[b] ^ s[c], 7)

def _compress(cv, m, counter, blen, flags):
    s = list(cv) + IV[:4] + [counter & M32, counter >> 32, blen, flags]
    m = list(m)
    for r in range(7):
        _g(s, 0, 4, 8, 12, m[0], m[1]);  _g(s, 1, 5, 9, 13, m[2], m[3])
        _g(s, 2, 6, 10, 14, m[4], m[5]); _g(s, 3, 7, 11, 15, m[6], m[7])
        _g(s, 0, 5, 10, 15, m[8], m[9]); _g(s, 1, 6, 11, 12, m[10], m[11])
        _g(s, 2, 7, 8, 13, m[12], m[13]); _g(s, 3, 4, 9, 14, m[14], m[15])
        if r < 6: m = [m[i] for i in PERM]
    for i in range(8):
        s[i] ^= s[i + 8]; s[i + 8] ^= cv[i]
    return s

def blake3(data: bytes) -> bytes:
    assert len(data) <= 1024, "single chunk only"
    blocks = [data[i:i + 64] for i in range(0, len(data), 64)] or [b'']
    cv = IV
    for i, b in enumerate(blocks):
        flags = (CHUNK_START if i == 0 else 0)
        if i == len(blocks) - 1: flags |= CHUNK_END | ROOT
        words = struct.unpack('<16I', b.ljust(64, b'\0'))
        out = _compress(cv, words, 0, len(b), flags)
        cv = out[:8]
    return struct.pack('<8I', *out[:8])

if __name__ == '__main__':
    assert blake3(b'').hex() == 'af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262'
    assert blake3(b'abc').hex() == '6437b3ac38465133ffb63b75273a8db548c558465d79db03fd359c6cd5bd9d85'
    # official test vector input: bytes i % 251, length 1023 (single chunk, 16 blocks)
    v = bytes(i % 251 for i in range(1023))
    assert blake3(v).hex().startswith('10108970eeda3eb932baac1428c7a2163b0e924c9a9e25b35bba72b28f70bd11'), blake3(v).hex()
    print('blake3 ok')
