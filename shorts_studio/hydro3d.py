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

    # Broad wet-road reflections move coherently under the fixed car-follow
    # camera. They occupy enough area to make the physical road motion readable
    # on a phone, without resorting to camera shake or crop/zoom churn.
    broad_offset = (micro * (250.0 + 260.0 * speed)) % 230.0
    broad_alpha = int(50 + 46 * wetness)
    for i in range(-3, 8):
        x = i * 230.0 - broad_offset
        d.polygon(
            [
                (x, top + 12),
                (x + 104, top + 5),
                (x + 174, bottom - 4),
                (x + 38, bottom),
            ],
            fill=(91, 108, 118, broad_alpha),
        )
        d.line(
            (x + 24, top + 22, x + 142, bottom - 18),
            fill=(145, 164, 174, int(38 + 42 * wetness)),
            width=8,
        )

    # Smaller asphalt streaks add a second, slower spatial frequency so the
    # road never looks like a repeating conveyor-belt texture.
    offset = (micro * (175.0 + 210.0 * speed)) % 122.0
    for row, alpha, width in (
        (top + 25, 118, 7),
        (top + 60, 102, 7),
        (top + 98, 88, 6),
        (top + 138, 74, 6),
        (top + 178, 62, 5),
    ):
        for i in range(-3, 13):
            x = i * 122.0 - offset
            d.line(
                (x, row, x + 82, row - 9),
                fill=(126, 145, 154, alpha),
                width=width,
            )

    # The actual water film remains thin. Large moving reflection ribbons sit
    # on the wet pavement, not as a physically thick pool.
    water_h = 16 + int(32 * wetness)
    d.rectangle(
        (0, top - water_h, w, top + 7),
        fill=(29, 137, 184, int(108 + 72 * wetness)),
    )

    shimmer = (micro * (260 + 190 * speed)) % 156
    for band in range(4):
        yy = top - water_h * (0.22 + 0.19 * band)
        phase = shimmer + band * 41
        for i in range(-2, 10):
            x = i * 156 - phase
            d.line(
                (x, yy, x + 114, yy - 7 - band),
                fill=(184, 244, 253, int(125 + 88 * wetness)),
                width=5 + (band == 0),
            )

    layer = layer.filter(ImageFilter.GaussianBlur(0.42))
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
    # Vertical separation is intentionally visually exaggerated (not a
    # dimensional scale claim) so a phone viewer can see contact disappear.
    cy = cy_ground - radius * 0.42 * lift

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

    # Large rotating spokes make real wheel motion legible at 1080x1920.
    # They rotate with the tire; the camera and lighting remain fixed.
    phase = micro * math.tau * spin_speed
    for i in range(8):
        a = phase * 0.96 + i * math.tau / 8
        x1 = cx + math.cos(a) * hub * 1.35
        y1 = cy + math.sin(a) * hub * 1.35
        x2 = cx + math.cos(a) * rim * 0.88
        y2 = cy + math.sin(a) * rim * 0.88
        d.line((x1, y1, x2, y2), fill=(218, 226, 230, 225), width=12)

    # Rotating tread blocks. Motion is continuous even after the story state
    # settles, so long narration beats never turn into a held diagram.
    for i in range(40):
        a = (i / 40.0) * math.tau + phase
        x1 = cx + math.cos(a) * radius * 0.91
        y1 = cy + math.sin(a) * radius * 0.91
        x2 = cx + math.cos(a) * radius * 1.02
        y2 = cy + math.sin(a) * radius * 1.02
        alpha = int((108 + 142 * max(0.0, math.sin(a))) * tread_visibility)
        d.line((x1, y1, x2, y2), fill=(188, 199, 204, alpha), width=8)

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
    length = radius * (0.42 + 1.18 * c)
    y = road_y - 4
    alpha = int(65 + 155 * c)
    color = (87, 225, 176, alpha) if c > 0.48 else (255, 177, 87, alpha)
    width = max(7, int(10 + 10 * c + 3 * pulse))
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

    lead_x = cx + radius * 0.56
    tip_x = cx + radius * (1.88 + 0.40 * a)
    top_y = road_y - radius * (0.08 + 0.52 * a)
    wave = radius * 0.020 * math.sin(math.tau * 1.1 * micro)
    poly = [
        (cx - radius * 0.45, road_y - 5),
        (lead_x, road_y - 4),
        (tip_x, top_y + wave),
        (tip_x + radius * 0.12, road_y + 2),
    ]
    d.polygon(poly, fill=(24, 137, 188, int(98 + 132 * a)))
    d.line(poly[:3], fill=(171, 241, 252, int(175 + 70 * a)), width=max(4, int(radius * 0.030)))

    # Coherent moving pressure bands inside the wedge.
    for i in range(12):
        phase = (micro * (0.86 + 0.035 * i) + i * 0.091) % 1.0
        x = lead_x + (tip_x - lead_x) * phase
        local = 1.0 - phase
        h = radius * (0.08 + 0.25 * a * local)
        d.line(
            (x, road_y - 3, x, road_y - h),
            fill=(114, 226, 248, int((78 + 138 * p) * (0.55 + 0.45 * local))),
            width=7,
        )

    # Upward water-pressure arrows under the tire.
    for i in range(6):
        x = cx - radius * 0.44 + i * radius * 0.18
        h = radius * (0.09 + 0.21 * p) * (0.86 + 0.10 * math.sin(micro * 4.0 + i))
        d.line((x, road_y - 4, x, road_y - h), fill=(95, 220, 246, int(95 + 150 * p)), width=6)
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

    count = 156
    for i in range(count):
        base = i / count
        phase = (base + micro * (0.32 + 0.17 * speed) * (0.85 + (i % 5) * 0.035)) % 1.0
        side = -1.0 if i % 2 else 1.0
        x = cx + radius * (0.48 + 2.15 * phase)
        y = road_y - radius * (0.04 + 0.48 * math.sin(math.pi * phase) * strength)
        y += side * radius * 0.035 * math.sin(i * 1.7 + micro * 6.0)
        rr = 4.0 + 7.5 * (1.0 - phase)
        alpha = int((62 + 180 * math.sin(math.pi * phase)) * strength)
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(178, 238, 250, alpha))
        if i % 3 == 0:
            d.line(
                (x - radius * 0.20, y + radius * 0.04, x, y),
                fill=(130, 226, 246, int(alpha * 0.72)),
                width=4,
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
    for lane in (-0.34, -0.17, 0.0, 0.17, 0.34):
        start_x = cx + radius * (0.58 + lane * 0.15)
        start_y = road_y - radius * (0.08 + abs(lane) * 0.03)
        for j in range(7):
            q = (micro * 0.58 + j / 7.0 + lane * 0.21) % 1.0
            x = start_x - radius * 0.88 * q
            y = start_y + lane * radius * 0.40 + math.sin(q * math.pi) * radius * 0.06
            rr = 6.5
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(151, 240, 252, int(205 * s)))
    d.line(
        (cx - radius * 0.45, road_y - radius * 0.12,
         cx + radius * 0.60, road_y - radius * 0.12),
        fill=(65, 190, 228, int(110 * s)),
        width=9,
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

    # Bright requested steering direction: this remains visible even when the
    # road can no longer deliver the requested lateral force.
    box = (
        cx - radius * 1.28,
        cy - radius * 1.18,
        cx + radius * 1.02,
        cy + radius * 1.10,
    )
    d.arc(box, 192, 282, fill=(235, 242, 246, 220), width=10)
    ax = cx - radius * 1.11
    ay = cy - radius * 0.62
    d.polygon(
        [(ax, ay), (ax + 22, ay - 9), (ax + 15, ay + 18)],
        fill=(240, 246, 249, 225),
    )

    c = _clamp01(contact)

    # Requested lateral force is shown as a long translucent arrow.
    req_y = cy + radius * 0.66
    req_x0 = cx + radius * 0.52
    req_x1 = cx - radius * 0.72
    d.line(
        (req_x0, req_y, req_x1, req_y),
        fill=(234, 225, 174, 105),
        width=9,
    )
    d.polygon(
        [(req_x1 - 15, req_y), (req_x1 + 5, req_y - 10), (req_x1 + 5, req_y + 10)],
        fill=(238, 228, 181, 105),
    )

    # Actual force collapses with road contact. Keeping this small, saturated
    # arrow next to the long request arrow makes the loss readable instantly.
    actual_len = radius * (0.06 + 0.48 * c)
    actual_y = cy + radius * 0.83
    actual_x0 = cx + radius * 0.34
    actual_x1 = actual_x0 - actual_len
    pulse = 0.90 + 0.10 * math.sin(micro * 4.2)
    alpha = int((85 + 165 * c) * pulse)
    d.line(
        (actual_x0, actual_y, actual_x1, actual_y),
        fill=(255, 174, 83, alpha),
        width=10,
    )
    d.polygon(
        [(actual_x1 - 13, actual_y), (actual_x1 + 4, actual_y - 9), (actual_x1 + 4, actual_y + 9)],
        fill=(255, 195, 112, alpha),
    )

    layer = layer.filter(ImageFilter.GaussianBlur(0.28))
    image.alpha_composite(layer)


def _draw_final_comparison_ghost(
    image: Image.Image,
    micro: float,
    cx: float,
    cy: float,
    road_y: int,
    radius: float,
) -> None:
    """Show normal wet contact and a hydroplaning reference simultaneously.

    The main tire stays physically grounded. A smaller translucent reference
    wheel to the right rides on a visible water wedge with a broken contact
    mark, so the ending contains genuinely new comparative information rather
    than replaying the opening wet-contact state.
    """
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, "RGBA")

    gr = radius * 0.62
    gx = min(image.size[0] - gr * 1.05, cx + radius * 1.42)
    ground_cy = road_y - gr * 0.88
    gy = ground_cy - gr * 0.34

    d.ellipse(
        (gx - gr, gy - gr, gx + gr, gy + gr),
        fill=(15, 29, 36, 58),
        outline=(105, 214, 236, 185),
        width=6,
    )
    inner = gr * 0.53
    d.ellipse(
        (gx - inner, gy - inner, gx + inner, gy + inner),
        outline=(165, 230, 242, 135),
        width=4,
    )

    # Moving high-pressure wedge under the ghost reference.
    wave = gr * 0.035 * math.sin(micro * math.tau * 0.62)
    wedge = [
        (gx - gr * 0.52, road_y - 4),
        (gx + gr * 0.35, road_y - 4),
        (gx + gr * 1.36, road_y - gr * 0.42 + wave),
        (gx + gr * 1.46, road_y + 1),
    ]
    d.polygon(wedge, fill=(32, 151, 198, 125))
    d.line(wedge[:3], fill=(166, 238, 250, 205), width=6)

    # Broken red contact cue for the lifted reference wheel.
    y = road_y - 4
    d.line((gx - gr * 0.40, y, gx - gr * 0.12, y), fill=(255, 105, 86, 210), width=7)
    d.line((gx + gr * 0.12, y, gx + gr * 0.40, y), fill=(255, 105, 86, 210), width=7)

    # Main grounded contact is reinforced as the "normal wet" reference.
    d.line(
        (cx - radius * 0.64, road_y - 4, cx + radius * 0.64, road_y - 4),
        fill=(93, 232, 178, 225),
        width=11,
    )

    layer = layer.filter(ImageFilter.GaussianBlur(0.45))
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
        speed = 0.58 + 0.20 * mix
        wedge = 0.42 + 0.58 * mix
        pressure = 0.30 + 0.58 * mix
        contact = 0.98 - 0.18 * mix
        lift = 0.02 + 0.14 * mix
        spray = 0.48 + 0.34 * mix
        drainage = 0.34

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
        speed = 0.34 + 0.62 * mix
        wetness = 0.86
        wedge = 0.24 + 0.76 * mix
        pressure = 0.18 + 0.82 * mix
        contact = 0.98 - 0.88 * mix
        lift = 0.04 + 0.76 * mix
        spray = 0.38 + 0.62 * mix
        drainage = 0.52 - 0.28 * mix

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
        osc = 0.5 + 0.5 * math.sin(micro * math.tau * 0.38)
        speed = 0.68 + 0.10 * osc
        wetness = 0.82
        wedge = 0.62 + 0.20 * osc
        pressure = 0.52 + 0.26 * osc
        contact = 0.62 - 0.34 * osc
        lift = 0.18 + 0.34 * osc
        spray = 0.72 + 0.18 * osc
        drainage = 0.54

    elif kind == "final_drive":
        # Grounded wet-contact reference used for the final A/B comparison.
        speed = 0.52
        wetness = 0.72
        wedge = 0.12
        pressure = 0.10
        contact = 1.00
        lift = 0.00
        spray = 0.40
        drainage = 1.00

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

    if kind == "final_drive":
        _draw_final_comparison_ghost(image, micro, cx, cy, road_y, radius)

    if kind == "braking_loss":
        # Requested braking force points opposite travel, but with almost no
        # tire-road contact the transmissible force collapses.
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, "RGBA")
        # Long translucent arrow = requested braking. Short saturated arrow
        # = force the nearly contactless tire can actually transmit.
        req_y = road_y - radius * 0.34
        req_x0 = cx + radius * 0.62
        req_x1 = cx - radius * 0.62
        d.line((req_x0, req_y, req_x1, req_y), fill=(240, 225, 180, 105), width=10)
        d.polygon([(req_x1 - 15, req_y), (req_x1 + 5, req_y - 10), (req_x1 + 5, req_y + 10)], fill=(242, 229, 187, 105))

        alpha = int(85 + 170 * contact)
        y = road_y - radius * 0.10
        x0 = cx + radius * 0.20
        x1 = x0 - radius * (0.08 + 0.42 * contact)
        d.line((x0, y, x1, y), fill=(255, 166, 78, alpha), width=10)
        d.polygon([(x1 - 12, y), (x1 + 4, y - 9), (x1 + 4, y + 9)], fill=(255, 193, 111, alpha))
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
        "water_wedge": 0.70,
        "contact_shrink": 0.78,
        "speed_ramp": 0.72,
        "pressure_lift": 0.72,
        "recover_contact": 0.86,
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
