"""Generate an original painterly landscape for the brief's hero.

Deterministic per (date, mood). No network. Needs numpy + Pillow.
Mood: OPEN (golden afternoon), NORMAL (clear morning), HEAVY (storm breaking).
"""
import io, base64, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 840

PALETTES = {
    "OPEN": dict(sky_top=(88,118,140), sky_hz=(236,206,140), cloud_lit=(250,232,190), cloud_shadow=(150,140,120),
                 far=(140,150,160), mid=(92,104,72), trees=(46,60,34), tree_lit=(122,128,60),
                 field_near=(120,86,40), field_far=(196,160,88), sun=(255,236,170)),
    "NORMAL": dict(sky_top=(120,158,190), sky_hz=(222,226,214), cloud_lit=(248,246,236), cloud_shadow=(160,170,178),
                   far=(150,166,178), mid=(96,122,84), trees=(40,66,42), tree_lit=(110,140,80),
                   field_near=(84,100,52), field_far=(168,176,110), sun=(255,248,220)),
    "HEAVY": dict(sky_top=(46,54,64), sky_hz=(196,170,120), cloud_lit=(210,196,160), cloud_shadow=(60,64,72),
                  far=(92,100,108), mid=(60,70,56), trees=(26,34,26), tree_lit=(90,96,56),
                  field_near=(64,54,34), field_far=(140,118,70), sun=(255,226,150)),
}

def _noise(rng, h, w, octaves=5, base=3):
    acc = np.zeros((h, w), np.float32); amp = 1.0; tot = 0.0
    for o in range(octaves):
        gh, gw = base * 2**o + 1, int(base * 2**o * w / h) + 1
        g = rng.random((gh, gw)).astype(np.float32)
        up = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
        acc += amp * up; tot += amp; amp *= 0.5
    acc /= tot
    return (acc - acc.min()) / (np.ptp(acc) + 1e-6)

def _ridge(rng, w, base_y, amp, octaves=5, base=3):
    x = np.linspace(0, 1, w, dtype=np.float32)
    n = np.zeros(w, np.float32); a = 1.0; tot = 0.0
    for o in range(octaves):
        f = (base * 2**o) * (0.8 + 0.4 * rng.random())
        n += a * np.sin(2 * np.pi * (x * f + rng.random())); tot += a; a *= 0.5
    n = (n / tot + 1) / 2
    return (base_y - amp * n).astype(np.float32)

def _mix(a, b, t):
    t = t[..., None] if np.ndim(t) == 2 else t
    return a * (1 - t) + b * t

