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


# Topic-specific composition, not a global camera preset.
# The golf ball sits left of center so its dimples remain large on mobile while
# the downstream wake has enough horizontal room to stay readable.
# The camera is fixed slightly above the ball and looks diagonally downward:
# enough 3D depth to read the spherical surface, without turning the airflow
# explanation into a perspective-heavy camera move.
OPTIMAL_GOLF_CAMERA = Camera(
    yaw=-0.34,
    pitch=-0.22,
    distance=7.35,
    focal=895.0,
    cx=340.0,
    cy=475.0,
)

KINDS = (
    "hero_dimples",
    "smooth_morph",
    "smooth_wake",
    "boundary_layer",
    "separation_compare",
    "wake_compare",
    "dimple_wake",
    "trip_turbulence",
    "attached_flow",
    "wake_shrink",
    "drag_compare",
    "flight_payoff_setup",
    "flight_payoff",
)


def camera_for(kind: str, t: float) -> Camera:
    """Every beat shares the same topic-optimized viewpoint."""
    _ = (kind, t)
    return OPTIMAL_GOLF_CAMERA



def _rgb(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.lstrip("#")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _smoothstep(value: float) -> float:
    u = _clamp01(value)
    return u * u * (3.0 - 2.0 * u)


def _smootherstep(value: float) -> float:
    u = _clamp01(value)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def _ease_out_cubic(value: float) -> float:
    u = _clamp01(value)
    return 1.0 - (1.0 - u) ** 3


def _micro_time(t: float, time_seconds: float | None) -> float:
    # render_golf_frame remains convenient for unit tests that only pass t,
    # while production passes real elapsed seconds so secondary motion never
    # slows down merely because the source clip was made longer.
    return float(time_seconds) if time_seconds is not None else float(t) * 3.2

def _rotation(yaw: float, pitch: float) -> np.ndarray:
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=float)
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]], dtype=float)
    return rx @ ry


def _project(points: np.ndarray, camera: Camera) -> tuple[np.ndarray, np.ndarray]:
    p = points @ _rotation(camera.yaw, camera.pitch).T
    z = camera.distance - p[:, 2]
    z = np.maximum(z, 0.35)
    scale = camera.focal / z
    xy = np.column_stack((camera.cx + p[:, 0] * scale, camera.cy - p[:, 1] * scale))
    return xy, z


def _ball_geometry(
    center: tuple[float, float, float],
    radius: float,
    camera: Camera,
) -> tuple[float, float, float]:
    cx, cy, cz = center
    probes = np.array(
        [[cx, cy, cz], [cx + radius, cy, cz], [cx, cy + radius, cz]],
        dtype=float,
    )
    xy, _ = _project(probes, camera)
    r = max(8.0, float(np.linalg.norm(xy[1] - xy[0])))
    ry = max(8.0, float(np.linalg.norm(xy[2] - xy[0])))
    return float(xy[0, 0]), float(xy[0, 1]), (r + ry) * 0.5


def _fibonacci_normals(count: int = 148) -> np.ndarray:
    out = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(count):
        y = 1.0 - (2.0 * i + 1.0) / count
        r = math.sqrt(max(0.0, 1.0 - y * y))
        phi = i * golden
        out.append((math.cos(phi) * r, y, math.sin(phi) * r))
    return np.array(out, dtype=float)


_DIMPLE_NORMALS = _fibonacci_normals()


def _spin_matrix(angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    ry = np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]], dtype=float)
    tilt = 0.18
    ct, st = math.cos(tilt), math.sin(tilt)
    rz = np.array([[ct, -st, 0.0], [st, ct, 0.0], [0.0, 0.0, 1.0]], dtype=float)
    return rz @ ry


def _draw_background(image: Image.Image, glow: float = 0.0) -> None:
    w, h = image.size
    yy = np.linspace(0.0, 1.0, h)[:, None]
    top = np.array([2.0, 8.0, 15.0])
    bottom = np.array([0.0, 2.0, 7.0])
    arr = top[None, None, :] * (1.0 - yy[..., None]) + bottom[None, None, :] * yy[..., None]
    arr = np.repeat(arr, w, axis=1)
    if glow > 0.0:
        xx = np.linspace(-1.0, 1.0, w)[None, :]
        gy = np.linspace(-1.0, 1.0, h)[:, None]
        g = np.exp(-((xx - 0.18) ** 2 / 0.44 + (gy + 0.05) ** 2 / 0.55))
        arr += g[..., None] * np.array([2.0, 16.0, 22.0])[None, None, :] * glow
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    image.paste(Image.fromarray(arr, mode="RGB").convert("RGBA"))



