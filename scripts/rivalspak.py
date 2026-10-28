"""Read and write Marvel Rivals legacy .pak files (v11).

Rivals paks use the public game AES key, but only the first N bytes of every
file are encrypted, where N comes from a blake3 hash of the file path. This
matches what repak-rivals does so the output looks the same as the game's own paks.
"""
import ctypes
import hashlib
import io
import os
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from blake3_small import blake3

AES_KEY = bytes.fromhex("0C263D8C22DCB085894899C3A3796383E9BF9DE0CBFB08C9BF2DEF2E84F29D74")
OODLE_DLL = os.path.join(os.path.dirname(__file__), "..", "tools", "retoc-rivals", "oo2core_9_win64.dll")
MAGIC = 0x5A6F12E1
BLOCK = 0x10000
# NetEase writes this between the index and the footer on every pak
TRAILER = bytes.fromhex("0612242006000000010200100000000000000100010000000000000010000000000000")


def _swap4(b):
    return b"".join(b[i:i + 4][::-1] for i in range(0, len(b), 4))


def decrypt(b):
    d = Cipher(algorithms.AES(_swap4(AES_KEY)), modes.ECB()).decryptor()
    return _swap4(d.update(_swap4(b)) + d.finalize())


def encrypt(b):
    e = Cipher(algorithms.AES(_swap4(AES_KEY)), modes.ECB()).encryptor()
    return _swap4(e.update(_swap4(b)) + e.finalize())


def pad16(b):
    return b + b"\0" * (-len(b) % 16)


def enc_limit(path):
    h = blake3(b"\x11\x22\x33\x44" + path.lower().encode())
    limit = ((struct.unpack("<Q", h[:8])[0] % 0x3D) * 63 + 319) & ~0x3F
    return limit or 0x1000


def root_path(mount, name):
    p = mount + "/" + name
    while "//" in p:
        p = p.replace("//", "/")
    return p[len("../../../"):] if p.startswith("../../../") else p


_oodle = None


def oodle():
    global _oodle
    if _oodle is None:
        if not os.path.exists(OODLE_DLL):
            raise RuntimeError("oo2core_9_win64.dll missing, run retoc-rivals-cli once to unpack it")
        _oodle = ctypes.WinDLL(os.path.abspath(OODLE_DLL))
        i64, i32, vp = ctypes.c_int64, ctypes.c_int32, ctypes.c_void_p
        _oodle.OodleLZ_Decompress.restype = i64
        _oodle.OodleLZ_Decompress.argtypes = [ctypes.c_char_p, i64, ctypes.c_char_p, i64, i32, i32, i32,
                                              vp, i64, vp, vp, vp, i64, i32]
        _oodle.OodleLZ_Compress.restype = i64
        _oodle.OodleLZ_Compress.argtypes = [i32, ctypes.c_char_p, i64, ctypes.c_char_p, i32, vp, vp, vp, vp, i64]
        _oodle.OodleLZ_GetCompressedBufferSizeNeeded.restype = i64
        _oodle.OodleLZ_GetCompressedBufferSizeNeeded.argtypes = [i32, i64]
    return _oodle


def oodle_decompress(src, rawlen):
    out = ctypes.create_string_buffer(rawlen)
    n = oodle().OodleLZ_Decompress(src, len(src), out, rawlen, 1, 1, 0, None, 0, None, None, None, 0, 3)
    if n != rawlen:
        raise RuntimeError(f"oodle decompress failed ({n} != {rawlen})")
    return out.raw


def oodle_compress(src, compressor=8, level=4):  # Kraken, Normal like repak-rivals
    o = oodle()
    out = ctypes.create_string_buffer(o.OodleLZ_GetCompressedBufferSizeNeeded(compressor, len(src)))
    n = o.OodleLZ_Compress(compressor, src, len(src), out, level, None, None, None, None, 0)
    if n <= 0:
        raise RuntimeError("oodle compress failed")
    return out.raw[:n]


def _rstr(f):
    n = struct.unpack("<i", f.read(4))[0]
    if n == 0:
        return ""
    if n < 0:
        return f.read(-n * 2).decode("utf-16-le").rstrip("\0")
    return f.read(n).decode("utf-8").rstrip("\0")


def _wstr(s):
    b = s.encode("utf-8") + b"\0"
    return struct.pack("<i", len(b)) + b


