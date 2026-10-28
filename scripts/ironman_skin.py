"""Build the WhatsApp Iron Man skin (default costume 1034001) as an IoStore mod.

The armour's colour (_D), glow (_E) and specular colour (_S) textures are pulled from the game,
recoloured (red -> WhatsApp greens, gold -> white, cyan glow -> green), get the logo overlays from
ironman/decals on the stomach and back, and their mip pixels are rewritten in place as DXT1. Headers
stay exactly as the game cooked them. Tony's face and eyes (Head_02, Eyes_01) are left alone.

Lower mips are averaged the way the game's own chains are: in linear light.

    python scripts/ironman_skin.py [--game <Paks dir>]
"""
import argparse
import glob
import os
import shutil
import subprocess

import numpy as np

import bc1
import png
import ue_texture
from paths import DEFAULT_PAKS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RETOC = os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")
WORK = os.path.join(ROOT, "work", "ironman_skin")
COSTUME = "Marvel/Content/Marvel/Characters/1034/1034001"
TEXTURES = [
    "Textures/T_1034001_Body", "Textures/T_1034001_Equip_01", "Textures/T_1034001_Equip_02",
    "Textures/T_1034001_Equip_03", "Textures/T_1034001_Equip_04", "Textures/T_1034001_Equip_06",
    "Textures/T_1034001_Head_01",
    "Weapons/EnergyBeamEmitter/Textures/T_1034001_EnergyBeamEmitter_Weapon",
    "Weapons/FloatingGun/Textures/T_1034001_FloatingGun_Weapon_01",
    "Weapons/FloatingGun/Textures/T_1034001_FloatingGun_Weapon_02",
    "Weapons/Railgun/Textures/T_1034001_Railgun_Weapon_01", "Weapons/Railgun/Textures/T_1034001_Railgun_Weapon_02",
]
MOD = "IronWhatsapp"

GREEN = np.array([0x25, 0xD3, 0x66], np.float32)
DARKTEAL = np.array([0x07, 0x5E, 0x54], np.float32)
WHITE = np.array([245, 245, 245], np.float32)
MINT = np.array([0xDC, 0xF8, 0xC6], np.float32)
GLOW = np.array([110, 255, 160], np.float32)


def _hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4))
    return h * 60.0, s, mx


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def recolor_diffuse(img):
    """red plates -> dark teal / green / mint by brightness, gold -> white, cyan -> mint"""
    rgb = img.astype(np.float32) / 255.0
    h, s, v = _hsv(rgb)
    hd = np.abs(h - 355) % 360
    hd = np.minimum(hd, 360 - hd)
    red = (_smooth(s, 0.22, 0.42) * (1 - _smooth(hd, 28, 48)))[..., None]
    gold = (_smooth(s, 0.25, 0.45) * _smooth(h, 18, 26) * (1 - _smooth(h, 52, 62)))[..., None]
    cyan = (_smooth(s, 0.35, 0.55) * _smooth(h, 160, 170) * (1 - _smooth(h, 200, 210)))[..., None]
    t = np.clip(v[..., None] / 0.66, 0, 1.4)
    g = np.where(t < 0.55, DARKTEAL * (t / 0.55), DARKTEAL + (GREEN - DARKTEAL) * np.clip((t - 0.55) / 0.45, 0, 1))
    g = np.where(t > 1.0, GREEN + (MINT - GREEN) * np.clip((t - 1.0) / 0.4, 0, 1), g) / 255.0
    w = WHITE / 255.0 * np.clip(v[..., None] / 0.72, 0, 1.15) ** 0.8
    m = MINT / 255.0 * np.clip(v[..., None] / 0.85, 0, 1.1)
    out = rgb * (1 - red) + g * red
    out = out * (1 - gold) + w * gold
    out = out * (1 - cyan) + m * cyan
    return np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)


def recolor_emissive(img):
    """coloured glow -> WhatsApp green glow with the same brightness. Grey masks get their colour from
    the material instead, so those are left alone (recolouring a grey mask could dim the glow)."""
    rgb = img.astype(np.float32)
    lum = rgb.max(-1, keepdims=True)
    _, s, v = _hsv(rgb / 255.0)
    lit = v > 0.1
    if not lit.any() or s[lit].mean() < 0.15:
        return None
    return np.clip(GLOW * lum / 255.0, 0, 255).astype(np.uint8)


def downsample(f):
    """2x2 box average in float, no rounding between mip levels"""
    h, w = f.shape[:2]
    if h > 1:
        f = (f[0::2] + f[1::2]) / 2
    if w > 1:
        f = (f[:, 0::2] + f[:, 1::2]) / 2
    return f