def _draw_ball(
    image: Image.Image,
    t: float,
    *,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    radius: float = 1.52,
    dimple_strength: float = 1.0,
    spin_speed: float = 0.30,
    highlight: float = 1.0,
    time_seconds: float | None = None,
) -> tuple[float, float, float]:
    camera = OPTIMAL_GOLF_CAMERA
    micro = _micro_time(t, time_seconds)
    sx, sy, sr = _ball_geometry(center, radius, camera)
    pad = int(sr * 1.12) + 6
    left = max(0, int(sx - pad))
    top = max(0, int(sy - pad))
    right = min(image.width, int(sx + pad))
    bottom = min(image.height, int(sy + pad))
    yy, xx = np.mgrid[top:bottom, left:right]
    dx = (xx - sx) / max(sr, 1.0)
    dy = (yy - sy) / max(sr, 1.0)
    r2 = dx * dx + dy * dy
    mask = r2 <= 1.0
    nz = np.sqrt(np.clip(1.0 - r2, 0.0, 1.0))

    key = np.clip(0.38 + 0.54 * (-0.46 * dx - 0.60 * dy + 0.74 * nz), 0.10, 1.0)
    fresnel = np.power(np.clip(1.0 - nz, 0.0, 1.0), 1.8)
    base = np.array([221.0, 228.0, 232.0])
    cool = np.array([88.0, 169.0, 199.0])
    rgb = base[None, None, :] * (0.56 + 0.52 * key[..., None])
    rgb += cool[None, None, :] * (0.14 * fresnel[..., None])
    # Keep the light fixed in world space. Only a tiny intensity breathing is
    # allowed; the apparent motion must come from the ball texture itself.
    highlight_gain = highlight * (0.975 + 0.025 * math.sin(math.tau * 0.41 * micro))
    spec = np.exp(-(((dx + 0.34) / 0.17) ** 2 + ((dy + 0.36) / 0.12) ** 2))
    rgb += spec[..., None] * np.array([255.0, 255.0, 255.0])[None, None, :] * (0.56 * highlight_gain)
    rgb = np.clip(rgb, 0.0, 255.0)

    rgba = np.zeros((bottom - top, right - left, 4), dtype=np.uint8)
    rgba[..., :3] = rgb.astype(np.uint8)
    rgba[..., 3] = (mask * 255).astype(np.uint8)
    image.alpha_composite(Image.fromarray(rgba, mode="RGBA"), (left, top))

    rim = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim, "RGBA")
    rd.ellipse(
        (sx - sr, sy - sr, sx + sr, sy + sr),
        outline=(219, 244, 251, 165),
        width=max(2, int(sr * 0.014)),
    )
    image.alpha_composite(rim)

    if dimple_strength > 0.01:
        # spin_speed is rotations/second. This is deliberately independent of
        # the one-shot story progress so a completed explanation state keeps
        # gently moving for the full narration beat.
        spin = _spin_matrix(micro * math.tau * spin_speed)
        normals = _DIMPLE_NORMALS @ spin.T
        cam_rot = _rotation(camera.yaw, camera.pitch)
        cam_normals = normals @ cam_rot.T
        visible = cam_normals[:, 2] > 0.08
        nvis = normals[visible]
        cvis = cam_normals[visible]
        points = np.array(center, dtype=float)[None, :] + nvis * (radius * 0.985)
        xy, depth = _project(points, camera)
        order = np.argsort(depth)[::-1]
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay, "RGBA")
        for idx in order:
            px, py = xy[idx]
            face = max(0.0, min(1.0, float(cvis[idx, 2])))
            if face <= 0.05:
                continue
            rr = max(2.0, sr * (0.030 + 0.010 * face) * dimple_strength)
            ry = rr * (0.45 + 0.48 * face)
            shade = int(55 + 62 * (1.0 - face))
            alpha = int((78 + 94 * face) * dimple_strength)
            d.ellipse((px - rr, py - ry, px + rr, py + ry), fill=(shade, shade + 7, shade + 11, alpha))
            hi = rr * 0.48
            d.arc(
                (px - hi, py - ry * 0.56, px + hi, py + ry * 0.28),
                200, 332,
                fill=(235, 246, 249, int(68 * face * dimple_strength)),
                width=1,
            )
        overlay = overlay.filter(ImageFilter.GaussianBlur(0.35))
        image.alpha_composite(overlay)

    return sx, sy, sr

