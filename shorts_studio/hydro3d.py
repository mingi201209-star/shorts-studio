from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


@dataclass(frozen=True)
class Camera:
    yaw: float
    pitch: float
    distance: float
    focal: float
    cx: float
    cy: float


# Topic-specific camera: the viewer rides alongside the tire from slightly
# above and ahead. That keeps the tread, contact patch, road, water wedge, and
# spray readable at the same time without camera movement.
OPTIMAL_HYDRO_CAMERA = Camera(
    yaw=-0.20,
    pitch=-0.24,
    distance=7.2,
    focal=900.0,
    cx=420.0,
    cy=455.0,
)

KINDS = (
    "hero_contact",
    "water_wedge",
    "contact_shrink",
    "full_hydroplane",
    "drainage_channels",
    "speed_ramp",
    "pressure_lift",
    "wedge_closeup",
    "steering_loss",
    "braking_loss",
    "recover_contact",
    "final_cutaway",
    "final_drive",
)


def camera_for(kind: str, t: float) -> Camera:
    if kind not in KINDS:
        raise ValueError(kind)
    return OPTIMAL_HYDRO_CAMERA


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _smoothstep(v: float) -> float:
    u = _clamp01(v)
    return u * u * (3.0 - 2.0 * u)


def _smootherstep(v: float) -> float:
    u = _clamp01(v)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def _micro_time(t: float, time_seconds: float | None) -> float:
    return float(time_seconds) if time_seconds is not None else float(t) * 3.0


def _background(width: int, height: int) -> Image.Image:
    yy = np.linspace(0.0, 1.0, height)[:, None]
    xx = np.linspace(0.0, 1.0, width)[None, :]
    glow = np.exp(-(((xx - 0.42) / 0.48) ** 2 + ((yy - 0.42) / 0.50) ** 2))
    base = np.zeros((height, width, 3), dtype=np.float32)
    base[..., 0] = 4 + 7 * glow
    base[..., 1] = 7 + 17 * glow
    base[..., 2] = 11 + 23 * glow
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def _road_geometry(height: int) -> tuple[int, int]:
    return int(height * 0.715), int(height * 0.935)


def _draw_road(image: Image.Image, micro: float, speed: float, wetness: float) -> int:
    w, h = image.size
    top, bottom = _road_geometry(h)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")

    d.polygon(
        [(0, top), (w, top - 8), (w, bottom), (0, bottom)],
        fill=(21, 24, 27, 255),
    )

    # Moving asphalt highlights give the viewer a stable car-follow camera
    # while preserving clear object-scale motion for the whole beat.
    offset = (micro * (104.0 + 138.0 * speed)) % 150.0
    for row, alpha in ((top + 38, 40), (top + 86, 30), (top + 142, 22)):
        for i in range(-2, 10):
            x = i * 150.0 - offset
            d.line(
                (x, row, x + 74, row - 5),
                fill=(100, 111, 119, alpha),
                width=3,
            )

    # Water sheet is intentionally thin and translucent. The wedge under the
    # tire carries the hydroplaning story; this base layer establishes that
    # the whole road is wet.
    water_h = 9 + int(18 * wetness)
    d.rectangle(
        (0, top - water_h, w, top + 4),
        fill=(33, 134, 176, int(70 + 40 * wetness)),
    )

    shimmer = (micro * (150 + 110 * speed)) % 210
    for i in range(-1, 7):
        x = i * 210 - shimmer
        d.line(
            (x, top - water_h * 0.55, x + 115, top - water_h * 0.55 - 4),
            fill=(164, 235, 250, int(78 + 42 * wetness)),
            width=2,
        )

    layer = layer.filter(ImageFilter.GaussianBlur(0.35))
    image.alpha_composite(layer)
    return top