class Pak:
    def __init__(self, path):
        self.path = path
        self.fh = open(path, "rb")
        self.fh.seek(0, 2)
        foot = self._rd(self.fh.tell() - 221, 221)
        self.encrypted_index = foot[16]
        magic, self.version, ioff, isize = struct.unpack("<IiQQ", foot[17:41])
        if magic != MAGIC:
            raise ValueError("not a pak")
        self.compression = [foot[61 + i * 32:93 + i * 32].rstrip(b"\0").decode() for i in range(5)]
        f = io.BytesIO(self._idx(ioff, isize))
        self.mount = _rstr(f)
        self.count, self.seed = struct.unpack("<iQ", f.read(12))
        if struct.unpack("<I", f.read(4))[0]:
            f.read(36)
        if not struct.unpack("<I", f.read(4))[0]:
            raise ValueError("no full directory index")
        fdoff, fdsize = struct.unpack("<qq", f.read(16))
        f.read(20)
        self._encoded = f.read(struct.unpack("<i", f.read(4))[0])
        g = io.BytesIO(self._idx(fdoff, fdsize))
        self.files = {}
        # names with no location: patch paks list their iostore packages this way,
        # and for loose files like .bnk/.wem it means the patch deleted them
        self.no_location = set()
        for _ in range(struct.unpack("<i", g.read(4))[0]):
            d = _rstr(g)
            for _ in range(struct.unpack("<i", g.read(4))[0]):
                name = (d + _rstr(g)).lstrip("/")
                eo = struct.unpack("<i", g.read(4))[0]
                if eo >= 0:
                    self.files[name] = eo
                else:
                    self.no_location.add(name)

    def _rd(self, off, n):
        self.fh.seek(off)
        return self.fh.read(n)

    def _idx(self, off, n):
        b = self._rd(off, n)
        return decrypt(b) if self.encrypted_index else b

    def entry(self, name):
        e = io.BytesIO(self._encoded[self.files[name]:])
        v = struct.unpack("<I", e.read(4))[0]
        bsize = v & 0x3F
        bsize = struct.unpack("<I", e.read(4))[0] if bsize == 0x3F else bsize << 11
        comp = (v >> 23) & 0x3F
        enc = bool(v & (1 << 22))
        nblk = (v >> 6) & 0xFFFF

        def var(bit):
            return struct.unpack("<I", e.read(4))[0] if v & (1 << bit) else struct.unpack("<Q", e.read(8))[0]

        off, usize = var(31), var(30)
        size = var(29) if comp else usize
        hdr = 53 + (4 + 16 * nblk if comp else 0)
        blocks = []
        if comp:
            if nblk == 1 and not enc:
                blocks = [(0, size)]
            else:
                cur = 0
                for _ in range(nblk):
                    b = struct.unpack("<I", e.read(4))[0]
                    blocks.append((cur, cur + b))
                    cur += (b + 15) & ~15 if enc else b
        return dict(offset=off, size=size, usize=usize, comp=comp, encrypted=enc, bsize=bsize, blocks=blocks, hdr=hdr)

    def read(self, name):
        e = self.entry(name)
        data = self._rd(e["offset"] + e["hdr"], (e["size"] + 15) & ~15 if e["encrypted"] else e["size"])
        if e["encrypted"]:
            lim = min(enc_limit(root_path(self.mount, name)), len(data))
            data = decrypt(data[:lim]) + data[lim:]
        data = data[:e["size"]]
        if not e["comp"]:
            return data
        out = bytearray()
        for s, t in e["blocks"]:
            # single block entries can have a block size of 0, same as repak
            want = e["usize"] if len(e["blocks"]) == 1 else min(e["bsize"], e["usize"] - len(out))
            out += oodle_decompress(data[s:t], want)
        if len(out) != e["usize"]:
            raise RuntimeError(f"{name}: size mismatch")
        return bytes(out)

    def full_name(self, name):
        return root_path(self.mount, name)