def _bezier(p0, p1, p2, p3, n=44):
    pts = []
    for i in range(n):
        u = i / (n - 1)
        a = (1 - u) ** 3
        b = 3 * (1 - u) ** 2 * u
        c = 3 * (1 - u) * u ** 2
        d = u ** 3
        pts.append((
            a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
            a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
        ))
    return pts



def _sample_path(points: list[tuple[float, float]], phase: float) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]
    u = phase % 1.0
    pos = u * (len(points) - 1)
    lo = int(math.floor(pos))
    hi = min(len(points) - 1, lo + 1)
    f = pos - lo
    return (
        points[lo][0] * (1.0 - f) + points[hi][0] * f,
        points[lo][1] * (1.0 - f) + points[hi][1] * f,
    )


def _draw_wake(
    image: Image.Image,
    micro_t: float,
    sx: float,
    sy: float,
    sr: float,
    width: float,
    intensity: float,
    *,
    vortex_count: int = 8,
    length_scale: float = 1.0,
) -> None:
    """Coherent downstream wake with a readable but calm motion hierarchy.

    The wake is deliberately continuous, not frame-random noise: a broad
    low-frequency volume breathes slightly while longer-lived vortices convect
    downstream. This makes the flow easy to track on a phone without looking
    like flicker or a particle effect pasted on top.
    """
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")

    breathe = 1.0 + 0.100 * math.sin(math.tau * 0.73 * micro_t)
    eff_width = width * breathe
    sway_y = sr * 0.080 * math.sin(math.tau * 0.47 * micro_t + 0.4)
    sway_x = sr * 0.060 * math.sin(math.tau * 0.39 * micro_t)

    env_rx = sr * 1.36 * length_scale
    env_ry = sr * max(0.18, eff_width * 0.74)
    env_cx = sx + sr * 1.82 * length_scale + sway_x
    env_cy = sy + sway_y
    d.ellipse(
        (env_cx - env_rx, env_cy - env_ry, env_cx + env_rx, env_cy + env_ry),
        fill=(19, 111, 134, int(32 * intensity)),
    )

    for i in range(vortex_count):
        rate = 0.24 + 0.018 * (i % 3)
        age = (micro_t * rate + i / max(1, vortex_count)) % 1.0
        x = sx + sr * (0.56 + 2.82 * length_scale * age)
        envelope = eff_width * (0.98 - 0.42 * age)
        side = -1.0 if i % 2 else 1.0
        y = (
            sy
            + side * sr * envelope * (0.18 + 0.24 * math.sin(math.pi * age))
            + sr * 0.070 * math.sin(math.tau * (0.61 * micro_t + i * 0.173))
        )
        size_x = sr * (0.26 + 0.22 * _smoothstep(age))
        size_y = sr * max(0.15, envelope * (0.28 + 0.17 * (1.0 - age)))
        life = math.sin(math.pi * age) ** 1.35
        alpha = int((36 + 78 * life) * intensity)
        d.ellipse(
            (x - size_x, y - size_y, x + size_x, y + size_y),
            fill=(36, 174, 202, max(0, min(175, alpha))),
        )

    overlay = overlay.filter(ImageFilter.GaussianBlur(max(7, int(sr * 0.075))))
    image.alpha_composite(overlay)