def _draw_tire(
    image: Image.Image,
    micro: float,
    road_y: int,
    *,
    lift: float,
    spin_speed: float,
    tread_visibility: float = 1.0,
) -> tuple[float, float, float]:
    w, _ = image.size
    cx = w * 0.43
    radius = w * 0.225
    cy_ground = road_y - radius * 0.88
    cy = cy_ground - radius * 0.24 * lift

    back_dx, back_dy = -34, -16
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")

    # Cylinder thickness / rear tire face.
    d.ellipse(
        (cx - radius + back_dx, cy - radius + back_dy,
         cx + radius + back_dx, cy + radius + back_dy),
        fill=(12, 15, 18, 255),
        outline=(61, 68, 72, 210),
        width=4,
    )

    # Main tire.
    d.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=(18, 21, 24, 255),
        outline=(104, 112, 116, 230),
        width=5,
    )
    inner = radius * 0.53
    d.ellipse(
        (cx - inner, cy - inner, cx + inner, cy + inner),
        fill=(44, 48, 52, 255),
        outline=(142, 151, 157, 220),
        width=4,
    )
    rim = radius * 0.38
    d.ellipse(
        (cx - rim, cy - rim, cx + rim, cy + rim),
        fill=(113, 120, 126, 255),
        outline=(211, 217, 221, 190),
        width=3,
    )
    hub = radius * 0.105
    d.ellipse((cx - hub, cy - hub, cx + hub, cy + hub), fill=(32, 35, 38, 255))

    # Rotating tread blocks. Motion is continuous even after the story state
    # settles, so long narration beats never turn into a held diagram.
    phase = micro * math.tau * spin_speed
    for i in range(30):
        a = (i / 30.0) * math.tau + phase
        x1 = cx + math.cos(a) * radius * 0.91
        y1 = cy + math.sin(a) * radius * 0.91
        x2 = cx + math.cos(a) * radius * 1.02
        y2 = cy + math.sin(a) * radius * 1.02
        alpha = int((58 + 100 * max(0.0, math.sin(a))) * tread_visibility)
        d.line((x1, y1, x2, y2), fill=(158, 166, 169, alpha), width=4)

    # Three readable circumferential groove cues near the visible lower face.
    for off in (-0.18, 0.0, 0.18):
        yy = cy + radius * (0.69 + off * 0.20)
        d.arc(
            (cx - radius * 0.90, yy - radius * 0.18,
             cx + radius * 0.90, yy + radius * 0.18),
            12, 168,
            fill=(7, 10, 12, int(190 * tread_visibility)),
            width=5,
        )

    # Soft rim highlight provides depth without a moving light source.
    hi = Image.new("RGBA", image.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi, "RGBA")
    hd.arc(
        (cx - radius * 0.98, cy - radius * 0.98,
         cx + radius * 0.98, cy + radius * 0.98),
        205, 330,
        fill=(184, 196, 201, 90),
        width=7,
    )
    hi = hi.filter(ImageFilter.GaussianBlur(1.5))
    layer.alpha_composite(hi)

    image.alpha_composite(layer)
    return cx, cy, radius


