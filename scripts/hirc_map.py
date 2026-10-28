"""Map Wwise events in a bank to the media they can play.

Event names come from the game's AkAudioEvent asset names (Wwise ids are the
FNV-1 32 hash of the lowercase name). Containers are linked through each node's
DirectParentID, so any media under an event's play target counts.
"""
import struct
from collections import defaultdict

from wwise_bank import Bank

CONTAINERS = {5, 6, 7, 9}  # random/sequence, switch, actor mixer, blend


def fnv1(name):
    h = 2166136261
    for c in name.lower().encode():
        h = ((h * 16777619) & 0xFFFFFFFF) ^ c
    return h


VOLUME, PITCH, MAKEUP_GAIN = 0x00, 0x02, 0x06


def _node_base(p, off):
    """NodeBaseParams: override fx, fx list, override metadata, metadata list, override attachment,
    bus, parent, bit vector, then the prop bundle. Returns (parent, {prop id: float})."""
    num_fx = p[off + 1]
    off += 2 + (1 + 7 * num_fx if num_fx else 0)
    num_meta = p[off + 1]
    off += 2 + 6 * num_meta
    off += 1 + 4
    parent = struct.unpack_from("<I", p, off)[0]
    off += 4 + 1
    n = p[off]
    ids = p[off + 1:off + 1 + n]
    vals = struct.unpack_from(f"<{n}f", p, off + 1 + n)
    return parent, dict(zip(ids, vals))


class HircMap:
    def __init__(self, bank: Bank, names=()):
        h = bank.get(b"HIRC")
        self.types, self.parent, self.source, self.props = {}, {}, {}, {}
        self.children = defaultdict(list)
        self.event_actions, self.action = {}, {}
        for t, oid, po, sz in bank.hirc():
            p = h[po + 4:po + sz]
            self.types[oid] = t
            if t == 2:
                plugin, sid = struct.unpack_from("<IxI", p, 0)
                off = 14
                if plugin & 0xF == 1:  # codec (real audio), not a source plugin like silence or vibration
                    self.source[oid] = sid
                elif plugin & 0xF == 2:  # source plugins carry their params first
                    off += 4 + struct.unpack_from("<I", p, 14)[0]
                self.parent[oid], self.props[oid] = _node_base(p, off)
            elif t in CONTAINERS:
                self.parent[oid], self.props[oid] = _node_base(p, 0)
            elif t == 3:
                self.action[oid] = struct.unpack_from("<HI", p, 0)
            elif t == 4:
                n = p[0]
                self.event_actions[oid] = list(struct.unpack_from(f"<{n}I", p, 1))
        for oid, par in self.parent.items():
            self.children[par].append(oid)
        self.names = {fnv1(n): n for n in names}

    def sounds_under(self, oid):
        out, stack = [], [oid]
        while stack:
            o = stack.pop()
            if self.types.get(o) == 2 and o in self.source:
                out.append(o)
            stack.extend(self.children.get(o, []))
        return out

    def chain(self, oid):
        """(volume dB, pitch cents) the game adds on top of a sound, summed up its parents in this bank"""
        vol = pitch = 0.0
        while oid in self.props:
            pr = self.props[oid]
            vol += pr.get(VOLUME, 0.0) + pr.get(MAKEUP_GAIN, 0.0)
            pitch += pr.get(PITCH, 0.0)
            oid = self.parent.get(oid)
        return vol, pitch

    def media_chains(self, eid):
        """{media: (volume dB, pitch cents)} for the sounds an event can play"""
        out = {}
        for aid in self.event_actions.get(eid, []):
            atype, target = self.action.get(aid, (0, 0))
            if atype & 0xFF00 == 0x0400:
                for s in self.sounds_under(target):
                    out.setdefault(self.source[s], self.chain(s))
        return out

    def event_media(self, eid):
        """media ids an event can start (play actions only)"""
        media = []
        for aid in self.event_actions.get(eid, []):
            atype, target = self.action.get(aid, (0, 0))
            if atype & 0xFF00 == 0x0400:  # play
                for s in self.sounds_under(target):
                    if self.source[s] not in media:
                        media.append(self.source[s])
        return media

    def split_event(self, eid):
        """(main, extra): main = media of the first audible play action, where random and
        switch children are alternatives and only one child of a blend layer is kept. extra =
        everything else the event plays at the same time (layers under the main sound)."""
        main, extra = [], []

        def walk(o):
            t = self.types.get(o)
            if t == 2:
                if o in self.source and self.source[o] not in main:
                    main.append(self.source[o])
                return
            kids = [k for k in self.children.get(o, []) if self.sounds_under(k)]
            if t == 9 and kids:
                keep = next((k for k in kids if {self.source[s] for s in self.sounds_under(k)} <= set(main)), kids[0])
                for k in kids:
                    if k != keep:
                        extra.extend(self.source[s] for s in self.sounds_under(k))
                kids = [keep]
            for k in kids:
                walk(k)

        targets = [t for a in self.event_actions.get(eid, [])
                   for at, t in [self.action.get(a, (0, 0))] if at & 0xFF00 == 0x0400 and self.sounds_under(t)]
        # the main sound is the one picked from variants (random/switch) if there is one
        first = next((t for t in targets if self.types.get(t) in (5, 6)), targets[0] if targets else None)
        for t in targets:
            if t == first:
                walk(t)
            else:
                extra.extend(self.source[s] for s in self.sounds_under(t))
        return main, [m for m in dict.fromkeys(extra) if m not in main]

    def events(self):
        return {eid: self.names.get(eid, str(eid)) for eid in self.event_actions}