def paint(date_key: str, mood: str = "OPEN") -> Image.Image:
    p = {k: np.array(v, np.float32) for k, v in PALETTES.get(mood, PALETTES["OPEN"]).items()}
    seed = int(hashlib.sha256(f"{date_key}:{mood}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    hz = H * (0.50 + 0.06 * rng.random())
    sun_x = W * (0.25 + 0.5 * rng.random()); sun_y = hz * (0.35 + 0.3 * rng.random())

    # sky gradient + sun glow
    t = np.clip(yy / hz, 0, 1) ** 1.4
    img = _mix(np.broadcast_to(p["sky_top"], (H, W, 3)), np.broadcast_to(p["sky_hz"], (H, W, 3)), t)
    d = np.hypot((xx - sun_x) / W, (yy - sun_y) / H)
    glow = np.exp(-(d / 0.22) ** 2)
    img = _mix(img, np.broadcast_to(p["sun"], (H, W, 3)), glow * 0.55)

    # clouds: thresholded fractal noise, lit from the sun side
    cn = _noise(rng, H, W // 2, 6, 2)
    cn = np.asarray(Image.fromarray((cn * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
    stretch = np.clip(1.05 - yy / hz, 0, 1) ** 0.7
    cover = {"OPEN": 0.50, "NORMAL": 0.55, "HEAVY": 0.34}[mood]
    thr = np.quantile(cn, 1 - cover * 0.8); top = np.quantile(cn, 0.985)
    cm = np.clip((cn - thr) / (top - thr), 0, 1) ** 0.8 * stretch
    gy = np.gradient(cn, axis=0) * -60
    shade = np.clip(0.45 + gy + (1 - np.hypot(xx - sun_x, yy - sun_y) / W) * 0.5, 0, 1)
    cloud_col = _mix(np.broadcast_to(p["cloud_shadow"], (H, W, 3)), np.broadcast_to(p["cloud_lit"], (H, W, 3)), shade)
    img = _mix(img, cloud_col, cm * 0.9)

    # light rays falling from the sun
    ang = np.arctan2(yy - sun_y, xx - sun_x)
    rays = (np.sin(ang * rng.integers(9, 15) + rng.random() * 6) * 0.5 + 0.5) ** 6
    ray_m = rays * np.clip((yy - sun_y) / (hz - sun_y + 1), 0, 1) * (yy < hz) * 0.18
    img = _mix(img, np.broadcast_to(p["sun"], (H, W, 3)), ray_m)

    # far hills (hazy), mid hills, tree line
    far = _ridge(rng, W, hz + H * 0.03, H * 0.11, 4, 1)
    m = (yy > far[None, :]).astype(np.float32)
    far_col = _mix(p["far"], p["sky_hz"], 0.2)
    img = _mix(img, np.broadcast_to(far_col, (H, W, 3)), m * 0.85)

    mid = _ridge(rng, W, hz + H * 0.10, H * 0.08, 5, 1)
    m2 = (yy > mid[None, :]).astype(np.float32)
    lit = np.clip(1 - np.abs(xx - sun_x) / W * 1.6, 0, 1)
    mid_col = _mix(np.broadcast_to(p["mid"], (H, W, 3)), np.broadcast_to(p["field_far"], (H, W, 3)), lit * 0.35)
    img = _mix(img, mid_col, m2)

    # field: far gold to near umber, with horizontal streaks
    near = _ridge(rng, W, hz + H * 0.22, H * 0.05, 4, 1)
    fy = near[None, :]
    ft = np.clip((yy - fy) / (H - fy), 0, 1)
    streak = _noise(rng, H, W // 8, 4, 6)
    streak = np.asarray(Image.fromarray((streak * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
    field = _mix(np.broadcast_to(p["field_far"], (H, W, 3)), np.broadcast_to(p["field_near"], (H, W, 3)), ft ** 0.8)
    field = field * (0.86 + 0.28 * streak[..., None])
    img = _mix(img, field, np.clip((yy - fy) / 18, 0, 1))

    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    canvas = canvas.filter(ImageFilter.GaussianBlur(1.6))
    dr = ImageDraw.Draw(canvas)

    # tree clumps along the mid ridge
    side = rng.random() < 0.5
    groups = [(rng.random() * W, mid, W * (0.04 + 0.08 * rng.random()), H * (0.06 + 0.10 * rng.random()))
              for _ in range(rng.integers(10, 16))]
    gx = W * (0.08 + 0.12 * rng.random()) if side else W * (0.80 - 0.10 * rng.random())
    groups += [(gx + (rng.random() - 0.5) * W * 0.12, near, W * (0.10 + 0.06 * rng.random()), H * (0.30 + 0.14 * rng.random()))
               for _ in range(3)]
    groups.sort(key=lambda g: g[1][int(min(g[0], W - 1))])
    for cx, ridge, width, height in groups:
        cx = min(max(cx, 0), W - 1); base = ridge[int(cx)] + H * 0.015
        for _ in range(int(width * height / 70)):
            x = cx + (rng.random() - 0.5) * width
            prof = 1 - ((x - cx) / (width / 2)) ** 2
            y = base - rng.random() * height * max(prof, 0.05)
            r = (2 + rng.random() * 7) * (height / (H * 0.2)) ** 0.5
            toward = 1 - min(abs(x - sun_x) / W * 1.5, 1)
            l = np.clip(0.15 + 0.45 * (base - y) / height + 0.3 * toward + rng.normal(0, 0.12), 0, 1)
            c = p["trees"] * (1 - l) + p["tree_lit"] * l
            c = tuple(int(v) for v in np.clip(c + rng.normal(0, 3, 3), 0, 255))
            dr.ellipse([x - r, y - r * 0.8, x + r, y + r * 0.8], fill=c)

    # brush strokes: sample the canvas and re-lay short strokes for an oil texture
    arr = np.asarray(canvas)
    n = 26000
    xs = rng.integers(0, W, n); ys = rng.integers(0, H, n)
    for x, y in zip(xs, ys):
        c = arr[y, x].astype(np.int16) + rng.integers(-10, 11, 3)
        sky = y < hz
        L = rng.uniform(6, 18) if sky else rng.uniform(4, 12)
        a = rng.normal(0.0 if (sky or y > near[x]) else -0.6, 0.35)
        dx, dy = np.cos(a) * L, np.sin(a) * L * (0.4 if sky else 0.7)
        dr.line([x - dx, y - dy, x + dx, y + dy], fill=tuple(int(v) for v in np.clip(c, 0, 255)),
                width=int(rng.integers(2, 5)))

    out = np.asarray(canvas.filter(ImageFilter.GaussianBlur(0.6)), np.float32)
    # varnish warmth, canvas grain, vignette
    out = out * np.array([1.03, 1.0, 0.92])
    grain = rng.normal(0, 5, (H, W, 1))
    v = np.clip(1 - ((xx / W - 0.5) ** 2 * 1.1 + (yy / H - 0.5) ** 2 * 1.6), 0, 1)[..., None]
    out = (out + grain) * (0.68 + 0.32 * v)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

def data_uri(date_key: str, mood: str = "OPEN", width: int = 1400) -> str:
    im = paint(date_key, mood)
    im = im.resize((width, int(width * H / W)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=80, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

if __name__ == "__main__":
    import sys
    for mood in ("OPEN", "NORMAL", "HEAVY"):
        paint(sys.argv[1] if len(sys.argv) > 1 else "2026-11-07", mood).save(f"/home/claude/paint-{mood}.jpg", quality=85)
