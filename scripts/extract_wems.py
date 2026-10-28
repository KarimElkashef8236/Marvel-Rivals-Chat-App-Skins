"""Pull the custom sounds out of the old Season 1.5 sound pak.

A media entry counts as custom when the old mod bank has it and the current game
bank has the same id with different data. Old game sounds that NetEase removed
since then are skipped. Output goes to audio/<bank name>/<media id>.wem
"""
import argparse
import os
import struct

from gamefiles import GameFiles
from paths import DEFAULT_PAKS
from rivalspak import Pak
from wwise_bank import Bank

ROOT = os.path.join(os.path.dirname(__file__), "..")


def wem_desc(b):
    fmt, ch, rate = struct.unpack_from("<HHI", b, 20)
    kind = {0xFFFE: "pcm", 0xFFFF: "vorbis"}.get(fmt, hex(fmt))
    return f"{kind} {ch}ch {rate}Hz {len(b)} bytes"


def pcm_wem_to_wav(b):
    fmt, ch, rate, _, align, bits = struct.unpack_from("<HHIIHH", b, 20)
    off = 12
    while off + 8 <= len(b):
        tag, size = struct.unpack_from("<4sI", b, off)
        if tag == b"data":
            data = b[off + 8:off + 8 + size]
            head = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(data), b"WAVE", b"fmt ", 16, 1, ch, rate,
                               rate * align, align, bits, b"data", len(data))
            return head + data
        off += 8 + size + (size & 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sound_pak", help="the original 68_DoctorWhatsappSounds_9999999_P.pak")
    ap.add_argument("--game", default=DEFAULT_PAKS)
    args = ap.parse_args()

    old = Pak(args.sound_pak)
    game = GameFiles(args.game)
    for name in old.files:
        if not name.endswith(".bnk"):
            continue
        full = old.full_name(name)
        mod_bank = Bank(old.read(name))
        cur_data, src = game.read(full)
        cur_bank = Bank(cur_data)
        bank_name = os.path.splitext(os.path.basename(name))[0]
        out = os.path.join(ROOT, "audio", bank_name)
        os.makedirs(out, exist_ok=True)
        custom = [i for i in mod_bank.order if i in cur_bank.media and mod_bank.media[i] != cur_bank.media[i]]
        gone = [i for i in mod_bank.order if i not in cur_bank.media]
        print(f"{full} (current from {src})")
        print(f"  {len(custom)} custom, {len(gone)} old game sounds no longer in the bank (skipped)")
        preview = os.path.join(ROOT, "audio", "preview")
        os.makedirs(preview, exist_ok=True)
        for i in custom:
            wem = mod_bank.media[i]
            open(os.path.join(out, f"{i}.wem"), "wb").write(wem)
            if wem_desc(wem).startswith("pcm"):
                open(os.path.join(preview, f"{bank_name}_{i}.wav"), "wb").write(pcm_wem_to_wav(wem))
            print(f"  {i}: {wem_desc(wem)} (game has {wem_desc(cur_bank.media[i])})")


if __name__ == "__main__":
    main()
