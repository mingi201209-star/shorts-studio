"""Side-view cross-section of a rolling tire hydroplaning on a water film.

Why this exists (custom code note, per CLAUDE.md): no maintained library or
vendor example renders a narration-synced tire/water-film cross-section, so
this module is the minimal custom part. Everything generic is delegated to
proven tools -- Pillow for anti-aliased drawing/resampling, numpy for the
per-pixel shading, FFmpeg/libx264 for encoding.

Why it replaces ``hydroplaning3d`` in the quality-reset production (that
module is kept intact for its own tests and other callers): a real render
review showed the flat-shaded 3D cylinder reading as low-budget CG, and its
exaggerated lift (the tire floating about a radius above a blob of water)
was physically misleading -- real hydroplaning separates tire and road by a
water film only millimetres thick. This view is the classic engineering
cross-section plus a magnified inset of the contact zone: the camera never
moves, and every change between beats is a change of physical state (bow
wave, wedge penetration, contact length, lift), never a crop/zoom.

All state is a pure function of one global progress value ``g`` in [0, 1],
so adjacent beat clips start/end on identical states.
"""
from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 980, 926  # fits render's 980x950 media box with a 12 px black margin top/bottom
SS = 2  # supersampling factor; frames are drawn at 2x and Lanczos-downsampled

# World geometry (arbitrary units ~ pixels at scale 1). Tire centre x = 0,
# road surface y = 0, +y points DOWN like image rows.
TIRE_R = 300.0
DEFLECTION = 16.0           # tire flattening -> contact patch length 2*sqrt(2*R*d)
FILM = 7.0                  # undisturbed water film (exaggerated mm-scale film)
MAX_LIFT = 8.0              # at full hydroplaning the tire rides ON the film
ROTATIONS = 1.8             # wheel turns across the whole sequence (slow-motion cross-section)

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
)


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _ramp(g: float, a: float, b: float) -> float:
    return _smooth((g - a) / (b - a))


# --- physical state (pure functions of g) ----------------------------------

def rotation_at(g: float) -> float:
    """Wheel angle in radians; speed rises with g (the 'faster' premise)."""
    g = max(0.0, min(1.0, g))
    return 2 * math.pi * ROTATIONS * (0.75 * g + 0.25 * g * g)


def bow_wave_at(g: float) -> float:
    """Height factor of the water piled up ahead of the tire (0..1)."""
    return 0.10 + 0.90 * _ramp(g, 0.12, 0.50)


def wedge_at(g: float) -> float:
    """Fraction of the contact patch invaded by the water wedge (0..1)."""
    return _ramp(g, 0.48, 0.86)


def contact_at(g: float) -> float:
    """Remaining dry contact fraction (1 = full patch, 0 = none)."""
    return 1.0 - wedge_at(g)


def lift_at(g: float) -> float:
    """Tire lift in world units; only once the wedge has crossed the patch."""
    return MAX_LIFT * _ramp(g, 0.84, 0.96)


def state(g: float) -> dict:
    return {
        "g": g, "rotation": rotation_at(g), "bow": bow_wave_at(g),
        "wedge": wedge_at(g), "contact": contact_at(g), "lift": lift_at(g),
    }


def contact_half_length() -> float:
    return math.sqrt(TIRE_R ** 2 - (TIRE_R - DEFLECTION) ** 2)


@dataclass(frozen=True)
class View:
    """World -> screen mapping: screen = (world - centre) * scale + anchor."""
    width: int
    height: int
    scale: float
    world_cx: float
    world_cy: float
    anchor_x: float
    anchor_y: float

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        return ((x - self.world_cx) * self.scale + self.anchor_x,
                (y - self.world_cy) * self.scale + self.anchor_y)


MAIN_VIEW = View(W, H, 0.78, 0.0, 0.0, 490.0, 500.0)
INSET_BOX = (40, 600, 940, 905)  # screen rectangle of the magnified panel
INSET_VIEW = View(INSET_BOX[2] - INSET_BOX[0], INSET_BOX[3] - INSET_BOX[1],
                  3.4, 10.0, -6.0, (INSET_BOX[2] - INSET_BOX[0]) / 2, 150.0)


