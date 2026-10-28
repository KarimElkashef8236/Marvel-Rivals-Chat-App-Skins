"""Find the newest copy of a file across the game's legacy paks (patch paks win)."""
import glob
import os
import re

from paths import DEFAULT_PAKS
from rivalspak import Pak


def _order(path):
    name = os.path.basename(path)
    m = re.match(r"Patch_-Windows_([\d.]+)_P\.pak$", name, re.I)
    if m:
        return (1, tuple(int(x) for x in m.group(1).split(".")))
    return (0, ())


class GameFiles:
    def __init__(self, paks_dir=DEFAULT_PAKS):
        if not os.path.isdir(paks_dir):
            raise SystemExit(f"game Paks folder not found: {paks_dir} (use --game)")
        paks = [p for p in glob.glob(os.path.join(paks_dir, "*.pak")) if "Windows" in os.path.basename(p)]
        self.paks = [Pak(p) for p in sorted(paks, key=_order, reverse=True)]

    def find(self, full_path):
        """full_path like Marvel/Content/WwiseAudio/bnk_sfx_1018001.bnk (loose files only, not packages)"""
        for pak in self.paks:
            mount = pak.mount.replace("../../../", "")
            if not full_path.startswith(mount):
                continue
            rel = full_path[len(mount):]
            if rel in pak.files:
                return pak, rel
            if rel in pak.no_location:
                return None, None  # a newer patch deleted it
        return None, None

    def read(self, full_path):
        pak, rel = self.find(full_path)
        if pak is None:
            raise FileNotFoundError(f"{full_path} isn't in the game anymore")
        return pak.read(rel), os.path.basename(pak.path)
