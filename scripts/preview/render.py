"""Preview renderer: a hero mesh from the game with its colour textures, as PNG views or a turntable GIF.

HOW TO USE

  From the command line (unpacks what it needs from the game into work\\preview\\, read only):

    python scripts/preview/render.py --mesh Marvel/Content/Marvel/Characters/1037/1037001/Meshes/SK_1037_1037001 ^
        --out work/preview/magneto.png
    python scripts/preview/render.py --mesh ... --textures magneto/preview/textures --out discord.png
    python scripts/preview/render.py --mesh ... --window 0.3,0.0,0.7,0.3 --views front --out face.png
    python scripts/preview/render.py --mesh ... --turntable work/preview/magneto.gif --frames 40

  --textures <folder> (repeatable) puts PNGs named like the game textures (T_1037001_Equip_03_D.png) over the
  vanilla ones, that's how a skin's recoloured textures show up. --views takes any of front, threequarter,
  back or a yaw in degrees (0 = front, positive turns the camera to the hero's right). --window is a close-up:
  left, top, right, bottom as fractions of the full body frame. --height sets the image height, --ss the
  supersampling (3 = 3x3 samples per pixel).

  From Python:

    import game, render, skm
    prefix = game.unpack_mesh(asset, out)                 # retoc unpack of the mesh (legacy files)
    mesh = skm.load(prefix)                                # LOD0 geometry + material slots
    game.hero_textures(mesh, tex_dir, out)                 # decoded _D PNGs + slots.json per material slot
    tex = render.load_textures(tex_dir, overrides=[r"magneto\\preview\\textures"])
    img = render.render(mesh, tex, view="threequarter", height=720)          # uint8 (H, W, 3)
    img = render.views(mesh, tex, ("front", "threequarter", "back"))        # side by side
    render.turntable(mesh, tex, "spin.gif", frames=40, height=480)          # README sized GIF

WHAT IT DOES

  Orthographic camera, z-buffer rasterizer (raster.py), supersampled. Colour texture per material slot
  (UV channel 0, bilinear, sRGB), a key, fill and top-back light plus a rim light, a little shine, on a dark
  gradient background with a soft shadow under the feet. Materials are one sided (back faces culled) except
  two sided ones: slots with a "back" texture in slots.json (the back faces use it, like Magneto's cape inside)
  and alpha tested hair cards ("mask" texture, texels under 50% are see-through). Slots marked "hidden" are
  skipped (eye highlight shells and so on). No normal maps, no skinning: the bind pose (A pose) as cooked.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import raster   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
VIEWS = {"front": 0.0, "threequarter": 35.0, "side": 90.0, "back": 180.0}

BG_TOP = np.array([38, 41, 50]) / 255.0
BG_BOTTOM = np.array([17, 18, 22]) / 255.0


# ---------------------------------------------------------------- textures
def srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def _read_png(path):
    from PIL import Image
    return np.asarray(Image.open(path))


def load_textures(folder, overrides=()):
    """slots.json + PNGs (game.hero_textures) -> {slot: dict(d, back, mask, hidden)} as float32 arrays
    (colours linear). PNGs in the override folders win over the ones in folder, matched by file name."""
    with open(os.path.join(folder, "slots.json")) as fh:
        slots = json.load(fh)
    cache = {}

    def get(name, colour):
        key = (name, colour)
        if key not in cache:
            path = next((os.path.join(d, name + ".png") for d in list(overrides) + [folder]
                         if os.path.exists(os.path.join(d, name + ".png"))), None)
            if path is None:
                raise FileNotFoundError(f"{name}.png isn't in {folder} or the override folders")
            img = _read_png(path).astype(np.float32) / 255.0
            if img.ndim == 2:
                img = img[..., None]
            if colour:
                img = srgb_to_linear(img[..., :3] if img.shape[-1] >= 3 else np.repeat(img[..., :1], 3, -1))
            else:
                img = img[..., 0]
            cache[key] = np.ascontiguousarray(img)
        return cache[key]

    out = {}
    for slot, e in slots.items():
        t = dict(hidden=bool(e.get("hidden")), material=e.get("material", ""))
        if not t["hidden"]:
            t["d"] = get(e["d"], True)
            if e.get("back"):
                t["back"] = get(e["back"], True)
            if e.get("mask"):
                t["mask"] = get(e["mask"], False)
        out[slot] = t
    return out


def sample(img, uv):
    """bilinear, wrapping. img (H, W) or (H, W, C), uv (n, 2) with v down (Unreal/DirectX)"""
    h, w = img.shape[:2]
    x = (uv[:, 0] % 1.0) * w - 0.5
    y = (uv[:, 1] % 1.0) * h - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0).astype(np.float32), (y - y0).astype(np.float32)
    x0, y0, x1, y1 = x0 % w, y0 % h, (x0 + 1) % w, (y0 + 1) % h
    if img.ndim == 3:
        fx, fy = fx[:, None], fy[:, None]
    top = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    bot = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return top * (1 - fy) + bot * fy


# ---------------------------------------------------------------- camera and framing
def camera(yaw):
    """yaw in degrees (0 = looking at the hero's face from +Y) -> right, up, toward camera (unit vectors)"""
    a = np.radians(yaw)
    right = np.array([np.cos(a), np.sin(a), 0.0])
    toward = np.array([-np.sin(a), np.cos(a), 0.0])
    return right, np.array([0.0, 0.0, 1.0]), toward


def full_frame(mesh, margin=0.06):
    """the same frame for every yaw: (centre x, centre z, half width, half height) in cm, around the vertical
    axis through the middle of the mesh (so a turntable doesn't wobble)"""
    p = mesh.positions[np.unique(mesh.triangles)]
    axis = (p[:, :2].min(0) + p[:, :2].max(0)) / 2
    radius = np.sqrt(((p[:, :2] - axis) ** 2).sum(1)).max()
    z0, z1 = p[:, 2].min(), p[:, 2].max()
    hh = (z1 - z0) / 2 * (1 + 2 * margin)
    return dict(axis=axis, cz=(z0 + z1) / 2 + (z1 - z0) * margin * 0.4, hh=hh, hw=radius * (1 + margin),
                floor=z0)


def _winding(mesh):
    """+1 if cross(v1 - v0, v2 - v0) points out of the surface, -1 if it points in (Unreal: in)"""
    p, t = mesh.positions, mesh.triangles
    g = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
    return 1.0 if (np.einsum("ij,ij->i", g, mesh.normals[t].sum(1)) > 0).mean() > 0.5 else -1.0


# ---------------------------------------------------------------- shading
LIGHTS = [  # view space direction (x right, y up, z toward camera), colour
    (np.array([-0.45, 0.55, 0.70]), np.array([1.00, 0.97, 0.92]) * 1.05),   # key, upper left front
    (np.array([0.80, 0.10, 0.55]), np.array([0.78, 0.84, 1.00]) * 0.38),    # fill, right
    (np.array([0.10, 0.75, -0.65]), np.array([1.00, 1.00, 1.00]) * 0.30),   # top back
]
AMBIENT = 0.22
RIM = (np.array([0.80, 0.86, 1.00]), 0.40, 3.0)   # colour, strength, falloff
SPEC = (0.10, 36.0)


def shade(albedo, n):
    """albedo linear (n, 3), n view space unit normals (n, 3) -> linear colour"""
    light = np.full((len(n), 3), AMBIENT, np.float32) * (0.75 + 0.35 * (n[:, 1:2] * 0.5 + 0.5))
    spec = np.zeros(len(n), np.float32)
    for k, (d, c) in enumerate(LIGHTS):
        d = d / np.linalg.norm(d)
        ndl = n @ d
        wrap = np.clip((ndl + 0.15) / 1.15, 0, 1)
        light += wrap[:, None] * c
        if k == 0:
            h = d + np.array([0, 0, 1.0])
            h /= np.linalg.norm(h)
            spec += np.clip(n @ h, 0, 1) ** SPEC[1] * SPEC[0]
    col = albedo * light + spec[:, None]
    rc, rs, rp = RIM
    rim = (1 - np.clip(n[:, 2], 0, 1)) ** rp * rs
    col += rim[:, None] * rc * (0.35 + 0.65 * albedo.mean(1, keepdims=True) ** 0.5)
    return col


def background(w, h):
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    bg = BG_TOP * (1 - y) + BG_BOTTOM * y
    xx = np.linspace(-1, 1, w, dtype=np.float32)[None, :, None]
    yy = np.linspace(-1, 1, h, dtype=np.float32)[:, None, None]
    vignette = 1 - 0.18 * np.clip(xx ** 2 * 0.6 + yy ** 2 * 0.4, 0, 1)
    return np.broadcast_to(bg, (h, w, 3)) * vignette


# ---------------------------------------------------------------- render
def render(mesh, textures, view="front", height=720, width=None, ss=3, window=None, frame=None,
           shadow=True, two_sided=None, hide=(), coverage=False):
    """-> uint8 (H, W, 3), or (image, coverage 0..1 (H, W)) with coverage=True.
    view: 'front', 'threequarter', 'side', 'back' or a yaw in degrees.
    window: (left, top, right, bottom) fractions of the full body frame, for close-ups.
    frame: full_frame(mesh) to share between calls (computed if None).
    two_sided: slot names drawn two sided (default: slots with a back texture or a mask).
    hide: extra slot names to skip."""
    yaw = VIEWS[view] if isinstance(view, str) else float(view)
    frame = frame or full_frame(mesh)
    right, up, toward = camera(yaw)
    p = mesh.positions.astype(np.float64)
    sx = p @ right - frame["axis"] @ right[:2]
    sy = p[:, 2]
    depth = p @ toward

    # visible region in cm
    x0, x1 = -frame["hw"], frame["hw"]
    y1, y0 = frame["cz"] + frame["hh"], frame["cz"] - frame["hh"]
    if window is not None:
        l, t, r, b = window
        x0, x1 = x0 + (x1 - x0) * l, x0 + (x1 - x0) * r
        y1, y0 = y1 - (y1 - y0) * t, y1 - (y1 - y0) * b
    if width is None:
        width = int(round(height * (x1 - x0) / (y1 - y0)))
    W, H = width * ss, height * ss
    scale = min(W / (x1 - x0), H / (y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    xy = np.stack([(sx - cx) * scale + W / 2, (cy - sy) * scale + H / 2], 1)

    # which triangles to draw
    names = [s["name"] for s in mesh.slots]
    tex = [textures.get(n, dict(hidden=True)) for n in names]
    if two_sided is None:
        two_sided = {n for n, t in zip(names, tex) if "back" in t or "mask" in t}
    slot_hidden = np.array([t.get("hidden", True) or n in hide for n, t in zip(names, tex)])
    slot_two = np.array([n in two_sided for n in names])
    tri, ts = mesh.triangles, mesh.tri_slot
    g = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]]) * _winding(mesh)
    facing = g @ toward > 0
    draw = ~slot_hidden[ts] & (facing | slot_two[ts])
    sel = np.nonzero(draw)[0]
    tris = tri[sel]

    masks = {i: t["mask"] for i, t in enumerate(tex) if "mask" in t and not slot_hidden[i]}
    uv0 = mesh.uvs[:, 0, :]

    def keep(tid, bary):
        ok = np.ones(len(tid), bool)
        slot = ts[sel[tid]]
        for i, m in masks.items():
            k = slot == i
            if k.any():
                tt = tris[tid[k]]
                uv = (uv0[tt] * bary[k][..., None]).sum(1)
                ok[k] = sample(m, uv) >= 0.5
        return ok

    tid, bary, _ = raster.rasterize(xy, depth, tris, W, H, keep=keep if masks else None)
    cov = tid >= 0
    t_sel = tid[cov]
    orig = sel[t_sel]
    slot = ts[orig]
    back = ~facing[orig]
    b = bary[cov]
    tt = tri[orig]
    uv = (uv0[tt] * b[..., None]).sum(1)
    n = (mesh.normals[tt] * b[..., None]).sum(1)
    n = np.where(back[:, None], -n, n)
    n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
    nv = np.stack([n @ right, n @ up, n @ toward], 1).astype(np.float32)

    albedo = np.zeros((len(slot), 3), np.float32)
    for i, t in enumerate(tex):
        if slot_hidden[i]:
            continue
        k = slot == i
        if not k.any():
            continue
        if "back" in t:
            kb = k & back
            kf = k & ~back
            if kf.any():
                albedo[kf] = sample(t["d"], uv[kf])
            if kb.any():
                albedo[kb] = sample(t["back"], uv[kb])
        else:
            albedo[k] = sample(t["d"], uv[k])
    lit = shade(albedo, nv)

    img = background(W, H).astype(np.float32).copy()
    if shadow:
        _floor_shadow(img, mesh, xy, sy, frame, scale)
    img = srgb_to_linear(img)
    img[cov] = lit
    img = raster.downsample(img, ss)
    out = linear_to_srgb(img / (1 + 0.12 * np.clip(img - 0.8, 0, None)))
    out = np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
    if coverage:
        return out, raster.downsample(cov.astype(np.float32), ss)
    return out