def srgb_to_linear(img):
    x = img.astype(np.float64) / 255.0
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb8(f):
    s = np.where(f <= 0.0031308, f * 12.92, 1.055 * np.maximum(f, 0) ** (1 / 2.4) - 0.055)
    return np.clip(s * 255 + 0.5, 0, 255).astype(np.uint8)


# module, mips averaged in linear light. The game's own mip chains show which: its DXT1 maps (_D, _E and _S alike)
# match a 2x2 average done in linear light (sRGB -> linear -> average -> sRGB), a plain average of the stored
# values comes out darker the smaller the mip
CODECS = {"PF_DXT1": (bc1, True)}


def write_mips(src, dst, new):
    """rewrite every mip the game ships from the new top mip image"""
    pf, table = ue_texture.mips(src)
    codec, linear = CODECS[pf]
    payloads = {}
    cur = srgb_to_linear(new) if linear else new.astype(np.float64)
    for mip in [t for t in table if t["where"] != "uptnl"]:
        while cur.shape[0] > mip["h"] or cur.shape[1] > mip["w"]:
            cur = downsample(cur)
        if cur.shape[:2] == new.shape[:2]:
            img = new
        else:
            img = linear_to_srgb8(cur) if linear else np.clip(cur + 0.5, 0, 255).astype(np.uint8)
        payloads[mip["index"]] = codec.encode(img)
    ue_texture.write(src, dst, payloads)


def retoc(*args):
    subprocess.run([RETOC, *args], check=True, stdout=subprocess.DEVNULL)


def build_texture(src, dst, kind, overlay):
    pf, table = ue_texture.mips(src)
    if pf not in CODECS:
        print(f"  {os.path.basename(src)}: {pf}, not DXT1, left vanilla")
        return None
    present = [m for m in table if m["where"] != "uptnl"]
    top = present[0]
    img = bc1.decode(ue_texture.read_mip(src, top), top["w"], top["h"])
    if kind in ("D", "S"):  # _S is a coloured specular copy of _D
        new = recolor_diffuse(img)
        if overlay is not None:
            a = overlay[..., 3:4].astype(np.float32) / 255.0
            new = np.clip(new * (1 - a) + overlay[..., :3] * a + 0.5, 0, 255).astype(np.uint8)
    else:
        new = recolor_emissive(img)
        if new is None:
            return None
        if overlay is not None:  # no old glow shining through the logo
            new = (new * (1 - overlay[..., 3:4].astype(np.float32) / 255.0)).astype(np.uint8)
    changed = (np.abs(new.astype(int) - img.astype(int)).max(-1) > 24).mean()
    if changed < 0.002:
        return None
    write_mips(src, dst, new)
    return changed, new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS)
    args = ap.parse_args()
    shutil.rmtree(WORK, ignore_errors=True)
    src_dir, raw = os.path.join(WORK, "game"), os.path.join(WORK, MOD)
    filters = []
    for t in TEXTURES:
        for kind in ("D", "E", "S"):
            filters += ["--filter", f"../../../{COSTUME}/{t}_{kind}.uasset"]
    retoc("unpack", os.path.join(args.game, "pakchunkCharacter-Windows.utoc"), *filters, "--output", src_dir,
          "--game-paks-dir", args.game)
    preview = os.path.join(ROOT, "ironman", "preview", "textures")
    os.makedirs(preview, exist_ok=True)
    for t in TEXTURES:
        for kind in ("D", "E", "S"):
            src = os.path.join(src_dir, COSTUME, f"{t}_{kind}")
            if not os.path.exists(src + ".uasset"):
                continue
            name = os.path.basename(t)
            dec = os.path.join(ROOT, "ironman", "decals", f"{name}_D.png")
            overlay = png.read(dec) if os.path.exists(dec) else None
            res = build_texture(src, os.path.join(raw, COSTUME, f"{t}_{kind}"), kind, overlay)
            if res is None:
                print(f"  {name}_{kind}: nothing to recolour, left vanilla")
                continue
            png.write(os.path.join(preview, f"{name}_{kind}.png"), res[1])
            print(f"  {name}_{kind}: {res[0] * 100:.0f}% of pixels recoloured{' + logo' if overlay is not None else ''}")
    out = os.path.join(ROOT, "ironman", "dist", "~mods")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, f"{MOD}_9999999_P.*")):
        os.remove(f)
    retoc("pack", raw, "--output", out)
    print(f"wrote {out}\\{MOD}_9999999_P.pak/.utoc/.ucas")


if __name__ == "__main__":
    main()
