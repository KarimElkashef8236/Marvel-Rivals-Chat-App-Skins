"""Put a hero's custom sounds into the game's current banks and pack them.

Same swap the original mod did: the whole clip replaces the media entry in the
bank and the HIRC is left alone. Sounds that stream get the clip at their stream
path too. Output is a legacy pak (audio mods stay legacy).
"""
import argparse
import json
import os

from gamefiles import GameFiles
from paths import DEFAULT_PAKS
from rivalspak import write_pak
from wwise_bank import Bank

ROOT = os.path.join(os.path.dirname(__file__), "..")
STRANGE_BANKS = {
    "bnk_vo_1018001": "Marvel/Content/WwiseAudio/English(US)/bnk_vo_1018001.bnk",
    "bnk_sfx_1018001": "Marvel/Content/WwiseAudio/bnk_sfx_1018001.bnk",
}
STRANGE_PAK = "68_DoctorWhatsappSounds_9999999_P.pak"


def loose_path(game, bank_path, mid):
    root = "Marvel/Content/WwiseAudio/"
    lang = os.path.dirname(bank_path[len(root):])
    for folder in ([f"Media/{lang}"] if lang else []) + ["Media"]:
        path = f"{root}{folder}/{str(mid)[:2]}/{mid}.wem"
        if game.find(path)[0]:
            return path
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "audio", "sounds.json"))
    ap.add_argument("--game", default=DEFAULT_PAKS)
    ap.add_argument("--out", default=os.path.join(ROOT, "dist", "~mods"))
    args = ap.parse_args()
    cfg = json.load(open(args.config, encoding="utf-8"))
    banks = {os.path.splitext(os.path.basename(cfg["bank"]))[0]: cfg["bank"]} if "bank" in cfg else STRANGE_BANKS
    pak_name = cfg.get("pak", STRANGE_PAK)

    game = GameFiles(args.game)
    files, missing = {}, []
    for bank_name, full in banks.items():
        wem_dir = os.path.join(ROOT, cfg.get("dir", "audio"), bank_name)
        wems = {int(f[:-4]): open(os.path.join(wem_dir, f), "rb").read()
                for f in sorted(os.listdir(wem_dir)) if f.endswith(".wem")}
        data, src = game.read(full)
        bank = Bank(data)
        print(f"{full} (current from {src}, {len(bank.media)} media)")
        streamed = {s["sid"] for s in bank.sources() if s["stream"] != 0}
        for mid, wem in wems.items():
            if mid not in bank.media:
                missing.append(mid)
                print(f"  {mid}: NOT in the current bank, the game changed this sound id")
                continue
            print(f"  {mid}: {len(bank.media[mid])} -> {len(wem)} bytes")
            bank.set_media(mid, wem)
            if mid in streamed:
                # prefetch + stream sound: the bank now holds the whole clip, ship the same clip
                # where the game keeps the stream file so the two always match
                loose = loose_path(game, full, mid)
                if loose:
                    files[loose] = wem
                    print(f"    also {loose}")
        rebuilt = bank.build()
        check = Bank(rebuilt)
        assert all(check.media[m] == w for m, w in wems.items() if m not in missing)
        files[full] = rebuilt

    os.makedirs(args.out, exist_ok=True)
    out = os.path.join(args.out, pak_name)
    write_pak(out, files)
    print(f"wrote {out}")
    if missing:
        raise SystemExit(f"{len(missing)} sound ids are gone from the game, those sounds need remapping")


if __name__ == "__main__":
    main()