def _floor_shadow(img, mesh, xy, sy, frame, scale):
    """soft dark ellipse under the feet (the camera is level, so the floor itself is a line)"""
    low = sy < frame["floor"] + 12
    if not low.any():
        return
    fx = xy[low, 0]
    cx = (fx.min() + fx.max()) / 2
    rx = (fx.max() - fx.min()) / 2 + 14 * scale
    ry = max(rx * 0.16, 3)
    cy = xy[low, 1].max() - ry * 0.25
    H, W = img.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    a = 0.6 * np.exp(-d * 2.2)
    img *= (1 - a)[..., None]


def views(mesh, textures, names=("front", "threequarter", "back"), height=720, gap=0, **kw):
    """several views of the same frame side by side"""
    frame = kw.pop("frame", None) or full_frame(mesh)
    imgs = [render(mesh, textures, v, height=height, frame=frame, **kw) for v in names]
    if gap:
        bg = (BG_BOTTOM * 255).astype(np.uint8)
        sep = np.broadcast_to(bg, (imgs[0].shape[0], gap, 3))
        imgs = [x for im in imgs for x in (im, sep)][:-1]
    return np.concatenate(imgs, 1)


def save_png(path, img):
    from PIL import Image
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    Image.fromarray(img).save(path, optimize=True)


