"""Build the ability sounds from a hero's sounds json (default audio/sounds.json, Strange).

For every ability, the main sound of each listed event (plus the _p2 ally and _p3 enemy
versions of it) gets the clip (from <dir>/<src>, src is "whatsapp" unless the json says
otherwise), and the extra layers that played on top of it get silence. An ability can also
list the exact media to replace and to mute instead ("replace", "mute"), which the Iron Man
json does. The game's own pitch on those sounds is undone (unless "pitch_fix" is false) and
each clip is leveled against the game's volume on it, so they all land around target_db in
game. "even_variants" is for when the game dropped some variants from your own version of an
event but the ally/enemy versions still play them: those get leveled like the variants that are
still shared, so they don't come out quieter or louder than the rest.
"repeat" / "every" play the clip that many times, one every "every" seconds, and
"lead_in" puts that many seconds of silence before it in game ("prev_note" goes on the end
of the preview's file name). Writes <dir>/<bank name>/<media id>.wem, named previews in
<dir>/preview/ (how it should sound in game) and <dir>/SOUNDS.md.

    python scripts/make_sounds.py [--config ironman/sounds.json] [--game <Paks dir>]
"""
import argparse
import glob
import json
import os
import re

import numpy as np

from gamefiles import GameFiles
from hirc_map import HircMap
from mf_decode import decode, wav_bytes as raw_wav
from paths import DEFAULT_PAKS
from wem import RATE, process, read_wav, repitch, set_level, wav_bytes, wem_bytes
from wwise_bank import Bank

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STRANGE_BANK = "Marvel/Content/WwiseAudio/bnk_sfx_1018001.bnk"
SOUND_COL = {"whatsapp": "WhatsApp sound", "discord": "Discord sound"}


