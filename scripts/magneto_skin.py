"""Build the Discord Magneto skin (default costume 1037001) as an IoStore mod.

Discord colours: the red trim goes blurple and the metal goes Discord greys, the helmet dome turns blurple with
white face stripes, the cape turns blurple with a white Clyde (the Discord logo) and a green online dot where the
old helmet emblem was, the inside of the cape goes Discord dark grey, the belt buckle gets a Clyde badge and the
rusty parts of the sword, ring and cannon go blurple. The logos and masks come from magneto/decals.

The colour (_D) and specular colour (_S) textures are pulled from the game, recoloured, and their mip pixels are
rewritten in place. Headers stay exactly as the game cooked them. _S is the colour of the shine (a darker copy of
_D with the same red), so it gets the new colour of _D at its own old brightness: the hue moves, the shine doesn't
go up. Where the old emblems were (back of the cape, inside the belt buckle) the _S, _ORM and _N maps are painted
over too, so the old emblem doesn't show through in the shine or the bumps. The red glow along the cape edges goes
blurple (magneto_mats.py). His face, hair and skin stay vanilla. The far LOD uses the same textures
(magneto_lod.py checks that).

Shared textures: costume 1037102 uses these armour, cape and weapon textures directly, so it gets the Discord look
as well. Costume 1037100 uses the default belt and cape bump maps, so the relief of its own emblems goes flat
(colours unchanged). Costume 1037302's sword uses the default sword _D. The cannon's _D also colours Magneto's
rock effects, which pick up the slightly cooler Discord grey.

Lower mips are averaged the way the game's own chains are: in linear light for the DXT1 maps, plain for BC5.

    python scripts/magneto_skin.py [--game <Paks dir>]
"""
import argparse
import glob
import os
import shutil
import subprocess

import numpy as np

import bc1
import bc5
import magneto_lod
import magneto_mats
import png
import ue_texture
from paths import DEFAULT_PAKS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RETOC = os.path.join(ROOT, "tools", "retoc-rivals", "retoc-rivals-cli.exe")
WORK = os.path.join(ROOT, "work", "magneto_skin")
DECALS = os.path.join(ROOT, "magneto", "decals")
COSTUME = "Marvel/Content/Marvel/Characters/1037/1037001"
MOD = "DiscordMagneto"

# part: (folder, colour texture, specular colour texture or None)
PARTS = {
    "Equip_01": ("Textures", "T_1037001_Equip_01_D", "T_1037001_Equip_01_S"),   # helmet, arms, chest
    "Equip_02": ("Textures", "T_1037001_Equip_02_D", "T_1037001_Equip_02_S"),   # torso, belt
    "Equip_03": ("Textures", "T_1037001_Equip_03_D", "T_1037001_Equip_03_S"),   # cape outside
    "Equip_04": ("Textures", "T_1037001_Equip_04_D", "T_1037001_Equip_04_S"),   # legs, shoulders
    "Equip_05": ("Textures", "T_1037001_Equip_05_D", "T_1037001_Equip_05_S"),   # cape inside
    "Sword": ("Weapons/Sword/Textures", "T_EQPT_1037001_Sword_Weapon_D", None),
    "Ring": ("Weapons/Ring/Textures", "T_1037001_Ring_Weapon_D", "T_1037001_Ring_Weapon_S"),
    "Cannon": ("Weapons/PowerfulIronCcannon/Textures", "T_1037001_PowerfulIronCcannon_Weapon_01_D",
               "T_1037001_PowerfuilronCcannon_Weapon_01_S"),   # (sic) the game spells the _S that way
}
# the parts with an old emblem under a new logo: their bump (_N) and roughness/metal (_ORM) maps get it smoothed out
FLATTEN = {"Equip_02": ("T_1037001_Equip_02_N", "T_1037001_Equip_02_ORM"),
           "Equip_03": ("T_1037001_Equip_03_N", "T_1037001_Equip_03_ORM")}

# the round emblem in the middle of the belt buckle on T_1037001_Equip_02 (texels): centre x, y, radius of the
# dark inner disc the Clyde badge covers
BUCKLE = (272.56, 973.54, 33.5)


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255.0