def gif_palette(shots, covers, colors=255, bg_colors=40):
    """one palette for all frames: bg_colors for the backdrop (median cut, keeps the gradient smooth) and the
    rest for the hero (octree, keeps small areas like skin from snapping to the wrong colour)"""
    from PIL import Image
    px = np.concatenate([s.reshape(-1, 3) for s in shots])
    cv = np.concatenate([c.reshape(-1) for c in covers])
    rng = np.random.default_rng(0)

    def pal(sel, n, method):
        p = px[sel]
        if len(p) > 400_000:
            p = p[rng.integers(0, len(p), 400_000)]
        if not len(p):
            return []
        img = Image.fromarray(p.reshape(-1, 1, 3))
        q = img.quantize(colors=n, method=method)
        used = len(q.getcolors(n + 1) or [])
        return q.getpalette()[:3 * max(used, 1)]

    bg = pal(cv == 0, bg_colors, Image.Quantize.MEDIANCUT)
    fg = pal(cv > 0, colors - len(bg) // 3, Image.Quantize.FASTOCTREE)
    flat = (bg + fg)[:3 * 256]
    p = Image.new("P", (1, 1))
    p.putpalette(flat + [0] * (768 - len(flat)))
    return p


def turntable(mesh, textures, path, frames=40, height=480, ss=2, seconds=4.0, start=0.0, colors=255,
              max_bytes=6_000_000, **kw):
    """frames renders around the hero -> looping GIF with one shared palette. Drops frames to every other
    one if the file is over max_bytes (GitHub shows README GIFs up to 10 MB, smaller loads faster).
    -> file size"""
    from PIL import Image
    frame = kw.pop("frame", None) or full_frame(mesh)
    shots, covers = [], []
    for i in range(frames):
        s, c = render(mesh, textures, start + 360.0 * i / frames, height=height, ss=ss, frame=frame,
                      coverage=True, **kw)
        shots.append(s)
        covers.append(c)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pal = gif_palette(shots, covers, colors)
    q = [Image.fromarray(s).quantize(palette=pal, dither=Image.Dither.NONE) for s in shots]
    while True:
        ms = int(round(seconds * 1000 / len(q)))
        q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True, disposal=1)
        size = os.path.getsize(path)
        if size <= max_bytes or len(q) <= 12:
            return size
        q = q[::2]