def _streamline_points(
    sx: float,
    sy: float,
    sr: float,
    offset: float,
    attached: float,
    wake_width: float,
) -> list[tuple[float, float]]:
    sign = -1.0 if offset < 0 else 1.0
    mag = abs(offset)
    y0 = sy + offset * sr * 1.28
    start = (25.0, y0)
    before = (sx - sr * 1.75, y0)
    shoulder = (sx - sr * 0.30, sy + sign * sr * (0.98 + 0.12 * mag))
    sep_x = sx + sr * (-0.04 + 0.92 * attached)
    sep_y = sy + sign * sr * (0.88 - 0.23 * attached + 0.18 * mag)
    end_y = sy + sign * sr * wake_width * (0.46 + 0.55 * mag)
    end = (image_right := 955.0, end_y)
    return _bezier(start, before, shoulder, (sep_x, sep_y), 26)[:-1] + _bezier(
        (sep_x, sep_y),
        (sx + sr * 1.35, sep_y),
        (sx + sr * 2.15, end_y),
        end,
        28,
    )



def _draw_flow(
    image: Image.Image,
    t: float,
    sx: float,
    sy: float,
    sr: float,
    *,
    attached: float,
    wake_width: float,
    strength: float = 1.0,
    boundary_glow: float = 0.0,
    time_seconds: float | None = None,
    vortex_count: int = 8,
) -> None:
    micro = _micro_time(t, time_seconds)
    _draw_wake(
        image,
        micro,
        sx,
        sy,
        sr,
        wake_width,
        strength,
        vortex_count=vortex_count,
    )

    glow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer, "RGBA")
    base = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(base, "RGBA")

    offsets = (-1.42, -1.18, -0.96, -0.74, -0.52, -0.30,
               0.30, 0.52, 0.74, 0.96, 1.18, 1.42)

    for j, off in enumerate(offsets):
        raw = _streamline_points(sx, sy, sr, off, attached, wake_width)
        pts = []
        for k, (px, py) in enumerate(raw):
            # Incoming air stays calm. Only the downstream half develops a
            # small coherent wave, so the viewer reads "flow around the ball"
            # rather than a vibrating diagram.
            downstream = _clamp01((px - (sx + sr * 0.05)) / max(sr * 2.8, 1.0))
            wave = (
                sr * 0.095 * downstream
                * math.sin(math.tau * (0.46 * micro - 0.72 * downstream + j * 0.071))
            )
            pts.append((px, py + wave))

        main_width = max(4, int(sr * 0.031))
        glow_width = max(main_width + 4, int(sr * 0.074))
        glow_draw.line(
            pts,
            fill=(55, 180, 208, int(34 * strength)),
            width=glow_width,
        )
        d.line(
            pts,
            fill=(77, 205, 229, int(138 * strength)),
            width=main_width,
        )

        # Two moving bright packets per streamline. They are longer than the
        # old beads, which makes direction legible without raising particle
        # count until the frame looks noisy.
        local_speed = 0.30 + 0.045 * (1.0 - min(1.0, abs(off) / 1.45)) + 0.010 * (j % 3)
        for packet in range(2):
            phase = (micro * local_speed + j * 0.097 + packet * 0.5) % 1.0
            q0 = (phase - 0.035) % 1.0
            q1 = (phase + 0.035) % 1.0
            p0 = _sample_path(pts, q0)
            p1 = _sample_path(pts, q1)
            d.line(
                (p0[0], p0[1], p1[0], p1[1]),
                fill=(205, 250, 255, int(220 * strength)),
                width=max(main_width + 3, int(sr * 0.045)),
            )
            for trail_i, alpha_scale in enumerate((0.52, 0.24)):
                q = (phase - (trail_i + 1) * 0.050) % 1.0
                px, py = _sample_path(pts, q)
                rr = max(2.5, sr * (0.022 - trail_i * 0.003))
                d.ellipse(
                    (px - rr, py - rr, px + rr, py + rr),
                    fill=(175, 239, 248, int(180 * strength * alpha_scale)),
                )

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(max(2, int(sr * 0.020))))
    image.alpha_composite(glow_layer)
    base = base.filter(ImageFilter.GaussianBlur(0.45))
    image.alpha_composite(base)

    if boundary_glow > 0.0:
        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow, "RGBA")
        pad = sr * 1.040
        pulse = 0.92 + 0.08 * math.sin(math.tau * 0.63 * micro)
        gd.arc(
            (sx - pad, sy - pad, sx + pad, sy + pad),
            190, 530,
            fill=(102, 239, 247, int(178 * boundary_glow * pulse)),
            width=max(6, int(sr * 0.058)),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(max(3, int(sr * 0.025))))
        image.alpha_composite(glow)