def _draw_contact_patch(
    image: Image.Image,
    cx: float,
    road_y: int,
    radius: float,
    contact: float,
    *,
    pulse: float,
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    c = _clamp01(contact)
    length = radius * (0.34 + 1.00 * c)
    y = road_y - 4
    alpha = int(65 + 155 * c)
    color = (87, 225, 176, alpha) if c > 0.48 else (255, 177, 87, alpha)
    width = max(5, int(7 + 7 * c + 2 * pulse))
    d.line((cx - length / 2, y, cx + length / 2, y), fill=color, width=width)
    if c < 0.18:
        # Broken segments make "almost no road contact" readable without text.
        d.line((cx - length * 0.65, y, cx - length * 0.18, y), fill=(255, 103, 83, 190), width=4)
        d.line((cx + length * 0.18, y, cx + length * 0.65, y), fill=(255, 103, 83, 190), width=4)
    layer = layer.filter(ImageFilter.GaussianBlur(1.2))
    image.alpha_composite(layer)


def _draw_water_wedge(
    image: Image.Image,
    micro: float,
    cx: float,
    road_y: int,
    radius: float,
    amount: float,
    pressure: float,
) -> None:
    a = _clamp01(amount)
    p = _clamp01(pressure)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")

    lead_x = cx + radius * 0.70
    tip_x = cx + radius * (1.72 + 0.28 * a)
    top_y = road_y - radius * (0.05 + 0.40 * a)
    wave = radius * 0.020 * math.sin(math.tau * 1.1 * micro)
    poly = [
        (cx - radius * 0.45, road_y - 5),
        (lead_x, road_y - 4),
        (tip_x, top_y + wave),
        (tip_x + radius * 0.12, road_y + 2),
    ]
    d.polygon(poly, fill=(24, 132, 181, int(72 + 110 * a)))
    d.line(poly[:3], fill=(163, 236, 250, int(145 + 80 * a)), width=max(3, int(radius * 0.022)))

    # Coherent moving pressure bands inside the wedge.
    for i in range(5):
        phase = (micro * (0.58 + 0.05 * i) + i * 0.17) % 1.0
        x = lead_x + (tip_x - lead_x) * phase
        local = 1.0 - phase
        h = radius * (0.08 + 0.25 * a * local)
        d.line(
            (x, road_y - 3, x, road_y - h),
            fill=(104, 218, 244, int((55 + 115 * p) * (0.55 + 0.45 * local))),
            width=3,
        )

    # Upward water-pressure arrows under the tire.
    for i in range(4):
        x = cx - radius * 0.32 + i * radius * 0.23
        h = radius * (0.09 + 0.21 * p) * (0.86 + 0.10 * math.sin(micro * 4.0 + i))
        d.line((x, road_y - 4, x, road_y - h), fill=(95, 215, 241, int(70 + 145 * p)), width=4)
        d.polygon(
            [(x, road_y - h - 9), (x - 7, road_y - h + 3), (x + 7, road_y - h + 3)],
            fill=(156, 239, 252, int(85 + 150 * p)),
        )

    layer = layer.filter(ImageFilter.GaussianBlur(0.65))
    image.alpha_composite(layer)


def _draw_spray(
    image: Image.Image,
    micro: float,
    cx: float,
    road_y: int,
    radius: float,
    intensity: float,
    speed: float,
) -> None:
    strength = _clamp01(intensity)
    if strength <= 0.01:
        return
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")

    count = 64
    for i in range(count):
        base = i / count
        phase = (base + micro * (0.32 + 0.17 * speed) * (0.85 + (i % 5) * 0.035)) % 1.0
        side = -1.0 if i % 2 else 1.0
        x = cx + radius * (0.48 + 2.15 * phase)
        y = road_y - radius * (0.04 + 0.48 * math.sin(math.pi * phase) * strength)
        y += side * radius * 0.035 * math.sin(i * 1.7 + micro * 6.0)
        rr = 2.0 + 4.5 * (1.0 - phase)
        alpha = int((45 + 155 * math.sin(math.pi * phase)) * strength)
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(178, 238, 250, alpha))
        if i % 4 == 0:
            d.line(
                (x - radius * 0.08, y + radius * 0.02, x, y),
                fill=(116, 214, 237, int(alpha * 0.52)),
                width=2,
            )
    layer = layer.filter(ImageFilter.GaussianBlur(0.55))
    image.alpha_composite(layer)


def _draw_drainage(
    image: Image.Image,
    micro: float,
    cx: float,
    road_y: int,
    radius: float,
    strength: float,
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")
    s = _clamp01(strength)

    # Flow paths through tread grooves. They move sideways/backward rather than
    # flashing, which makes the drainage function readable as a physical flow.
    for lane in (-0.25, 0.0, 0.25):
        start_x = cx + radius * (0.58 + lane * 0.15)
        start_y = road_y - radius * (0.08 + abs(lane) * 0.03)
        for j in range(5):
            q = (micro * 0.44 + j / 5.0 + lane * 0.21) % 1.0
            x = start_x - radius * 0.88 * q
            y = start_y + lane * radius * 0.40 + math.sin(q * math.pi) * radius * 0.06
            rr = 4.0
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(137, 233, 249, int(165 * s)))
    d.line(
        (cx - radius * 0.45, road_y - radius * 0.12,
         cx + radius * 0.60, road_y - radius * 0.12),
        fill=(62, 178, 220, int(72 * s)),
        width=6,
    )
    layer = layer.filter(ImageFilter.GaussianBlur(0.5))
    image.alpha_composite(layer)