# ---------------------------------------------------------------- command line
def main():
    import game
    import skm
    from paths import DEFAULT_PAKS
    ap = argparse.ArgumentParser(description="render a hero mesh from the game (see the top of render.py)")
    ap.add_argument("--mesh", required=True, help="Marvel/Content/.../SK_xxx (no extension)")
    ap.add_argument("--out", help="PNG with the views side by side")
    ap.add_argument("--views", default="front,threequarter,back")
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--ss", type=int, default=3)
    ap.add_argument("--window", help="close-up: left,top,right,bottom as fractions of the full frame")
    ap.add_argument("--textures", action="append", default=[], help="folder of PNGs that replace game textures")
    ap.add_argument("--turntable", help="GIF path")
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--gif-height", type=int, default=480)
    ap.add_argument("--work", default=os.path.join(ROOT, "work", "preview"))
    ap.add_argument("--game", default=DEFAULT_PAKS)
    ap.add_argument("--newest", action="store_true", help="use the export data of a newer patch copy")
    args = ap.parse_args()
    name = args.mesh.rstrip("/").split("/")[-1]
    raw = os.path.join(args.work, "game")
    prefix = game.unpack_mesh(args.mesh, raw, args.game)
    mesh = skm.load(prefix, newest=game.newest_export(args.mesh, args.game) if args.newest else None)
    print(mesh, "from", mesh.source)
    tex_dir = os.path.join(args.work, "textures", name)
    game.hero_textures(mesh, tex_dir, raw, args.game)
    tex = load_textures(tex_dir, overrides=args.textures)
    window = tuple(float(x) for x in args.window.split(",")) if args.window else None
    if args.out:
        names = [v if v in VIEWS else float(v) for v in args.views.split(",")]
        save_png(args.out, views(mesh, tex, names, height=args.height, ss=args.ss, window=window))
        print("wrote", args.out)
    if args.turntable:
        size = turntable(mesh, tex, args.turntable, frames=args.frames, height=args.gif_height)
        print(f"wrote {args.turntable} ({size / 1e6:.2f} MB)")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(HERE))
    main()