def _fnv64_path(path, seed):
    h = (0xCBF29CE484222325 + seed) & 0xFFFFFFFFFFFFFFFF
    for b in path.lower().encode("utf-16-le"):
        h = ((h ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _split(path):
    p = path[:-1] if path.endswith("/") else path
    i = p.rfind("/")
    return ("/", p) if i < 0 else (p[:i + 1], p[i + 1:])


def write_pak(out_path, files, mount="../../../", compress=True, encrypt_files=True):
    """files: {path relative to mount: bytes}. Mirrors repak-rivals V11 output."""
    buf = io.BytesIO()
    entries = {}
    for name in sorted(files):
        raw = files[name]
        full = root_path(mount, name)
        blocks = []
        if compress and raw:
            data = b""
            for i in range(0, len(raw), BLOCK):
                c = oodle_compress(raw[i:i + BLOCK])
                if encrypt_files:
                    c = pad16(c)
                blocks.append(len(c))
                data += c
            bsize = BLOCK
        else:
            data, bsize = raw, 0
        sha = hashlib.sha1(data).digest()
        if encrypt_files:
            lim = enc_limit(full)
            if lim > len(data):
                data = pad16(data)
                lim = len(data)
            data = encrypt(data[:lim]) + data[lim:]
        offset = buf.tell()
        comp = 1 if blocks else 0
        hdr_size = 53 + (4 + 16 * len(blocks) if comp else 0)
        hdr = struct.pack("<QQQI", 0, len(data), len(raw), comp) + sha
        if comp:
            hdr += struct.pack("<I", len(blocks))
            cur = hdr_size
            for b in blocks:
                hdr += struct.pack("<QQ", cur, cur + b)
                cur += b
        hdr += struct.pack("<BI", 1 if encrypt_files else 0, bsize)
        buf.write(hdr)
        buf.write(data)
        entries[name] = dict(offset=offset, size=len(data), usize=len(raw), comp=comp, blocks=blocks,
                             bsize=bsize, enc=encrypt_files)

    enc_entries, offsets = io.BytesIO(), {}
    for name, e in entries.items():
        offsets[name] = enc_entries.tell()
        bs = (e["bsize"] >> 11) & 0x3F
        if bs << 11 != e["bsize"]:
            bs = 0x3F
        flags = (bs | (len(e["blocks"]) << 6) | (int(e["enc"]) << 22) | (e["comp"] << 23)
                 | (1 << 29) | (1 << 30) | (1 << 31))
        enc_entries.write(struct.pack("<I", flags))
        if bs == 0x3F:
            enc_entries.write(struct.pack("<I", e["bsize"]))
        enc_entries.write(struct.pack("<II", e["offset"], e["usize"]))
        if e["comp"]:
            enc_entries.write(struct.pack("<I", e["size"]))
            if len(e["blocks"]) > 1 or e["enc"]:
                for b in e["blocks"]:
                    enc_entries.write(struct.pack("<I", b))
    enc_entries = enc_entries.getvalue()

    index_offset = buf.tell()
    seed = 0
    head_len = 4 + len(mount) + 1 + 8 + 4 + 4 + 36 + 4 + 36 + 4 + len(enc_entries) + 4
    phi_offset = index_offset + head_len + (-head_len % 16)

    phi = struct.pack("<I", len(entries))
    for name in entries:
        phi += struct.pack("<QI", _fnv64_path(name, seed), offsets[name])
    phi += struct.pack("<I", 0)

    dirs = {}
    for name in entries:
        p = name
        while p not in ("", "/"):
            p = _split(p)[0]
            dirs.setdefault(p, {})
        d, f = _split(name)
        dirs.setdefault(d, {})[f] = offsets[name]
    fdi = struct.pack("<I", len(dirs))
    for d in sorted(dirs):
        fdi += _wstr(d) + struct.pack("<I", len(dirs[d]))
        for f in sorted(dirs[d]):
            fdi += _wstr(f) + struct.pack("<I", dirs[d][f])

    def seal(b):
        b = pad16(b)
        return b, hashlib.sha1(b).digest(), encrypt(b)

    phi, phi_hash, phi_enc = seal(phi)
    fdi_offset = phi_offset + len(phi)
    fdi, fdi_hash, fdi_enc = seal(fdi)

    index = _wstr(mount) + struct.pack("<IQ", len(entries), seed)
    index += struct.pack("<IQQ", 1, phi_offset, len(phi)) + phi_hash
    index += struct.pack("<IQQ", 1, fdi_offset, len(fdi)) + fdi_hash
    index += struct.pack("<I", len(enc_entries)) + enc_entries + struct.pack("<I", 0)
    index, index_hash, index_enc = seal(index)

    buf.write(index_enc)
    buf.write(phi_enc)
    buf.write(fdi_enc)
    buf.write(TRAILER)
    names = [b"Oodle" if any(e["comp"] for e in entries.values()) else b""] + [b""] * 4
    buf.write(b"\0" * 16 + b"\x01" + struct.pack("<IIQQ", MAGIC, 11, index_offset, len(index)) + index_hash
              + b"".join(n.ljust(32, b"\0") for n in names))
    with open(out_path, "wb") as fh:
        fh.write(buf.getvalue())