BLURPLE = hexc("#5865F2")
WHITE = hexc("#F2F3F5")
CAPE_INSIDE = hexc("#2B2D31")
GREYS = ["#0B0C0E", "#1E1F22", "#2B2D31", "#313338", "#383A40", "#4E5058", "#80848E", "#B5BAC1", "#DBDEE1", "#F2F3F5"]
BLURPLES = ["#11132E", "#262B6B", "#3C45A5", "#5865F2", "#7984F5", "#A5ACF7", "#DCDFFC"]


def lum(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def _palette(names):
    cols = np.stack([hexc(n) for n in names])
    return lum(cols), cols


def ramp(x, ys, cols):
    x = np.clip(x, ys[0], ys[-1])
    out = np.empty(x.shape + (3,), np.float32)
    for k in range(3):
        out[..., k] = np.interp(x, ys, cols[:, k])
    return out


G_YS, G_COLS = _palette(GREYS)
B_YS, B_COLS = _palette(BLURPLES)


def hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    dd = np.maximum(d, 1e-6)
    h = np.zeros_like(mx)
    h = np.where(mx == b, (r - g) / dd + 4, h)
    h = np.where(mx == g, (b - r) / dd + 2, h)
    h = np.where(mx == r, ((g - b) / dd) % 6, h)
    return h * 60.0, s, mx


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def blend(a, b, m):
    return a * (1 - m[..., None]) + b * m[..., None]


def masks(rgb):
    """red paint and the light blue trim, soft 0..1, plus the value"""
    h, s, v = hsv(rgb)
    hd = np.abs(h - 355) % 360
    hd = np.minimum(hd, 360 - hd)
    red = smooth(s, 0.25, 0.45) * (1 - smooth(hd, 25, 40)) * smooth(v, 0.08, 0.2)
    blue = smooth(s, 0.18, 0.35) * smooth(h, 180, 190) * (1 - smooth(h, 235, 250)) * smooth(v, 0.2, 0.35)
    return red, blue, v


def blurple_from_value(v, ref, lift=0.0):
    """value relative to a typical lit pixel of that part -> blurple ramp (ref maps onto #5865F2)"""
    return ramp(lum(BLURPLE) * np.clip(v / ref, 0, 3) + lift, B_YS, B_COLS)


def grey_map(rgb):
    """same brightness, Discord greys"""
    return ramp(lum(rgb), G_YS, G_COLS)


def inpaint(img, hole, iters=3000, pad=40):
    """fill the hole pixels by diffusion from their surroundings (on the hole's bounding box only)"""
    ys, xs = np.nonzero(hole)
    y0, y1 = max(ys.min() - pad, 0), ys.max() + pad + 1
    x0, x1 = max(xs.min() - pad, 0), xs.max() + pad + 1
    out = img.copy()
    sub = out[y0:y1, x0:x1]
    h = hole[y0:y1, x0:x1]
    sub[h] = sub[~h].mean(0)
    for _ in range(iters):
        p = np.pad(sub, ((1, 1), (1, 1), (0, 0)), mode="edge")
        avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
        sub[h] = avg[h]
    return out


def armour(rgb, helmet=None):
    """Discord greys, red -> blurple, light blue trim -> blurple. helmet: blurple dome, red face stripes -> white"""
    red, blue, v = masks(rgb)
    res = blend(grey_map(rgb), blurple_from_value(v, 0.78), red)
    res = blend(res, blurple_from_value(v, 0.7, 0.05), blue)
    if helmet is not None:
        dome = blurple_from_value(lum(rgb), 0.62)
        white = ramp(np.clip(v / 0.78, 0, 1.2) * lum(WHITE) * 0.95, G_YS, G_COLS)
        res = blend(res, dome, helmet * (1 - red))
        res = blend(res, white, helmet * red)
    return res


def cape(rgb, emblem):
    """old helmet emblem painted out, then blurple by brightness"""
    y = lum(inpaint(rgb, emblem))
    return blurple_from_value(y, np.median(y[200:900, 250:780]))


def cape_inside(rgb):
    y = lum(rgb)
    return ramp(y / np.median(y[200:900, 250:780]) * lum(CAPE_INSIDE), G_YS, G_COLS)


def weapon(rgb):
    """Discord greys, the rusty red-brown parts -> blurple"""
    h, s, v = hsv(rgb)
    rust = smooth(s, 0.12, 0.25) * smooth(h, 0, 8) * (1 - smooth(h, 40, 55))
    return blend(grey_map(rgb), blurple_from_value(v, 0.45), rust)


def specular(s, d):
    """the colour of the new _D at the old specular brightness (never brighter than it was)"""
    while d.shape[0] > s.shape[0] or d.shape[1] > s.shape[1]:
        d = (d[0::2, 0::2] + d[1::2, 0::2] + d[0::2, 1::2] + d[1::2, 1::2]) / 4
    if d.shape[:2] != s.shape[:2]:
        raise SystemExit(f"_S is {s.shape[:2]}, _D is {d.shape[:2]}")
    tint = d / np.maximum(lum(d), 1e-3)[..., None]
    return np.clip(tint * lum(s)[..., None], 0, 1)


def overlay(img, name):
    """composite the RGBA logo overlay from magneto/decals, if there is one"""
    p = os.path.join(DECALS, f"{name}.png")
    if not os.path.exists(p):
        return img, None
    ov = png.read(p).astype(np.float32) / 255.0
    a = ov[..., 3:4]
    return img * (1 - a) + ov[..., :3] * a, a[..., 0]


def mask(name):
    return png.read(os.path.join(DECALS, f"{name}.png"))[..., 0] > 127


def cape_emblem(orm):
    """the old helmet emblem on the back of the cape: the mask from magneto/decals plus the emblem's own shape in
    the roughness map, which also catches the right end of the bar and a corner of the ring the mask misses"""
    win = np.zeros(orm.shape[:2], bool)
    win[60:480, 360:720] = True
    return mask("mask_emblem_T_1037001_Equip_03") | dilate(win & (orm[..., 1] < 95), 6)


def box_blur(img, r):
    p = np.pad(img, ((r + 1, r), (r + 1, r), (0, 0)), mode="edge").astype(np.float64)
    c = np.cumsum(np.cumsum(p, 0), 1)
    k = 2 * r + 1
    return ((c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)).astype(np.float32)


def bump_fill(img, hole, tile=64):
    """paint a shape out of the cape's normal map: smooth fill, then the fine woven bump pattern of the cloth (it
    repeats every 64 texels) is copied back in from the nearest repeat outside the hole"""
    out = inpaint(img, hole)
    detail = img - box_blur(img, 4)
    keep_out = dilate(hole, 4)
    todo = hole.copy()
    h, w = hole.shape
    shifts = sorted(((dy, dx) for dy in range(-8 * tile, 8 * tile + 1, tile) for dx in range(-8 * tile, 8 * tile + 1, tile)
                     if dy or dx), key=lambda d: d[0] ** 2 + d[1] ** 2)
    for dy, dx in shifts:
        ys, xs = np.nonzero(todo)
        if not len(ys):
            break
        sy, sx = ys + dy, xs + dx
        ok = (sy >= 0) & (sy < h) & (sx >= 0) & (sx < w)
        ys, xs, sy, sx = ys[ok], xs[ok], sy[ok], sx[ok]
        ok = ~keep_out[sy, sx]
        out[ys[ok], xs[ok]] += detail[sy[ok], sx[ok]]
        todo[ys[ok], xs[ok]] = False
    return out


def buckle_badge():
    """how much of each texel of T_1037001_Equip_02 the Clyde badge covers, inside the buckle ring only"""
    a = png.read(os.path.join(DECALS, "T_1037001_Equip_02_D.png"))[..., 3].astype(np.float32) / 255.0
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]].astype(np.float32)
    return a * (np.hypot(xx - BUCKLE[0], yy - BUCKLE[1]) < BUCKLE[2] + 1.5)


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


