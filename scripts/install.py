"""Copy the built mods into the game's ~mods folder.

    python scripts/install.py                        Dr Whatsapp (Strange): skin + sounds
    python scripts/install.py --obfuscated           Strange with the obfuscated skin instead
    python scripts/install.py --hero ironman         WhatsApp Iron Man: skin + sounds
    python scripts/install.py --hero ironman --beams Iron Man plus the optional green beams
    python scripts/install.py --hero magneto         Discord Magneto: skin + sounds
    python scripts/install.py --hero magneto --effects   Magneto plus the optional blurple effects
    python scripts/install.py --hero both            Strange and Iron Man
    python scripts/install.py --hero all             all three heroes (add --beams / --effects for the extras)
    python scripts/install.py --hero ironman --uninstall   remove that hero's files (beams / effects too)
"""
import argparse
import glob
import os
import shutil
import subprocess

from paths import DEFAULT_PAKS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = {
    "strange": ("DrWhatsapp_9999999_P.*", "68_DoctorWhatsappSounds_9999999_P.pak"),
    "ironman": ("IronWhatsapp_9999999_P.*", "69_IronWhatsappSounds_9999999_P.pak", "IronWhatsappBeams_9999999_P.*"),
    "magneto": ("DiscordMagneto_9999999_P.*", "70_DiscordMagnetoSounds_9999999_P.pak", "DiscordMagnetoFX_9999999_P.*"),
}
GROUPS = {"both": ("strange", "ironman"), "all": ("strange", "ironman", "magneto")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS, help="the game's Content\\Paks folder")
    ap.add_argument("--hero", choices=("strange", "ironman", "magneto", "both", "all"), default="strange")
    ap.add_argument("--obfuscated", action="store_true", help="Strange: use the obfuscated skin")
    ap.add_argument("--beams", action="store_true", help="Iron Man: also install the optional green beams")
    ap.add_argument("--effects", action="store_true", help="Magneto: also install the optional blurple effects")
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()
    heroes = GROUPS.get(args.hero, (args.hero,))

    if not os.path.exists(os.path.join(args.game, "pakchunk0-Windows.pak")):
        raise SystemExit(f"that's not the game's Paks folder: {args.game} (use --game)")
    running = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Marvel-Win64-Shipping.exe", "/NH"],
                             capture_output=True, text=True).stdout
    if "Marvel-Win64-Shipping.exe" in running:
        raise SystemExit("close Marvel Rivals first, it keeps the mod files open while it runs")
    mods = os.path.join(args.game, "~mods")
    os.makedirs(mods, exist_ok=True)
    for hero in heroes:
        for pattern in FILES[hero]:
            for f in glob.glob(os.path.join(mods, pattern)):
                os.remove(f)
    if args.uninstall:
        print(f"removed {' and '.join(heroes)} from {mods}")
        return

    files = []
    if "strange" in heroes:
        skin_dir = os.path.join(ROOT, "dist", "fallback-obfuscated" if args.obfuscated else "~mods")
        files += glob.glob(os.path.join(skin_dir, "DrWhatsapp_9999999_P.*"))
        files.append(os.path.join(ROOT, "dist", "~mods", "68_DoctorWhatsappSounds_9999999_P.pak"))
    if "ironman" in heroes:
        files += glob.glob(os.path.join(ROOT, "ironman", "dist", "~mods", "IronWhatsapp_9999999_P.*"))
        files.append(os.path.join(ROOT, "ironman", "dist", "~mods", "69_IronWhatsappSounds_9999999_P.pak"))
        if args.beams:
            files += glob.glob(os.path.join(ROOT, "ironman", "dist", "optional-beams", "IronWhatsappBeams_9999999_P.*"))
    if "magneto" in heroes:
        files += glob.glob(os.path.join(ROOT, "magneto", "dist", "~mods", "DiscordMagneto_9999999_P.*"))
        files.append(os.path.join(ROOT, "magneto", "dist", "~mods", "70_DiscordMagnetoSounds_9999999_P.pak"))
        if args.effects:
            files += glob.glob(os.path.join(ROOT, "magneto", "dist", "optional-effects", "DiscordMagnetoFX_9999999_P.*"))
    for f in files:
        shutil.copy2(f, mods)
        print(f"copied {os.path.basename(f)}")

    win64 = os.path.join(args.game, "..", "..", "Binaries", "Win64")
    needed = {
        "dsound.dll": "Ultimate ASI Loader (v7.7.0, 9.x reportedly doesn't work with the bypass)",
        "plugins/*signature*bypass*.asi": "UTOC Signature Bypass, nexusmods.com/marvelrivals/mods/2940",
        "plugins/*unmount*.asi": "Unmount Blocker, nexusmods.com/marvelrivals/mods/12735",
    }
    for pattern, what in needed.items():
        if not glob.glob(os.path.join(win64, pattern)):
            print(f"heads up, can't find {pattern} in Binaries\\Win64: {what}")


if __name__ == "__main__":
    main()