def _draw_turbulence_particles(
    image: Image.Image,
    t: float,
    sx: float,
    sy: float,
    sr: float,
    amount: float,
    *,
    time_seconds: float | None = None,
    count: int = 42,
) -> None:
    micro = _micro_time(t, time_seconds)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    for i in range(count):
        phase = (i / max(1, count) + micro * (0.20 + 0.012 * (i % 4))) % 1.0
        ang = math.radians(188 + 176 * phase)
        radial_jitter = 0.020 + 0.020 * math.sin(i * 1.71 + micro * 5.7)
        rr = sr * (1.015 + radial_jitter)
        x = sx + math.cos(ang) * rr
        y = sy + math.sin(ang) * rr
        tangential = sr * 0.026 * math.sin(i * 2.1 + micro * 8.2)
        px = x - math.sin(ang) * tangential
        py = y + math.cos(ang) * tangential
        radius = max(1.6, sr * 0.014)
        alpha = int((86 + 72 * (0.5 + 0.5 * math.sin(i * 0.73 + micro * 4.3))) * amount)
        d.line(
            (px - math.cos(ang) * radius * 2.4, py - math.sin(ang) * radius * 2.4, px, py),
            fill=(116, 224, 238, max(0, min(210, int(alpha * 0.45)))),
            width=max(1, int(radius)),
        )
        d.ellipse(
            (px - radius, py - radius, px + radius, py + radius),
            fill=(181, 247, 250, max(0, min(230, alpha))),
        )
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.65))
    image.alpha_composite(overlay)


def _draw_separation_markers(
    image: Image.Image,
    sx: float,
    sy: float,
    sr: float,
    attached: float,
    *,
    intensity: float = 1.0,
) -> None:
    """Warm accents show where the main flow leaves the surface.

    They are intentionally tiny compared with the wake; the marker is a visual
    cue, not a claim that separation itself emits light.
    """
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    x = sx + sr * (-0.08 + 0.96 * attached)
    yspan = sr * (0.76 - 0.20 * attached)
    halo_r = max(7.0, sr * 0.052)
    dot_r = max(3.0, sr * 0.020)
    for y in (sy - yspan, sy + yspan):
        d.ellipse(
            (x - halo_r, y - halo_r, x + halo_r, y + halo_r),
            fill=(242, 137, 66, int(58 * intensity)),
        )
        d.ellipse(
            (x - dot_r, y - dot_r, x + dot_r, y + dot_r),
            fill=(255, 194, 108, int(220 * intensity)),
        )
    overlay = overlay.filter(ImageFilter.GaussianBlur(1.6))
    image.alpha_composite(overlay)


def _draw_pressure_region(
    image: Image.Image,
    micro_t: float,
    sx: float,
    sy: float,
    sr: float,
    *,
    scale: float,
    intensity: float,
) -> None:
    pulse = 0.88 + 0.12 * math.sin(math.tau * 0.57 * micro_t)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    rx = sr * (0.58 + 0.58 * scale) * pulse
    ry = sr * (0.36 + 0.46 * scale) * pulse
    cx = sx + sr * (0.92 + 0.20 * scale)
    d.ellipse(
        (cx - rx, sy - ry, cx + rx, sy + ry),
        fill=(211, 78, 69, int(64 * intensity)),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(8, int(sr * 0.11))))
    image.alpha_composite(overlay)

def _draw_labels(image: Image.Image, left: str | None = None, right: str | None = None) -> None:
    if not left and not right:
        return
    d = ImageDraw.Draw(image, "RGBA")
    if left:
        d.rounded_rectangle((36, 55, 248, 115), radius=18, fill=(4, 10, 18, 165), outline=(92, 197, 220, 90), width=2)
        d.text((142, 85), left, fill=(222, 245, 250, 235), anchor="mm")
    if right:
        d.rounded_rectangle((710, 55, 944, 115), radius=18, fill=(4, 10, 18, 165), outline=(92, 197, 220, 90), width=2)
        d.text((827, 85), right, fill=(222, 245, 250, 235), anchor="mm")



