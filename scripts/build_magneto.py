"""Rebuild everything in magneto/dist from the game files.

    python scripts/build_magneto.py [--game "<...>\\MarvelGame\\Marvel\\Content\\Paks"]

Makes the skin (DiscordMagneto_9999999_P), the sounds (70_DiscordMagnetoSounds_9999999_P.pak) and the
optional blurple effects (optional-effects\\DiscordMagnetoFX_9999999_P).
Run it again after a game update. Needs tools\\retoc-rivals (run scripts\\build.py once, it downloads it).
"""
import argparse
import os
import subprocess
import sys

from paths import DEFAULT_PAKS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(script, *args):
    subprocess.run([sys.executable, os.path.join(HERE, script), *args], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS, help="the game's Content\\Paks folder")
    args = ap.parse_args()
    if not os.path.exists(os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")):
        raise SystemExit("run python scripts\\build.py once first, it gets retoc-rivals-cli")
    config = os.path.join(ROOT, "magneto", "sounds.json")
    run("magneto_skin.py", "--game", args.game)
    run("make_sounds.py", "--config", config, "--game", args.game)
    run("build_audio.py", "--config", config, "--game", args.game, "--out", os.path.join(ROOT, "magneto", "dist", "~mods"))
    run("magneto_vfx.py", "--game", args.game)
    print("done, files are in magneto\\dist")


if __name__ == "__main__":
    main()