def pool(m):
    """a mask at the next mip size (a pixel counts if any of its 4 counts)"""
    h, w = m.shape
    if h > 1:
        m = m[0::2] | m[1::2]
    if w > 1:
        m = m[:, 0::2] | m[:, 1::2]
    return m


def dilate(m, n):
    out = m.copy()
    for _ in range(n):
        o = out.copy()
        o[1:] |= out[:-1]
        o[:-1] |= out[1:]
        o[:, 1:] |= out[:, :-1]
        o[:, :-1] |= out[:, 1:]
        out = o
    return out


# module, bytes per 4x4 block, channels, mips averaged in linear light. The game's own mip chains show which: its
# DXT1 maps (_D, _S and _ORM alike) match a 2x2 average done in linear light (sRGB -> linear -> average -> sRGB),
# a plain average of the stored values comes out darker the smaller the mip; its BC5 bump maps match a plain average
CODECS = {"PF_DXT1": (bc1, 8, 3, True), "PF_BC5": (bc5, 16, 2, False)}


def top_mip(src):
    """-> (pixel format, largest mip the game ships, decoded)"""
    pf, table = ue_texture.mips(src)
    if pf not in CODECS:
        raise SystemExit(f"{os.path.basename(src)}: {pf}, expected DXT1 or BC5")
    top = [m for m in table if m["where"] != "uptnl"][0]   # the optional 2048 mip isn't in any game container
    return pf, CODECS[pf][0].decode(ue_texture.read_mip(src, top), top["w"], top["h"])