def render_golf_frame(
    kind: str,
    t: float,
    width: int = 980,
    height: int = 950,
    *,
    time_seconds: float | None = None,
) -> Image.Image:
    if kind not in KINDS:
        raise ValueError(f"unknown golf 3D kind: {kind}")
    for probe_kind in KINDS:
        for probe_t in (0.0, 0.5, 1.0):
            if camera_for(probe_kind, probe_t) != OPTIMAL_GOLF_CAMERA:
                raise RuntimeError(f"golf camera drift: {probe_kind} at {probe_t}")

    story = _clamp01(t)
    micro = _micro_time(story, time_seconds)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    _draw_background(image, glow=1.0)

    if kind == "hero_dimples":
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=1.0, spin_speed=0.34, time_seconds=micro
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=0.92, wake_width=0.50, strength=1.00, boundary_glow=0.42,
            time_seconds=micro, vortex_count=8,
        )

    elif kind == "smooth_morph":
        mix = story
        amount = 1.0 - mix
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=amount, spin_speed=0.30, time_seconds=micro
        )
        attached = 0.92 - 0.44 * mix
        wake = 0.50 + 0.48 * mix
        _draw_flow(
            image, story, sx, sy, sr,
            attached=attached, wake_width=wake, strength=1.08,
            boundary_glow=0.42 * amount, time_seconds=micro, vortex_count=9,
        )
        _draw_separation_markers(image, sx, sy, sr, attached, intensity=0.55 + 0.45 * mix)
        _draw_pressure_region(
            image, micro, sx, sy, sr,
            scale=0.24 + 0.76 * mix, intensity=0.20 + 0.65 * mix,
        )

    elif kind == "smooth_wake":
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=0.0, spin_speed=0.0, time_seconds=micro
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=0.28, wake_width=1.30, strength=1.18, boundary_glow=0.0,
            time_seconds=micro, vortex_count=10,
        )
        _draw_separation_markers(image, sx, sy, sr, 0.28, intensity=1.0)
        _draw_pressure_region(image, micro, sx, sy, sr, scale=1.0, intensity=0.92)

    elif kind == "dimple_wake":
        mix = 0.25 + 0.75 * story
        attached = 0.42 + 0.38 * story
        wake = 1.12 - 0.40 * story
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=0.34 + 0.66 * mix, spin_speed=0.30,
            time_seconds=micro,
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=attached, wake_width=wake, strength=1.06,
            boundary_glow=0.24 + 0.22 * story, time_seconds=micro, vortex_count=9,
        )
        _draw_separation_markers(image, sx, sy, sr, attached, intensity=0.85)
        _draw_pressure_region(
            image, micro, sx, sy, sr,
            scale=0.84 - 0.34 * story, intensity=0.60 - 0.18 * story,
        )

    elif kind == "boundary_layer":
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=1.0, spin_speed=0.24, time_seconds=micro
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=0.64, wake_width=0.86, strength=0.94, boundary_glow=1.24,
            time_seconds=micro, vortex_count=8,
        )
        _draw_turbulence_particles(
            image, story, sx, sy, sr, 0.64, time_seconds=micro, count=44
        )

    elif kind == "trip_turbulence":
        pulse = 0.5 + 0.5 * math.sin(micro * math.tau * 0.82)
        attached = 0.72 + 0.14 * story
        wake = 0.78 - 0.16 * story
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=1.0, spin_speed=0.28, time_seconds=micro
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=attached, wake_width=wake, strength=1.08, boundary_glow=1.18,
            time_seconds=micro, vortex_count=9,
        )
        _draw_turbulence_particles(
            image, story, sx, sy, sr,
            0.96 + 0.22 * pulse, time_seconds=micro, count=108,
        )
        _draw_separation_markers(image, sx, sy, sr, attached, intensity=0.70)

    elif kind == "attached_flow":
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=1.0, spin_speed=0.30, time_seconds=micro
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=0.98, wake_width=0.42, strength=1.16, boundary_glow=0.34,
            time_seconds=micro, vortex_count=8,
        )
        # The boundary layer remains turbulent even while attached. Keep
        # those surface particles moving so this long explanation beat reads
        # as continuous airflow, not a held diagram.
        _draw_turbulence_particles(
            image, story, sx, sy, sr,
            0.82, time_seconds=micro, count=84,
        )
        _draw_separation_markers(image, sx, sy, sr, 0.97, intensity=0.78)

    elif kind == "separation_compare":
        # Continue from the preceding single dimpled-ball state instead of
        # popping instantly to a two-ball diagram. The existing dimpled ball
        # stays large and near the center while the smooth comparison state
        # grows out above it; both then settle into the fixed-camera split.
        # Hold the inherited single-ball state briefly, then split. Besides
        # feeling more continuous, this gives the compositor a stable source
        # anchor before the physical comparison begins.
        split = _smootherstep(_clamp01((story - 0.40) / 0.60))
        states = (
            (0.18 + 1.17 * split, 0.0, 0.28, 1.24, 0.26 + 0.64 * split),
            (-(0.08 + 1.27 * split), 1.0, 0.96, 0.46, 1.34 - 0.44 * split),
        )
        for idx, (cy_world, dimples, attached, wake, radius) in enumerate(states):
            if idx == 0 and split < 0.015:
                continue
            local_micro = micro + idx * 0.37
            sx, sy, sr = _draw_ball(
                image, story,
                center=(0.0, cy_world, 0.0),
                radius=radius,
                dimple_strength=dimples,
                spin_speed=0.26,
                time_seconds=local_micro,
            )
            _draw_flow(
                image, story, sx, sy, sr,
                attached=attached, wake_width=wake, strength=0.94,
                boundary_glow=0.36 * dimples, time_seconds=local_micro,
                vortex_count=7 if dimples else 9,
            )
            _draw_separation_markers(image, sx, sy, sr, attached, intensity=0.85)
            if dimples == 0.0:
                _draw_pressure_region(image, local_micro, sx, sy, sr, scale=0.92, intensity=0.72)

    elif kind == "wake_compare":
        # Consequence view after the separation comparison: one smooth ball
        # and a large coherent vortex street. The camera is unchanged; only
        # the phenomenon takes visual priority.
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=0.0, spin_speed=0.0, time_seconds=micro
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=0.26, wake_width=1.38, strength=1.30, boundary_glow=0.0,
            time_seconds=micro, vortex_count=12,
        )
        _draw_separation_markers(image, sx, sy, sr, 0.26, intensity=1.0)
        _draw_pressure_region(image, micro, sx, sy, sr, scale=1.10, intensity=1.0)

    elif kind == "wake_shrink":
        mix = story
        attached = 0.30 + 0.66 * mix
        wake = 1.36 - 0.90 * mix
        sx, sy, sr = _draw_ball(
            image, story, dimple_strength=1.0, spin_speed=0.31, time_seconds=micro
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=attached, wake_width=wake, strength=1.12,
            boundary_glow=0.44 + 0.14 * mix, time_seconds=micro, vortex_count=9,
        )
        _draw_separation_markers(image, sx, sy, sr, attached, intensity=0.84)
        _draw_pressure_region(
            image, micro, sx, sy, sr,
            scale=0.96 - 0.66 * mix, intensity=0.74 - 0.38 * mix,
        )

    elif kind == "drag_compare":
        # Same continuity rule as the separation comparison: start from the
        # dimpled state already on screen, then physically split into the
        # smooth-vs-dimple drag comparison without moving the camera.
        # As above, preserve the incoming dimpled state for the first few
        # frames before the smooth comparison grows out of it.
        split = _smootherstep(_clamp01((story - 0.40) / 0.60))
        states = (
            (0.18 + 1.07 * split, 0.0, 0.28, 1.26, 1.0, 0.26 + 0.62 * split),
            (-(0.08 + 1.17 * split), 1.0, 0.96, 0.46, 0.28, 1.32 - 0.44 * split),
        )
        for idx, (cy_world, dimples, attached, wake, pressure, radius) in enumerate(states):
            if idx == 0 and split < 0.015:
                continue
            local_micro = micro + idx * 0.29
            sx, sy, sr = _draw_ball(
                image, story,
                center=(0.0, cy_world, 0.0),
                radius=radius,
                dimple_strength=dimples,
                spin_speed=0.27,
                time_seconds=local_micro,
            )
            _draw_flow(
                image, story, sx, sy, sr,
                attached=attached, wake_width=wake, strength=0.96,
                boundary_glow=0.34 * dimples, time_seconds=local_micro,
                vortex_count=7 if dimples else 9,
            )
            _draw_pressure_region(
                image, local_micro, sx, sy, sr,
                scale=pressure, intensity=0.78 if dimples == 0.0 else 0.36,
            )

    elif kind == "flight_payoff_setup":
        # Begin the payoff as one continuous physical move instead of holding
        # a diagram and then cutting to flight. Use a steady physical carry
        # rather than an ease-to-stop so every half-second still contains
        # visible object motion while the camera remains completely fixed.
        lead = min(1.0, micro / 2.7)
        center = (-0.82 + 0.72 * lead, 0.0, 0.0)
        sx, sy, sr = _draw_ball(
            image, story, center=center, dimple_strength=1.0, spin_speed=0.36,
            time_seconds=micro,
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=0.96, wake_width=0.44, strength=1.06, boundary_glow=0.36,
            time_seconds=micro, vortex_count=8,
        )
        ghosts = Image.new("RGBA", image.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(ghosts, "RGBA")
        for i, xw in enumerate((0.35, 0.82, 1.28, 1.72)):
            gx, gy, gr = _ball_geometry((xw, 0.0, 0.0), 1.52, OPTIMAL_GOLF_CAMERA)
            alpha = 54 - i * 9
            gd.ellipse(
                (gx - gr * 0.80, gy - gr * 0.80, gx + gr * 0.80, gy + gr * 0.80),
                outline=(137, 223, 238, max(16, alpha)),
                width=3,
            )
        ghosts = ghosts.filter(ImageFilter.GaussianBlur(0.7))
        image.alpha_composite(ghosts)

    elif kind == "flight_payoff":
        # Keep the camera fixed. The ball itself carries through the frame at
        # a readable near-constant speed, while rotation/flow/wake continue.
        # The wider travel makes motion legible on a phone without relying on
        # camera movement or crop/zoom churn.
        travel = min(1.0, micro / 3.4)
        center = (-0.10 + 1.90 * travel, 0.0, 0.0)
        sx, sy, sr = _draw_ball(
            image, story, center=center, dimple_strength=1.0, spin_speed=0.34,
            time_seconds=micro,
        )
        _draw_flow(
            image, story, sx, sy, sr,
            attached=0.96, wake_width=0.46, strength=1.04, boundary_glow=0.44,
            time_seconds=micro, vortex_count=8,
        )
        trail = Image.new("RGBA", image.size, (0, 0, 0, 0))
        td = ImageDraw.Draw(trail, "RGBA")
        for i in range(5):
            q = max(0.0, micro - 0.13 * (i + 1))
            q_travel = min(1.0, q / 3.4)
            ghost_center = (-0.10 + 1.90 * q_travel, 0.0, 0.0)
            gx, gy, gr = _ball_geometry(ghost_center, 1.52, OPTIMAL_GOLF_CAMERA)
            td.ellipse(
                (gx - gr * 0.84, gy - gr * 0.84, gx + gr * 0.84, gy + gr * 0.84),
                outline=(135, 222, 238, max(8, 48 - i * 8)),
                width=2,
            )
        image.alpha_composite(trail)

    return image

def render_golf_motion(
    kind: str,
    out_path: str | Path,
    *,
    duration: float = 5.0,
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
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    frames = max(2, round(duration * fps))

    # One-shot causal transitions finish promptly, then the secondary motion
    # time keeps running. This avoids both a frozen final state and the awkward
    # "morph starts over" seam that -stream_loop would expose.
    progress_seconds = {
        "smooth_morph": 0.90,
        "separation_compare": 0.85,
        "dimple_wake": 1.00,
        "trip_turbulence": 1.10,
        "wake_shrink": 1.00,
        "drag_compare": 0.85,
    }

    try:
        for i in range(frames):
            elapsed = i / fps
            transition = progress_seconds.get(kind)
            progress = _smootherstep(elapsed / transition) if transition else 1.0
            frame = render_golf_frame(
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
