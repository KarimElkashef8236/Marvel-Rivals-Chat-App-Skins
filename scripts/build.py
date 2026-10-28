"""Rebuild everything in dist/ from the original Season 1.5 rars in original/.

    python scripts/build.py [--game "<...>\\MarvelGame\\Marvel\\Content\\Paks"]

Run it again after a game update so the sounds get rebuilt on the new banks.
"""
import argparse
import glob
import hashlib
import io
import os
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile

from paths import DEFAULT_PAKS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORK = os.path.join(ROOT, "work")
DIST = os.path.join(ROOT, "dist")
RETOC = os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")
RETOC_URL = ("https://github.com/natimerry/repak-rivals/releases/download/v3.9.3/"
             "retoc-rivals-cli-x86_64-pc-windows-msvc.zip")
RETOC_SHA256 = "587c5b319dfeb1a56052e4fa77d8a0795e19f217e467315ee7a06bde26e99357"
JUNK = ("patched_files", "chunknames")  # repak-rivals strips these, netease ac flags them


def get_retoc():
    if os.path.exists(RETOC):
        return
    print(f"downloading retoc-rivals-cli v3.9.3 from {RETOC_URL}")
    data = urllib.request.urlopen(RETOC_URL).read()
    if hashlib.sha256(data).hexdigest() != RETOC_SHA256:
        raise SystemExit("retoc-rivals-cli download failed the sha256 check")
    zipfile.ZipFile(io.BytesIO(data)).extractall(os.path.dirname(RETOC))


def retoc(*args):
    subprocess.run([RETOC, *args], check=True)


def first_prop_index(uexp):
    # cooked textures use unversioned properties, the first u16 is the first header fragment
    # and its low 7 bits are how many schema slots get skipped before the first saved value
    return struct.unpack_from("<H", open(uexp, "rb").read(), 0)[0] & 0x7F


def fix_texture_props(raw, game_paks):
    """Season 2 added OriginalWidth, OriginalHeight and LineCountPerFrame to Texture2D
    right before ImportedSize, so every property the Season 1.5 textures saved now sits
    3 slots later. Without this the game reads the textures wrong."""
    probe = os.path.join(WORK, "game_tex")
    retoc("unpack", os.path.join(game_paks, "pakchunkCharacter-Windows.utoc"), "--filter",
          "../../../Marvel/Content/Marvel/Characters/1018/1018001/Texture/T_1018001_Body_D.uasset",
          "--output", probe, "--game-paks-dir", game_paks)
    game_first = first_prop_index(glob.glob(os.path.join(probe, "**", "T_1018001_Body_D.uexp"), recursive=True)[0])
    if game_first != 7:
        raise SystemExit(f"the game's Texture2D layout changed again (ImportedSize is at {game_first} now, "
                         f"this fix expects 7), the texture fix needs updating")
    for uexp in glob.glob(os.path.join(raw, "**", "T_1018001_*.uexp"), recursive=True):
        b = bytearray(open(uexp, "rb").read())
        frag = struct.unpack_from("<H", b, 0)[0]
        if frag & 0x7F != 4:
            raise SystemExit(f"{os.path.basename(uexp)} doesn't look like a Season 1.5 texture")
        struct.pack_into("<H", b, 0, (frag & ~0x7F) | 7)
        open(uexp, "wb").write(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS, help="the game's Content\\Paks folder")
    args = ap.parse_args()

    get_retoc()
    # only clear this build's own folders, the Iron Man and Magneto builds keep their stuff in work\ too
    for d in ("orig", "DrWhatsapp", "game_tex"):
        shutil.rmtree(os.path.join(WORK, d), ignore_errors=True)
    orig = os.path.join(WORK, "orig")
    os.makedirs(orig)
    for rar in glob.glob(os.path.join(ROOT, "original", "*.rar")):
        subprocess.run(["tar", "-xf", rar, "-C", orig], check=True)
    skin_pak = os.path.join(orig, "DrWhatsapp_9999999_P.pak")
    sound_pak = os.path.join(orig, "68_DoctorWhatsappSounds_9999999_P.pak")

    # skin: legacy pak -> raw files -> iostore (.pak/.utoc/.ucas)
    raw = os.path.join(WORK, "DrWhatsapp")
    retoc("unpack", skin_pak, "--output", raw)
    for j in JUNK:
        if os.path.exists(os.path.join(raw, j)):
            os.remove(os.path.join(raw, j))
    fix_texture_props(raw, args.game)
    mods = os.path.join(DIST, "~mods")
    fallback = os.path.join(DIST, "fallback-obfuscated")
    for d in (mods, fallback):
        os.makedirs(d, exist_ok=True)
        for f in glob.glob(os.path.join(d, "DrWhatsapp_9999999_P.*")):
            os.remove(f)
    retoc("pack", raw, "--output", mods)
    retoc("pack", raw, "--output", fallback, "--obfuscate", "--game-paks-dir", args.game)

    # sounds: the ult clips come from the old mod, every other ability gets its WhatsApp sound
    # from audio/sounds.json, then it all goes into the current game banks
    if not glob.glob(os.path.join(ROOT, "audio", "bnk_*", "*.wem")):
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "extract_wems.py"), sound_pak, "--game", args.game],
                       check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "make_sounds.py"), "--game", args.game], check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_audio.py"), "--game", args.game, "--out", mods],
                   check=True)
    print("done, files are in dist\\~mods")


if __name__ == "__main__":
    main()