def write_mips(src, dst, new, only=None):
    """rewrite every mip the game ships from the new top mip image. only: mask of the top mip, then just the
    4x4 blocks that touch it are encoded again and every other block keeps the game's bytes"""
    pf, table = ue_texture.mips(src)
    codec, bsize, _, linear = CODECS[pf]
    payloads, m = {}, only
    cur = srgb_to_linear(new) if linear else new.astype(np.float64)
    for mip in [t for t in table if t["where"] != "uptnl"]:
        while cur.shape[0] > mip["h"] or cur.shape[1] > mip["w"]:
            cur = downsample(cur)
            m = None if m is None else pool(m)
        if cur.shape[:2] == new.shape[:2]:
            img = new
        else:
            img = linear_to_srgb8(cur) if linear else np.clip(cur + 0.5, 0, 255).astype(np.uint8)
        data = codec.encode(img)
        if m is not None:
            bh, bw = max(1, (mip["h"] + 3) // 4), max(1, (mip["w"] + 3) // 4)
            pm = np.pad(m, ((0, bh * 4 - m.shape[0]), (0, bw * 4 - m.shape[1])))
            blocks = pm.reshape(bh, 4, bw, 4).any((1, 3)).reshape(-1)
            old = np.frombuffer(ue_texture.read_mip(src, mip), np.uint8).reshape(-1, bsize)
            data = np.where(blocks[:, None], np.frombuffer(data, np.uint8).reshape(-1, bsize), old).tobytes()
        payloads[mip["index"]] = data
    ue_texture.write(src, dst, payloads)


def to8(img):
    return np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8)