# --- static layers ---------------------------------------------------------

@lru_cache(maxsize=4)
def _asphalt(h: int, w: int, scale: float) -> np.ndarray:
    """Asphalt cross-section strip (3x wide for scrolling) in world units.

    Dense light-grey aggregate stones in a dark binder, drawn once at world
    resolution with OpenCV and resampled bicubically, so the magnified inset
    shows smooth stones rather than blocks. Real asphalt is visibly speckled;
    that contrast is also what makes the road's motion past the tire legible.
    """
    import cv2

    rng = np.random.default_rng(7)
    px_per_unit = scale * SS
    gw = max(16, int(3 * w / px_per_unit) + 1)
    gh = max(8, int(h / px_per_unit) + 1)
    up = 4  # draw at 4 px per world unit (1 unit ~ 1 mm at this tire size)
    canvas = np.full((gh * up, gw * up), 36.0, np.float32)
    n = int(gw * gh / 22)
    for _ in range(n):
        cx, cy = rng.uniform(0, gw * up), rng.uniform(0, gh * up)
        ax, ay = rng.uniform(3, 9) * up, rng.uniform(2, 6) * up
        tone = float(rng.uniform(58, 138))
        cv2.ellipse(canvas, (int(cx), int(cy)), (int(ax), int(ay)), float(rng.uniform(0, 180)), 0, 360, tone, -1, cv2.LINE_AA)
    # Soft stone edges only -- no per-pixel grain, which would alias into
    # frame-to-frame flicker when the road scrolls.
    canvas = cv2.GaussianBlur(canvas, (0, 0), 0.7 * up)
    tex = cv2.resize(canvas, (3 * w, h), interpolation=cv2.INTER_AREA if px_per_unit < up else cv2.INTER_CUBIC)
    tex = tex * np.linspace(1.0, 0.6, h)[:, None]
    tex = np.clip(tex, 0, 255)
    return np.stack([tex * 0.97, tex * 0.98, tex * 1.03], axis=-1)