def _draw_turn_cue(
    image: Image.Image,
    micro: float,
    cx: float,
    cy: float,
    radius: float,
    contact: float,
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")

    # Requested steering direction.
    box = (
        cx - radius * 1.15,
        cy - radius * 1.05,
        cx + radius * 0.95,
        cy + radius * 1.05,
    )
    d.arc(box, 195, 278, fill=(230, 236, 240, 160), width=6)
    ax = cx - radius * 1.02
    ay = cy - radius * 0.56
    d.polygon([(ax, ay), (ax + 15, ay - 6), (ax + 10, ay + 12)], fill=(235, 241, 244, 180))

    # Lateral force arrows fade away with contact.
    c = _clamp01(contact)
    alpha = int(35 + 190 * c)
    for i in range(3):
        x = cx - radius * 0.18 + i * radius * 0.18
        y = cy + radius * 0.82
        length = radius * (0.10 + 0.30 * c) * (0.92 + 0.08 * math.sin(micro * 3.1 + i))
        d.line((x, y, x - length, y), fill=(255, 199, 102, alpha), width=4)
        d.polygon(
            [(x - length - 9, y), (x - length + 3, y - 6), (x - length + 3, y + 6)],
            fill=(255, 211, 126, alpha),
        )

    layer = layer.filter(ImageFilter.GaussianBlur(0.35))
    image.alpha_composite(layer)


def render_hydro_frame(
    kind: str,
    t: float,
    width: int = 980,
    height: int = 950,
    *,
    time_seconds: float | None = None,
) -> Image.Image:
    if kind not in KINDS:
        raise ValueError(f"unknown hydro kind: {kind}")
    for probe in KINDS:
        if camera_for(probe, 0.5) != OPTIMAL_HYDRO_CAMERA:
            raise RuntimeError(f"hydro camera drift: {probe}")

    story = _clamp01(t)
    micro = _micro_time(story, time_seconds)

    image = _background(width, height)

    # State parameters: road speed, wetness, lift, contact, wedge, pressure,
    # spray, drainage. Continuous transitions change only the phenomenon.
    speed = 0.50
    wetness = 0.65
    lift = 0.0
    contact = 1.0
    wedge = 0.20
    pressure = 0.18
    spray = 0.32
    drainage = 0.25
    steering = False

    if kind == "hero_contact":
        speed = 0.56
        wedge = 0.22
        pressure = 0.18
        spray = 0.50
        drainage = 0.64

    elif kind == "water_wedge":
        mix = story
        speed = 0.46 + 0.28 * mix
        wedge = 0.18 + 0.72 * mix
        pressure = 0.18 + 0.52 * mix
        contact = 1.0 - 0.25 * mix
        lift = 0.08 * mix
        spray = 0.36 + 0.42 * mix
        drainage = 0.40

    elif kind == "contact_shrink":
        mix = story
        speed = 0.72
        wedge = 0.80 + 0.14 * mix
        pressure = 0.68 + 0.24 * mix
        contact = 0.78 - 0.62 * mix
        lift = 0.10 + 0.58 * mix
        spray = 0.82
        drainage = 0.30

    elif kind == "full_hydroplane":
        speed = 0.86
        wetness = 0.90
        wedge = 1.00
        pressure = 1.00
        contact = 0.05
        lift = 0.82
        spray = 1.00
        drainage = 0.18

    elif kind == "drainage_channels":
        speed = 0.56
        wetness = 0.76
        wedge = 0.46
        pressure = 0.38
        contact = 0.90
        lift = 0.05
        spray = 0.58
        drainage = 1.00

    elif kind == "speed_ramp":
        mix = story
        speed = 0.28 + 0.68 * mix
        wetness = 0.82
        wedge = 0.18 + 0.82 * mix
        pressure = 0.15 + 0.85 * mix
        contact = 1.0 - 0.90 * mix
        lift = 0.78 * mix
        spray = 0.30 + 0.70 * mix
        drainage = 0.46 - 0.20 * mix

    elif kind == "pressure_lift":
        mix = story
        speed = 0.82
        wetness = 0.88
        wedge = 0.84 + 0.16 * mix
        pressure = 0.68 + 0.32 * mix
        contact = 0.58 - 0.52 * mix
        lift = 0.28 + 0.56 * mix
        spray = 0.92
        drainage = 0.20

    elif kind == "wedge_closeup":
        # Same fixed viewpoint, but the physical state itself makes the water
        # wedge dominate: high water pressure, nearly lost contact, and strong
        # coherent spray/pressure bands.
        speed = 0.88
        wetness = 0.94
        wedge = 1.00
        pressure = 1.00
        contact = 0.12
        lift = 0.76
        spray = 1.00
        drainage = 0.12

    elif kind == "steering_loss":
        speed = 0.86
        wetness = 0.92
        wedge = 1.00
        pressure = 0.98
        contact = 0.04
        lift = 0.82
        spray = 1.00
        drainage = 0.16
        steering = True

    elif kind == "braking_loss":
        speed = 0.84
        wetness = 0.92
        wedge = 0.98
        pressure = 0.96
        contact = 0.06
        lift = 0.80
        spray = 0.96
        drainage = 0.16

    elif kind == "recover_contact":
        mix = story
        speed = 0.82 - 0.46 * mix
        wetness = 0.68
        wedge = 0.96 - 0.70 * mix
        pressure = 0.92 - 0.72 * mix
        contact = 0.08 + 0.88 * mix
        lift = 0.78 - 0.72 * mix
        spray = 0.94 - 0.54 * mix
        drainage = 0.35 + 0.42 * mix

    elif kind == "final_cutaway":
        # Payoff cycles around a near-threshold state: enough contact to see
        # the road, enough water pressure to see how easily it can disappear.
        osc = 0.5 + 0.5 * math.sin(micro * math.tau * 0.22)
        speed = 0.68 + 0.10 * osc
        wetness = 0.82
        wedge = 0.62 + 0.20 * osc
        pressure = 0.52 + 0.26 * osc
        contact = 0.62 - 0.34 * osc
        lift = 0.18 + 0.34 * osc
        spray = 0.72 + 0.18 * osc
        drainage = 0.54

    elif kind == "final_drive":
        # Final stable state: slower road speed, visible drainage, and a
        # restored contact patch. The road still scrolls and the tire still
        # rotates so the ending never becomes a freeze-frame.
        speed = 0.50
        wetness = 0.66
        wedge = 0.24
        pressure = 0.18
        contact = 0.96
        lift = 0.03
        spray = 0.48
        drainage = 0.96

    road_y = _draw_road(image, micro, speed=speed, wetness=wetness)
    cx, cy, radius = _draw_tire(
        image,
        micro,
        road_y,
        lift=lift,
        spin_speed=0.26 + 0.34 * speed,
        tread_visibility=1.0,
    )

    _draw_water_wedge(image, micro, cx, road_y, radius, wedge, pressure)
    _draw_drainage(image, micro, cx, road_y, radius, drainage)
    _draw_spray(image, micro, cx, road_y, radius, spray, speed)
    _draw_contact_patch(
        image,
        cx,
        road_y,
        radius,
        contact,
        pulse=0.5 + 0.5 * math.sin(micro * 3.2),
    )

    if steering:
        _draw_turn_cue(image, micro, cx, cy, radius, contact)

    if kind == "braking_loss":
        # Requested braking force points opposite travel, but with almost no
        # tire-road contact the transmissible force collapses.
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, "RGBA")
        alpha = int(45 + 185 * contact)
        y = road_y - radius * 0.12
        x0 = cx + radius * 0.18
        x1 = x0 - radius * (0.16 + 0.36 * contact)
        d.line((x0, y, x1, y), fill=(255, 178, 90, alpha), width=5)
        d.polygon([(x1 - 10, y), (x1 + 4, y - 7), (x1 + 4, y + 7)], fill=(255, 198, 114, alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(0.4))
        image.alpha_composite(layer)

    return image


def render_hydro_motion(
    kind: str,
    out_path: str | Path,
    *,
    duration: float = 4.5,
    fps: int = 30,
    width: int = 980,
    height: int = 950,
) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None

    frames = max(2, round(duration * fps))
    transition_seconds = {
        "water_wedge": 1.10,
        "contact_shrink": 1.15,
        "speed_ramp": 1.45,
        "pressure_lift": 1.10,
        "recover_contact": 1.30,
    }

    try:
        for i in range(frames):
            elapsed = i / fps
            transition = transition_seconds.get(kind)
            progress = _smootherstep(elapsed / transition) if transition else 1.0
            frame = render_hydro_frame(
                kind,
                progress,
                width=width,
                height=height,
                time_seconds=elapsed,
            ).convert("RGB")
            proc.stdin.write(frame.tobytes())

        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"ffmpeg failed for {kind}: {stderr[-3000:]}")
    finally:
        if proc.poll() is None:
            proc.kill()

    if not out.is_file() or out.stat().st_size < 10_000:
        raise RuntimeError(f"motion render missing or too small: {out}")
    return out