def resample(a, rate):
    """FFT resample to RATE, band limited like repitch"""
    n, m = len(a), int(round(len(a) * RATE / rate))
    spec = np.fft.rfft(a, axis=0)
    out = np.zeros((m // 2 + 1, a.shape[1]), dtype=complex)
    k = min(len(spec), len(out))
    out[:k] = spec[:k]
    return np.fft.irfft(out, n=m, axis=0) * (m / n)


def load_clip(src_dir, name):
    src = glob.glob(os.path.join(src_dir, name + ".*"))
    if not src:
        raise SystemExit(f"no {src_dir}\\{name}.* file")
    src = src[0]
    if src.endswith(".wav"):
        try:
            return read_wav(src)
        except ValueError:
            pass
    cache = os.path.join(ROOT, "work", "decoded", os.path.basename(os.path.dirname(src_dir)), name + ".wav")
    if not os.path.exists(cache):
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        ch, rate, bits, pcm = decode(os.path.abspath(src))
        if rate == RATE:
            open(cache, "wb").write(raw_wav(ch, rate, bits, pcm))
        else:  # some mp3s are 48 kHz: the cache gets the 44.1 kHz stereo version
            a = np.frombuffer(pcm, dtype="<i2").astype(np.float64).reshape(-1, ch)
            a = np.repeat(a, 2, axis=1) if ch == 1 else a[:, :2]
            open(cache, "wb").write(wav_bytes(resample(a, rate)))
    return read_wav(cache)


def ring(clip, repeat, every):
    """the clip repeat times, one starting every `every` seconds (added on top if they overlap)"""
    step = int(round(every * RATE))
    body = np.zeros(((repeat - 1) * step + len(clip), 2))
    for k in range(repeat):
        body[k * step:k * step + len(clip)] += clip
    return body


def process_silence():
    return np.zeros((int(0.05 * RATE), 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "audio", "sounds.json"))
    ap.add_argument("--game", default=DEFAULT_PAKS)
    args = ap.parse_args()
    cfg = json.load(open(args.config, encoding="utf-8"))
    base_dir = os.path.join(ROOT, cfg.get("dir", "audio"))
    bank_path = cfg.get("bank", STRANGE_BANK)
    out = os.path.join(base_dir, os.path.splitext(os.path.basename(bank_path))[0])
    preview_dir = os.path.join(base_dir, "preview")
    src_dir = os.path.join(base_dir, cfg.get("src", "whatsapp"))
    os.makedirs(out, exist_ok=True)
    os.makedirs(preview_dir, exist_ok=True)

    game = GameFiles(args.game)
    bank = Bank(game.read(bank_path)[0])
    names = set()
    for a in cfg["abilities"]:
        for e in a["events"] + a.get("mute_events", []):
            names.update({e, e + "_p2", e + "_p3"})
    hm = HircMap(bank, names)
    by_name = {n: eid for eid, n in hm.events().items()}

    def variants(e):
        if e not in by_name:
            raise SystemExit(f"event {e} isn't in the current bank")
        return [v for v in (e, e + "_p2", e + "_p3") if v in by_name]

    keep = set(cfg.get("keep", []))
    never = {int(k) for k in cfg.get("never_touch", {})}
    used, extra, rows = {}, set(), []
    for f in glob.glob(os.path.join(preview_dir, "*.wav")):  # only the numbered previews made here
        if re.match(r"\d+ ", os.path.basename(f)):
            os.remove(f)
    for f in glob.glob(os.path.join(out, "*.wem")):
        if not os.path.basename(f)[:-4].isdigit() or int(os.path.basename(f)[:-4]) not in keep:
            os.remove(f)
    target = cfg.get("target_db", -22.0)
    for i, a in enumerate(cfg["abilities"], 1):
        clip = process(load_clip(src_dir, a["sound"]), a.get("start"), a.get("end"))
        if a.get("repeat", 1) > 1 and not a.get("every", 0) > 0:
            raise SystemExit(f"{a['name']}: repeat {a['repeat']} needs every > 0")
        if a.get("repeat"):  # rings: the clip repeat times, one every `every` s
            clip = ring(clip, a["repeat"], a.get("every", 0.0))
        game_clip = clip
        if a.get("lead_in"):  # silence before it in game only, the preview starts on the clip
            game_clip = np.concatenate([np.zeros((int(round(a["lead_in"] * RATE)), 2)), clip])
        if a.get("pad_to"):  # loops: keep the gap before the clip repeats
            pad = int(a["pad_to"] * RATE) - len(game_clip)
            if pad > 0:
                game_clip = np.concatenate([game_clip, np.zeros((pad, 2))])
        explicit = [int(m) for m in a.get("replace", [])]
        if explicit and not all(any(m in hm.media_chains(by_name[v]) for e in a["events"] for v in variants(e))
                                for m in explicit):
            raise SystemExit(f"{a['name']}: a media in 'replace' isn't played by its events any more")
        rendered, notes = {}, set()
        for e in a["events"]:
            base = hm.media_chains(by_name[e])
            base_main = [m for m in explicit if m in base] if explicit else hm.split_event(by_name[e])[0]
            ref_vol = sum(base[m][0] for m in base_main) / len(base_main) if base_main else None
            for v in variants(e):
                chains = hm.media_chains(by_name[v])
                if explicit:
                    main = [m for m in explicit if m in chains]
                else:
                    main, x = hm.split_event(by_name[v])
                    extra.update(x)
                for m in main:
                    if m in keep:
                        continue
                    if m in never:
                        raise SystemExit(f"{a['name']}: media {m} is on the never_touch list")
                    if m in used and used[m] != a["name"]:
                        raise SystemExit(f"media {m} is in both {used[m]} and {a['name']}")
                    if m in used:
                        continue
                    used[m] = a["name"]
                    # the game adds its own volume and pitch on top of each sound. Undo the pitch, and
                    # level each clip so it lands at the same loudness for the player using it. Ally and
                    # enemy versions keep the game's own offsets from that.
                    vol, pitch = base[m] if m in base_main else (ref_vol if ref_vol is not None else chains[m][0],
                                                                 chains[m][1])
                    shared = [k for k in main if k in base_main]
                    if a.get("even_variants") and m not in base_main and shared:
                        # a variant only the ally/enemy version still plays gets leveled like the ones it
                        # shares with your own version, so every variant comes out just as loud
                        vol = chains[m][0] - sum(chains[k][0] - base[k][0] for k in shared) / len(shared)
                    if not a.get("pitch_fix", True):
                        pitch = 0
                    if pitch:
                        notes.add(f"{-pitch:+.0f} cents")
                    level = max(min(target - vol + a.get("gain_db", 0.0), cfg.get("max_rms_db", -8.0)), -40.0)
                    key = (round(pitch), round(level, 1))
                    if key not in rendered:
                        rendered[key] = wem_bytes(set_level(repitch(game_clip, -pitch), level,
                                                            limit_db=cfg.get("limit_db", 0.0)))
                    open(os.path.join(out, f"{m}.wem"), "wb").write(rendered[key])
        for e in a.get("mute_events", []):  # sounds that fire together with this one, silenced
            for v in variants(e):
                m, x = hm.split_event(by_name[v])
                extra.update(m + x)
        extra.update(int(m) for m in a.get("mute", []))
        preview = re.sub(r'[\\/:*?"<>|]', "-", f"{i:02d} {a['key']} - {a['name']}{a.get('prev_note', '')}.wav")
        open(os.path.join(preview_dir, preview), "wb").write(wav_bytes(clip))
        count = sum(1 for n in used.values() if n == a["name"])
        rows.append((a, len(clip) / RATE, count, preview))
        fix = f"  (pre-shifted {', '.join(sorted(notes))})" if notes else ""
        if len(game_clip) != len(clip):
            fix += f"  (in game {len(game_clip) / RATE:.2f}s)"
        print(f"{a['key']:11} {a['name']:44} {a['sound']:32} {len(clip) / RATE:4.2f}s  {count} media{fix}")

    for k in cfg.get("keep_previews", []):
        wem = open(os.path.join(base_dir, k["file"]), "rb").read()
        clip = np.frombuffer(wem[108:], dtype="<i2").astype(np.float64).reshape(-1, 2)
        open(os.path.join(preview_dir, k["name"] + ".wav"), "wb").write(wav_bytes(clip))

    # layers that played under the old sound get silence so the new clip isn't doubled or muddied
    silence = wem_bytes(process_silence())
    muted = sorted(extra - set(used) - keep - never)
    for m in muted:
        open(os.path.join(out, f"{m}.wem"), "wb").write(silence)
    print(f"muted {len(muted)} extra layers")

    rel = os.path.relpath(args.config, ROOT).replace(os.sep, "/")
    with open(os.path.join(base_dir, "SOUNDS.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# Ability sounds\n\nMade by `scripts/make_sounds.py` from `{rel}`. "
                 f"Previews are in `{cfg.get('dir', 'audio')}/preview/`.\n\n")
        col = SOUND_COL.get(cfg.get("src", "whatsapp"), "Sound")
        fh.write(f"| # | Key | Ability | {col} | Length | Plays on |\n| --- | --- | --- | --- | --- | --- |\n")
        for i, (a, secs, n, preview) in enumerate(rows, 1):
            fh.write(f"| {i} | {a['key']} | {a['name']} | {a['sound_desc']} | {secs:.1f}s | {a['when']} |\n")
        if cfg.get("keep_desc"):
            fh.write("\nKept from the original mod: " + cfg["keep_desc"] + "\n")


if __name__ == "__main__":
    main()
