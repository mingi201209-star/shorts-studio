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
# A shallow 3/4 angle keeps the surface texture visible without hiding the
# separation/wake mechanism behind a dramatic perspective.
OPTIMAL_GOLF_CAMERA = Camera(
    yaw=-0.24,
    pitch=-0.11,
    distance=7.20,
    focal=880.0,
    cx=345.0,
    cy=455.0,
)

KINDS = (
    "hero_dimples",
    "smooth_morph",
    "smooth_wake",
    "dimple_wake",
    "boundary_layer",
    "trip_turbulence",
    "attached_flow",
    "separation_compare",
    "wake_shrink",
    "drag_compare",
    "flight_payoff",
)


def camera_for(kind: str, t: float) -> Camera:
    """Every beat shares the same topic-optimized viewpoint."""
    _ = (kind, t)
    return OPTIMAL_GOLF_CAMERA


def _rgb(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.lstrip("#")
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))


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
) -> tuple[float, float, float]:
    camera = OPTIMAL_GOLF_CAMERA
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
    spec = np.exp(-(((dx + 0.34) / 0.17) ** 2 + ((dy + 0.36) / 0.12) ** 2))
    rgb += spec[..., None] * np.array([255.0, 255.0, 255.0])[None, None, :] * (0.56 * highlight)
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
        spin = _spin_matrix(t * math.tau * spin_speed)
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


def _draw_wake(image: Image.Image, sx: float, sy: float, sr: float, width: float, intensity: float) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    length = sr * 3.25
    for i in range(8):
        frac = i / 7.0
        cx = sx + sr * (0.62 + frac * 2.52)
        local = sr * width * (0.96 - 0.48 * frac)
        wobble = math.sin(i * 1.7) * sr * 0.035
        d.ellipse(
            (cx - sr * 0.36, sy - local + wobble, cx + sr * 0.52, sy + local + wobble),
            fill=(39, 169, 201, int((28 + 20 * (1.0 - frac)) * intensity)),
        )
    overlay = overlay.filter(ImageFilter.GaussianBlur(max(8, int(sr * 0.10))))
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
) -> None:
    _draw_wake(image, sx, sy, sr, wake_width, strength)
    base = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(base, "RGBA")
    offsets = (-1.25, -0.90, -0.58, -0.30, 0.30, 0.58, 0.90, 1.25)
    paths = []
    for j, off in enumerate(offsets):
        pts = _streamline_points(sx, sy, sr, off, attached, wake_width)
        paths.append(pts)
        d.line(pts, fill=(73, 192, 222, int(64 * strength)), width=max(2, int(sr * 0.012)))
        phase = (t * 1.55 + j * 0.11) % 1.0
        k = min(len(pts) - 2, int(phase * (len(pts) - 1)))
        px, py = pts[k]
        rr = max(2, int(sr * 0.020))
        d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(183, 246, 255, int(190 * strength)))
    base = base.filter(ImageFilter.GaussianBlur(0.55))
    image.alpha_composite(base)

    if boundary_glow > 0.0:
        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow, "RGBA")
        pad = sr * 1.035
        gd.arc(
            (sx - pad, sy - pad, sx + pad, sy + pad),
            206, 514,
            fill=(98, 235, 244, int(120 * boundary_glow)),
            width=max(4, int(sr * 0.035)),
        )
        glow = glow.filter(ImageFilter.GaussianBlur(max(3, int(sr * 0.018))))
        image.alpha_composite(glow)


def _draw_turbulence_particles(image: Image.Image, t: float, sx: float, sy: float, sr: float, amount: float) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    for i in range(24):
        phase = (i / 24.0 + t * 0.55) % 1.0
        ang = math.radians(198 + 155 * phase)
        rr = sr * (1.00 + 0.045 * math.sin((i * 1.7 + t * 7.0)))
        x = sx + math.cos(ang) * rr
        y = sy + math.sin(ang) * rr
        jitter = math.sin(i * 2.4 + t * 15.0) * sr * 0.022
        r = max(1.5, sr * 0.015)
        d.ellipse((x-r, y-r+jitter, x+r, y+r+jitter), fill=(165, 243, 248, int(120 * amount)))
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.8))
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