def retoc(*args):
    subprocess.run([RETOC, *args], check=True, stdout=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_PAKS)
    args = ap.parse_args()
    shutil.rmtree(WORK, ignore_errors=True)
    src_dir, raw = os.path.join(WORK, "game"), os.path.join(WORK, MOD)
    names = [(folder, t) for folder, d, s in PARTS.values() for t in (d, s) if t]
    names += [("Textures", t) for pair in FLATTEN.values() for t in pair]
    filters = []
    for folder, t in names:
        filters += ["--filter", f"../../../{COSTUME}/{folder}/{t}.uasset"]
    retoc("unpack", os.path.join(args.game, "pakchunkCharacter-Windows.utoc"), *filters, "--output", src_dir,
          "--game-paks-dir", args.game)
    preview = os.path.join(ROOT, "magneto", "preview", "textures")
    os.makedirs(preview, exist_ok=True)

    def path(folder, t, root):
        return os.path.join(root, *COSTUME.split("/"), *folder.split("/"), t)

    for f, t in names:
        if not os.path.exists(path(f, t, src_dir) + ".uasset"):
            raise SystemExit(f"{t} didn't come out of pakchunkCharacter")
    emblem = cape_emblem(top_mip(path("Textures", "T_1037001_Equip_03_ORM", src_dir))[1])
    helmet = mask("mask_helmet_T_1037001_Equip_01").astype(np.float32)
    badge = buckle_badge()

    def save(folder, t, img, only=None, note=""):
        src = path(folder, t, src_dir)
        _, old = top_mip(src)
        new = img if img.dtype == np.uint8 else to8(img)
        changed = (np.abs(new.astype(int) - old.astype(int)).max(-1) > 24).mean()
        if changed < 0.002 and only is None:
            print(f"  {t}: nothing to recolour, left vanilla")
            return
        write_mips(src, path(folder, t, raw), new, only)
        shown = new
        if new.shape[-1] == 2:   # normal map: rebuild blue to look at it
            xy = new.astype(np.float32) / 127.5 - 1
            shown = np.dstack([new, to8((np.sqrt(np.clip(1 - (xy ** 2).sum(-1), 0, 1)) + 1) / 2)])
        png.write(os.path.join(preview, f"{t}.png"), shown)
        print(f"  {t}: {changed * 100:.1f}% of pixels changed{note}")

    for part, (folder, dname, sname) in PARTS.items():
        rgb = top_mip(path(folder, dname, src_dir))[1].astype(np.float32) / 255.0
        if part in ("Equip_01", "Equip_02", "Equip_04"):
            new = armour(rgb, helmet if part == "Equip_01" else None)
        elif part == "Equip_03":
            new = cape(rgb, emblem)
        elif part == "Equip_05":
            new = cape_inside(rgb)
        else:
            new = weapon(rgb)
        new, logo = overlay(new, dname)
        save(folder, dname, new, note=" + logo" if logo is not None else "")
        if sname is None:
            continue
        s0 = top_mip(path(folder, sname, src_dir))[1].astype(np.float32) / 255.0
        s = s0
        if part == "Equip_03":
            s = inpaint(s0, emblem)
        elif part == "Equip_02":   # the badge gets the dull shine of the buckle's dark disc, no old emblem in it
            s = blend(s0, np.full(3, np.percentile(lum(s0[badge > 0.5]), 25), np.float32), badge)
        new_s = specular(s, new)
        up = (lum(new_s) - lum(s0)) * 255
        up = up[~emblem] if part == "Equip_03" else up[badge == 0] if part == "Equip_02" else up
        save(folder, sname, new_s, note=f" (shine: mean {up.mean():+.1f}, max {up.max():+.1f} away from the old emblems)")

    for part, (nname, oname) in FLATTEN.items():
        for t in (nname, oname):
            img = top_mip(path("Textures", t, src_dir))[1].astype(np.float32)
            if part == "Equip_03":
                hole, new = emblem, bump_fill(img, emblem) if t == nname else inpaint(img, emblem)
            else:   # buckle: flat under the badge, with the disc's typical roughness/metal
                hole = badge > 0
                flat = np.full(img.shape[-1], 128.0) if t == nname else np.median(img[badge > 0.5], 0)
                new = blend(img, flat.astype(np.float32), badge)
            save("Textures", t, np.clip(new + 0.5, 0, 255).astype(np.uint8), only=dilate(hole, 4),
                 note=" (old emblem smoothed out)")

    try:
        for asset, cont, done in magneto_mats.build(raw, args.game, os.path.join(WORK, "mats")):
            print(f"  {os.path.basename(asset)} (from {cont}): "
                  + ", ".join(f"{p} {tuple(round(x, 3) for x in o)} -> {tuple(round(x, 3) for x in n)}"
                              for p, o, n in done))
    except SystemExit as e:
        print(f"  cape glow left red: {e}")
    ok, msg = magneto_lod.check(args.game)
    if not ok:
        print("  check this: " + msg)

    out = os.path.join(ROOT, "magneto", "dist", "~mods")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, f"{MOD}_9999999_P.*")):
        os.remove(f)
    retoc("pack", raw, "--output", out)
    print(f"wrote {out}\\{MOD}_9999999_P.pak/.utoc/.ucas")


if __name__ == "__main__":
    main()