@lru_cache(maxsize=2)
def _bokeh(h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Soft roadside light bokeh strip (3x wide) for the sky behind the wheel."""
    import cv2

    rng = np.random.default_rng(21)
    rgb = np.zeros((h, 3 * w, 3), np.float32)
    alpha = np.zeros((h, 3 * w), np.float32)
    palette = [(255, 196, 120), (255, 226, 180), (235, 240, 255), (255, 120, 90), (150, 190, 255)]
    for _ in range(int(3 * w / (60 * SS))):
        cx = rng.uniform(0, 3 * w)
        cy = rng.uniform(0.35, 0.92) * h
        r = rng.uniform(28, 70) * SS
        col = palette[int(rng.integers(len(palette)))]
        strength = float(rng.uniform(0.18, 0.42))
        disc = np.zeros_like(alpha)
        cv2.circle(disc, (int(cx), int(cy)), int(r), 1.0, -1, cv2.LINE_AA)
        disc = cv2.GaussianBlur(disc, (0, 0), r * 0.18) * strength
        rgb += disc[..., None] * np.array(col, np.float32)
        alpha += disc
    alpha = np.clip(alpha, 0, 0.6)
    rgb = rgb / np.maximum(alpha[..., None], 1e-3) * np.clip(alpha[..., None], 0, 1)
    rgb = np.clip(rgb / np.maximum(alpha[..., None], 1e-3), 0, 255)
    rgb = cv2.GaussianBlur(rgb, (0, 0), 3 * SS)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 3 * SS)
    return rgb, alpha


@lru_cache(maxsize=4)
def _font(size: int, path: str | None = None):
    for cand in ((path,) if path else ()) + _FONT_CANDIDATES:
        if cand and Path(cand).is_file():
            return ImageFont.truetype(cand, size)
    return None


# --- geometry helpers (world units) ----------------------------------------

def _water_thickness(xs: np.ndarray, st: dict) -> np.ndarray:
    half = contact_half_length()
    front, rear = half, -half
    thick = np.full_like(xs, FILM, dtype=float)
    d = np.maximum(xs - front, 0) / 110.0
    bow = FILM + st["bow"] * 40.0 * np.exp(-d) * (1 - np.exp(-d * 7))
    thick = np.where(xs > front, bow, thick)
    recov = 1 - np.exp(-np.maximum(rear - xs, 0) / 150.0)
    squeeze = 1 - 0.65 * st["contact"]
    thick = np.where(xs < rear, FILM * (squeeze + (1 - squeeze) * recov), thick)
    return thick


def _tire_floor(xs: np.ndarray, st: dict) -> np.ndarray:
    """Lowest world y the tire may occupy at each x (road, wedge or film)."""
    half = contact_half_length()
    front = half
    tip = front - st["wedge"] * 2 * half
    wedge = np.where((xs > tip) & (xs <= front),
                     FILM * np.clip((xs - tip) / max(1.0, front - tip), 0, 1) ** 0.7, 0.0)
    wedge = np.where(xs > front, FILM, wedge)
    return -np.maximum(wedge, st["lift"])


# --- rendering ---------------------------------------------------------------

@lru_cache(maxsize=4)
def _view_static(view: View):
    """Per-view constants: world coordinates of every pixel and the backdrop."""
    w, h = view.width * SS, view.height * SS
    s = view.scale * SS
    jj, ii = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    wx = (jj + 0.5 - view.anchor_x * SS) / s + view.world_cx
    wy = (ii + 0.5 - view.anchor_y * SS) / s + view.world_cy
    road_row = int(np.clip(view.anchor_y * SS + (0 - view.world_cy) * s, 0, h))
    t = np.clip(ii / max(1, road_row), 0, 1) ** 1.6
    top = np.array([9, 14, 25], np.float32)
    mid = np.array([24, 38, 58], np.float32)
    bg = top * (1 - t[..., None]) + mid * t[..., None]
    nx = (jj / w) * 2 - 1
    ny = ii / h
    bg = bg * (1.0 - 0.35 * np.clip(nx ** 2 + (ny - 0.55) ** 2 * 1.6, 0, 1))[..., None]
    for arr in (wx, wy, bg):
        arr.setflags(write=False)
    return wx, wy, bg, road_row


def _render_view(st: dict, view: View, rain: bool) -> np.ndarray:
    w, h = view.width * SS, view.height * SS
    s = view.scale * SS
    wx, wy, bg, road_row = _view_static(view)
    xs = wx[0]
    img = bg.copy()

    if rain:
        # Out-of-focus roadside lights behind the wheel, scrolling with
        # parallax (slower than the road) as the car travels.
        bok, bok_a = _bokeh(road_row, w)
        shift = int(st["rotation"] * TIRE_R * s * 0.45) % (2 * w)
        a = bok_a[:, shift:shift + w, None]
        img[:road_row] = img[:road_row] * (1 - a) + bok[:, shift:shift + w] * a
        layer = Image.new("L", (w, h), 0)
        rd = ImageDraw.Draw(layer)
        rng = np.random.default_rng(3)
        clock = st["rotation"] * 0.10
        for _ in range(140):
            x0 = rng.uniform(-200, view.width + 200)
            yph = (rng.uniform() + clock * rng.uniform(0.8, 1.3)) % 1.0
            y = yph * (road_row / SS + 80) - 40
            x = x0 - (y + 40) * 0.18
            ln = rng.uniform(22, 42)
            rd.line([(x * SS, y * SS), ((x - ln * 0.18) * SS, (y + ln) * SS)],
                    fill=int(rng.uniform(35, 75)), width=SS)
        a = np.asarray(layer.filter(ImageFilter.GaussianBlur(SS * 0.6)), float)[..., None] / 255.0
        img = img * (1 - a) + np.array([170, 195, 220]) * a

    # Road (scrolls left: rolling without slipping -> distance = angle * R).
    if road_row < h:
        tex = _asphalt(h - road_row, w, view.scale)
        shift = int(st["rotation"] * TIRE_R * s) % (2 * w)
        img[road_row:] = tex[:, shift:shift + w]
        img[road_row:road_row + SS] = img[road_row:road_row + SS] * 0.5 + 60

    floor = _tire_floor(xs, st)
    thick = _water_thickness(xs, st)
    cy = -(TIRE_R - DEFLECTION) - st["lift"]
    px, py = wx, wy - cy
    r = np.hypot(px, py)
    ang = np.arctan2(py, px)
    tire = (r <= TIRE_R) & (wy <= floor[None, :])

    water = (wy >= -thick[None, :]) & (wy <= 0) & ~tire
    shimmer = 0.5 + 0.5 * np.sin(wx * 0.05 + st["rotation"] * 2.5 + wy * 0.3)
    water_rgb = np.stack([28 + 22 * shimmer, 118 + 40 * shimmer, 205 + 30 * shimmer], axis=-1)
    img = np.where(water[..., None], img * 0.2 + water_rgb * 0.8, img)
    line_w = 1.4 / s
    surf = water & (wy <= -thick[None, :] + max(line_w * 1.6, 0.9 / view.scale))
    img = np.where(surf[..., None], np.array([175, 228, 255]), img)

    # Rubber: key light from upper-left, rotating tread blocks.
    rot = st["rotation"]
    rubber = 24 + 20 * np.clip(-np.cos(ang + 2.3), 0, 1) * (r / TIRE_R) ** 6
    side = (r < TIRE_R * 0.93) & (r > TIRE_R * 0.70)
    rubber = rubber + np.where(side, 8 * np.clip(-np.sin(ang + 0.6), 0, 1), 0)
    pitch = 2 * math.pi / 56
    groove = (r > TIRE_R * 0.95) & (np.mod(ang - rot, pitch) / pitch < 0.26)
    rubber = np.where(groove, rubber * 0.55, rubber)
    tire_rgb = np.stack([rubber, rubber, rubber * 1.06], axis=-1)

    # Rim: dark barrel with five twin spokes, light motion blur.
    rim_r = TIRE_R * 0.66
    rim = r < rim_r
    metal = 165 + 70 * np.clip(-np.cos(ang + 2.2), 0, 1)
    barrel = 14 + 10 * (r / rim_r)
    cover = np.zeros_like(r)
    samples = 3
    span = 0.05
    for k in range(samples):
        a = ang - rot + span * (k / (samples - 1) - 0.5)
        sector = np.mod(a, 2 * math.pi / 5) - math.pi / 5
        half_w = 0.075 + 0.07 * (1 - r / rim_r)
        cover += (np.abs(np.abs(sector) - 0.14) < half_w) & (r > rim_r * 0.2)
    cover /= samples
    rim_val = barrel * (1 - cover) + metal * cover
    rim_val = np.where(rim & (r > rim_r - 8), metal + 30, rim_val)
    rim_val = np.where(r < rim_r * 0.2, 150 + 55 * np.clip(-np.cos(ang + 2.2), 0, 1), rim_val)
    tire_rgb = np.where(rim[..., None], np.stack([rim_val, rim_val, rim_val * 1.04], -1), tire_rgb)
    img = np.where(tire[..., None], tire_rgb, img)
    edge = tire & (r > TIRE_R - 2.4 / view.scale) & (py < 0)
    img = np.where(edge[..., None], img * 0.5 + np.array([120, 130, 145]) * 0.5, img)
    return img


def _draw_spray_and_contact(over: Image.Image, st: dict, view: View, ox: float = 0, oy: float = 0,
                            clip_box=None) -> None:
    d = ImageDraw.Draw(over)
    half = contact_half_length()
    front, rear = half, -half
    t = st["rotation"] / (2 * math.pi)
    rng = np.random.default_rng(11)
    k = max(1.0, view.scale)

    def dot(x, y, rad, col):
        sx, sy = view.to_screen(x, y)
        sx, sy = sx + ox, sy + oy
        if clip_box and not (clip_box[0] <= sx <= clip_box[2] and clip_box[1] <= sy <= clip_box[3]):
            return
        rr = rad * SS
        d.ellipse([sx * SS - rr, sy * SS - rr, sx * SS + rr, sy * SS + rr], fill=col)

    for _ in range(int(18 + 70 * st["bow"])):
        ph = (rng.uniform() + t * rng.uniform(1.2, 2.0)) % 1.0
        vx = rng.uniform(60, 220) * (0.5 + st["bow"])
        vy = rng.uniform(80, 260) * (0.4 + st["bow"])
        x = front + 15 + vx * ph
        y = -FILM - vy * ph + 300 * ph * ph
        if y < -2:
            dot(x, y, rng.uniform(1.2, 3.0) * min(k, 2.0), (190, 230, 255, int(200 * (1 - ph))))
    for _ in range(30):
        ph = (rng.uniform() + t * rng.uniform(1.5, 2.4)) % 1.0
        x = rear - 15 - rng.uniform(80, 260) * ph
        y = -FILM - rng.uniform(60, 200) * ph + 260 * ph * ph
        if y < -2:
            dot(x, y, rng.uniform(1.0, 2.4) * min(k, 2.0), (170, 210, 240, int(150 * (1 - ph))))

    tip = front - st["wedge"] * 2 * half
    if st["lift"] < 0.5 and tip - rear > 1:
        a = view.to_screen(rear, -0.5)
        b = view.to_screen(tip, -0.5)
        a = (a[0] + ox, a[1] + oy)
        b = (b[0] + ox, b[1] + oy)
        glow = Image.new("RGBA", over.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        width = 5 if view.scale < 2 else 9
        gd.line([(a[0] * SS, a[1] * SS), (b[0] * SS, b[1] * SS)], fill=(255, 170, 50, 255), width=width * SS)
        glow = glow.filter(ImageFilter.GaussianBlur(3 * SS))
        gd = ImageDraw.Draw(glow)
        gd.line([(a[0] * SS, a[1] * SS), (b[0] * SS, b[1] * SS)], fill=(255, 215, 130, 255), width=max(2, width // 2) * SS)
        over.alpha_composite(glow)


def render_frame(g: float, labels: bool = True, font_path: str | None = None,
                 headline: str | None = None) -> Image.Image:
    st = state(g)
    main = _render_view(st, MAIN_VIEW, rain=True)
    frame = Image.fromarray(np.clip(main, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    over = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    _draw_spray_and_contact(over, st, MAIN_VIEW)

    # Magnified inset of the contact zone, rendered natively (not upscaled).
    x0, y0, x1, y1 = INSET_BOX
    inset = _render_view(st, INSET_VIEW, rain=False)
    inset_img = Image.fromarray(np.clip(inset, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    inset_over = Image.new("RGBA", inset_img.size, (0, 0, 0, 0))
    _draw_spray_and_contact(inset_over, st, INSET_VIEW)
    inset_img.alpha_composite(inset_over)
    mask = Image.new("L", inset_img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inset_img.size[0] - 1, inset_img.size[1] - 1], radius=22 * SS, fill=255)
    over.paste(inset_img, (x0 * SS, y0 * SS), mask)
    od = ImageDraw.Draw(over)
    od.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS], radius=22 * SS, outline=(150, 200, 235, 200), width=2 * SS)

    # Source marker on the main view + connector lines to the panel.
    half_w_world = INSET_VIEW.width / INSET_VIEW.scale / 2
    half_h_world = INSET_VIEW.height / INSET_VIEW.scale / 2
    wl = INSET_VIEW.world_cx - half_w_world
    wr = INSET_VIEW.world_cx + half_w_world
    wt = INSET_VIEW.world_cy - (INSET_VIEW.anchor_y / INSET_VIEW.scale)
    wb = wt + INSET_VIEW.height / INSET_VIEW.scale
    ml, mt = MAIN_VIEW.to_screen(wl, wt)
    mr, mb = MAIN_VIEW.to_screen(wr, wb)
    od.rectangle([ml * SS, mt * SS, mr * SS, mb * SS], outline=(150, 200, 235, 210), width=2 * SS)
    od.line([(ml * SS, mb * SS), ((x0 + 22) * SS, y0 * SS)], fill=(150, 200, 235, 120), width=SS)
    od.line([(mr * SS, mb * SS), ((x1 - 22) * SS, y0 * SS)], fill=(150, 200, 235, 120), width=SS)
    _ = half_h_world

    if labels:
        font = _font(30 * SS, font_path)
        tag = _font(22 * SS, font_path)
        if font is not None:
            half = contact_half_length()
            front = half
            tip = front - st["wedge"] * 2 * half

            def callout(text, world_xy, text_xy, color):
                sx, sy = INSET_VIEW.to_screen(*world_xy)
                sx, sy = sx + x0, sy + y0
                tx, ty = text_xy
                od.line([(sx * SS, sy * SS), (tx * SS, (ty + 44) * SS)], fill=color + (235,), width=2 * SS)
                od.ellipse([(sx - 5) * SS, (sy - 5) * SS, (sx + 5) * SS, (sy + 5) * SS], fill=color + (255,))
                tw = od.textlength(text, font=font) / SS
                od.text(((tx - tw / 2) * SS, ty * SS), text, font=font, fill=color + (255,),
                        stroke_width=2 * SS, stroke_fill=(5, 10, 18, 255))

            amber, blue = (255, 190, 90), (130, 210, 255)
            if st["lift"] < 0.5 and tip + half > 3:
                callout("접촉면", ((-half + tip) / 2, 0.0), (250, INSET_BOX[1] + 46), amber)
            if st["wedge"] > 0.06:
                callout("물 쐐기", (tip + (front - tip) * 0.6, -FILM * 0.4), (700, INSET_BOX[1] + 46), blue)
            elif st["bow"] > 0.35:
                callout("밀려드는 물", (front + 40, -FILM - 12 * st["bow"]), (720, INSET_BOX[1] + 46), blue)
            if st["lift"] >= 0.5:
                callout("물막", (-20.0, -st["lift"] / 2), (330, INSET_BOX[1] + 46), blue)
            od.text(((x0 + 18) * SS, (y0 + 12) * SS), "접촉 부위 확대", font=tag, fill=(170, 205, 230, 230))
            if headline:
                hf = _font(58 * SS, font_path)
                tw = od.textlength(headline, font=hf)
                od.text(((W * SS - tw) / 2, 36 * SS), headline, font=hf, fill=(255, 255, 255, 255),
                        stroke_width=3 * SS, stroke_fill=(5, 10, 18, 255))
    frame.alpha_composite(over)
    return frame.convert("RGB").resize((W, H), Image.LANCZOS)


def render_clip(out: Path, g_start: float, g_end: float, duration: float, fps: int = 30,
                labels: bool = True, font_path: str | None = None, headline: str | None = None) -> Path:
    """Render global progress [g_start, g_end] to an H.264 clip via FFmpeg.

    Frames are streamed to ffmpeg's stdin as raw RGB (no temp PNGs).
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to encode the hydroplaning section clip")
    out.parent.mkdir(parents=True, exist_ok=True)
    total = max(2, int(round(duration * fps)))
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
         "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE,
    )
    try:
        for i in range(total):
            g = g_start + (g_end - g_start) * i / (total - 1)
            proc.stdin.write(render_frame(g, labels=labels, font_path=font_path, headline=headline).tobytes())
    finally:
        proc.stdin.close()
        rc = proc.wait(timeout=600)
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed encoding {out}")
    return out