def render_golf_frame(kind: str, t: float, width: int = 980, height: int = 950) -> Image.Image:
    if kind not in KINDS:
        raise ValueError(f"unknown golf 3D kind: {kind}")
    for probe_kind in KINDS:
        for probe_t in (0.0, 0.5, 1.0):
            if camera_for(probe_kind, probe_t) != OPTIMAL_GOLF_CAMERA:
                raise RuntimeError(f"golf camera drift: {probe_kind} at {probe_t}")

    image = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    _draw_background(image, glow=1.0)

    if kind == "hero_dimples":
        sx, sy, sr = _draw_ball(image, t, dimple_strength=1.0, spin_speed=0.40)
        _draw_flow(image, t, sx, sy, sr, attached=0.92, wake_width=0.50, strength=0.96, boundary_glow=0.45)

    elif kind == "smooth_morph":
        amount = max(0.0, 1.0 - t)
        sx, sy, sr = _draw_ball(image, t, dimple_strength=amount, spin_speed=0.28)
        attached = 0.36 + 0.56 * amount
        wake = 1.18 - 0.68 * amount
        _draw_flow(image, t, sx, sy, sr, attached=attached, wake_width=wake, strength=1.0, boundary_glow=0.25 * amount)

    elif kind == "smooth_wake":
        sx, sy, sr = _draw_ball(image, t, dimple_strength=0.0, spin_speed=0.0)
        _draw_flow(image, t, sx, sy, sr, attached=0.30, wake_width=1.22, strength=1.0)

    elif kind == "dimple_wake":
        grow = t * t * (3.0 - 2.0 * t)
        sx, sy, sr = _draw_ball(image, t, dimple_strength=grow, spin_speed=0.30)
        _draw_flow(
            image, t, sx, sy, sr,
            attached=0.32 + 0.60 * grow,
            wake_width=1.18 - 0.68 * grow,
            strength=1.0,
            boundary_glow=0.42 * grow,
        )

    elif kind == "boundary_layer":
        sx, sy, sr = _draw_ball(image, t, dimple_strength=1.0, spin_speed=0.18)
        _draw_flow(image, t, sx, sy, sr, attached=0.70, wake_width=0.72, strength=0.70, boundary_glow=0.95)
        _draw_turbulence_particles(image, t, sx, sy, sr, 0.70)

    elif kind == "trip_turbulence":
        pulse = 0.5 + 0.5 * math.sin(t * math.tau * 2.0)
        sx, sy, sr = _draw_ball(image, t, dimple_strength=1.0, spin_speed=0.22)
        _draw_flow(image, t, sx, sy, sr, attached=0.78 + 0.10 * t, wake_width=0.70 - 0.16 * t, strength=0.86, boundary_glow=0.72)
        _draw_turbulence_particles(image, t, sx, sy, sr, 0.72 + 0.24 * pulse)

    elif kind == "attached_flow":
        sx, sy, sr = _draw_ball(image, t, dimple_strength=1.0, spin_speed=0.26)
        _draw_flow(image, t, sx, sy, sr, attached=0.96, wake_width=0.48, strength=0.98, boundary_glow=0.55)

    elif kind == "separation_compare":
        # Same optimized viewpoint, two vertically separated states.
        for idx, (cy_world, dimples, attached, wake) in enumerate(((1.35, 0.0, 0.30, 1.10), (-1.35, 1.0, 0.94, 0.48))):
            sx, sy, sr = _draw_ball(
                image, t + idx * 0.13,
                center=(0.0, cy_world, 0.0),
                radius=0.90,
                dimple_strength=dimples,
                spin_speed=0.24,
            )
            _draw_flow(image, t, sx, sy, sr, attached=attached, wake_width=wake, strength=0.82, boundary_glow=0.30 * dimples)

    elif kind == "wake_shrink":
        mix = t * t * (3.0 - 2.0 * t)
        sx, sy, sr = _draw_ball(image, t, dimple_strength=1.0, spin_speed=0.30)
        _draw_flow(
            image, t, sx, sy, sr,
            attached=0.42 + 0.52 * mix,
            wake_width=1.04 - 0.58 * mix,
            strength=1.0,
            boundary_glow=0.48,
        )

    elif kind == "drag_compare":
        for idx, (cy_world, dimples, attached, wake) in enumerate(((1.25, 0.0, 0.30, 1.18), (-1.25, 1.0, 0.95, 0.46))):
            sx, sy, sr = _draw_ball(
                image, t + idx * 0.09,
                center=(0.0, cy_world, 0.0),
                radius=0.88,
                dimple_strength=dimples,
                spin_speed=0.24,
            )
            _draw_flow(image, t, sx, sy, sr, attached=attached, wake_width=wake, strength=0.90, boundary_glow=0.35 * dimples)
            # Pressure-drag cue: larger rear low-pressure glow for the smooth ball.
            rear = Image.new("RGBA", image.size, (0, 0, 0, 0))
            rd = ImageDraw.Draw(rear, "RGBA")
            rr = sr * (0.70 if dimples == 0.0 else 0.34)
            rd.ellipse((sx + sr * 0.58, sy - rr, sx + sr * 1.55, sy + rr), fill=(219, 70, 66, 55 if dimples == 0.0 else 24))
            rear = rear.filter(ImageFilter.GaussianBlur(max(6, int(sr * 0.09))))
            image.alpha_composite(rear)

    elif kind == "flight_payoff":
        # One continuous physical story: the dimpled ball keeps its compact wake
        # and carries farther across the same fixed camera frame.
        travel = 0.55 * t
        center = (travel, 0.0, 0.0)
        sx, sy, sr = _draw_ball(image, t, center=center, dimple_strength=1.0, spin_speed=0.42)
        _draw_flow(image, t, sx, sy, sr, attached=0.95, wake_width=0.46, strength=0.92, boundary_glow=0.42)
        trail = Image.new("RGBA", image.size, (0, 0, 0, 0))
        td = ImageDraw.Draw(trail, "RGBA")
        for i in range(4):
            q = max(0.0, t - 0.10 * (i + 1))
            if q <= 0:
                continue
            ghost_center = (0.55 * q, 0.0, 0.0)
            gx, gy, gr = _ball_geometry(ghost_center, 1.52, OPTIMAL_GOLF_CAMERA)
            td.ellipse((gx-gr*0.84, gy-gr*0.84, gx+gr*0.84, gy+gr*0.84), outline=(135, 222, 238, 45), width=2)
        image.alpha_composite(trail)

    return image


def render_golf_motion(
    kind: str,
    out_path: str | Path,
    *,
    duration: float = 3.2,
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
    try:
        for i in range(frames):
            t = i / max(1, frames - 1)
            frame = render_golf_frame(kind, t, width=width, height=height).convert("RGB")
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
