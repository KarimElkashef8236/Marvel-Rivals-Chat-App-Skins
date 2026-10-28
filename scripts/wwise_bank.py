"""Small Wwise soundbank reader/writer. Only touches DIDX/DATA, every other chunk is kept as is."""
import struct


class Bank:
    def __init__(self, data):
        self.chunks = []  # [tag, payload]
        off = 0
        while off < len(data):
            tag, size = struct.unpack_from("<4sI", data, off)
            self.chunks.append([tag, data[off + 8:off + 8 + size]])
            off += 8 + size
        self.version, self.bank_id = struct.unpack_from("<II", self.get(b"BKHD"), 0)
        self.media, self.order = {}, []
        didx, blob = self.get(b"DIDX"), self.get(b"DATA")
        if didx:
            for i in range(len(didx) // 12):
                mid, moff, msz = struct.unpack_from("<III", didx, i * 12)
                self.media[mid] = blob[moff:moff + msz]
                self.order.append(mid)

    def get(self, tag):
        for t, p in self.chunks:
            if t == tag:
                return p
        return None

    def put(self, tag, payload):
        for c in self.chunks:
            if c[0] == tag:
                c[1] = payload
                return
        raise KeyError(tag)

    def hirc(self):
        """yield (type, id, payload offset in HIRC, size)"""
        h = self.get(b"HIRC")
        if not h:
            return
        off = 4
        for _ in range(struct.unpack_from("<I", h, 0)[0]):
            t, sz, oid = struct.unpack_from("<BII", h, off)
            yield t, oid, off + 5, sz
            off += 5 + sz

    def sources(self):
        """sound objects (type 2) and the media they point at"""
        h = self.get(b"HIRC")
        for t, oid, po, _ in self.hirc():
            if t == 2:
                plugin, stream, sid, memsize = struct.unpack_from("<IBII", h, po + 4)
                yield dict(obj=oid, plugin=plugin, stream=stream, sid=sid, memsize=memsize)

    def set_media(self, mid, data):
        if mid not in self.media:
            self.order.append(mid)
        self.media[mid] = data

    def build(self):
        # media is 16 byte aligned inside DATA, same as the game's banks
        didx, blob = bytearray(), bytearray()
        for mid in self.order:
            blob += b"\0" * (-len(blob) % 16)
            didx += struct.pack("<III", mid, len(blob), len(self.media[mid]))
            blob += self.media[mid]
        if self.media:
            self.put(b"DIDX", bytes(didx))
            self.put(b"DATA", bytes(blob))
        return b"".join(struct.pack("<4sI", t, len(p)) + p for t, p in self.chunks)
