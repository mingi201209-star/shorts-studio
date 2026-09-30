from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Camera:
    yaw: float = 0.0
    pitch: float = -0.22
    distance: float = 9.5
    focal: float = 760.0
    cx: float = 490.0
    cy: float = 470.0


def _rgb(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def _clamp8(v: float) -> int:
    return max(0, min(255, int(v)))


def _shade(color: tuple[int, int, int], light: float) -> tuple[int, int, int, int]:
    return tuple(_clamp8(c * light) for c in color) + (255,)


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
    s = camera.focal / z
    xy = np.column_stack((camera.cx + p[:, 0] * s, camera.cy - p[:, 1] * s))
    return xy, z


def _draw_mesh(
    image: Image.Image,
    verts: np.ndarray,
    faces: list[tuple[int, ...]],
    color: str,
    camera: Camera,
    alpha: int = 255,
    light_dir: np.ndarray | None = None,
    outline: str | None = None,
) -> None:
    light_dir = light_dir if light_dir is not None else np.array([-0.35, 0.65, 0.67], dtype=float)
    light_dir = light_dir / np.linalg.norm(light_dir)
    xy, depth = _project(verts, camera)
    base = _rgb(color)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")

    entries: list[tuple[float, tuple[int, ...], float]] = []
    for face in faces:
        pts = verts[list(face)]
        if len(face) >= 3:
            n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
            norm = np.linalg.norm(n)
            if norm > 1e-6:
                n = n / norm
                illum = 0.34 + 0.74 * max(0.0, float(np.dot(n, light_dir)))
            else:
                illum = 0.62
        else:
            illum = 0.62
        entries.append((float(depth[list(face)].mean()), face, illum))

    for _, face, illum in sorted(entries, reverse=True):
        pts2 = [tuple(xy[i]) for i in face]
        fill = _shade(base, illum)
        fill = fill[:3] + (alpha,)
        d.polygon(pts2, fill=fill)
        if outline:
            d.line(pts2 + [pts2[0]], fill=_rgb(outline) + (min(255, alpha + 25),), width=2)

    image.alpha_composite(overlay)


def _sphere_mesh(
    center: tuple[float, float, float],
    radius: tuple[float, float, float],
    lat_steps: int = 12,
    lon_steps: int = 24,
) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    cx, cy, cz = center
    rx, ry, rz = radius
    verts = []
    for i in range(lat_steps + 1):
        theta = math.pi * i / lat_steps
        st, ct = math.sin(theta), math.cos(theta)
        for j in range(lon_steps):
            phi = 2.0 * math.pi * j / lon_steps
            cp, sp = math.cos(phi), math.sin(phi)
            verts.append((cx + rx * st * cp, cy + ry * ct, cz + rz * st * sp))
    faces: list[tuple[int, int, int, int]] = []
    for i in range(lat_steps):
        for j in range(lon_steps):
            a = i * lon_steps + j
            b = i * lon_steps + (j + 1) % lon_steps
            c = (i + 1) * lon_steps + (j + 1) % lon_steps
            d = (i + 1) * lon_steps + j
            faces.append((a, b, c, d))
    return np.array(verts, dtype=float), faces


def _box_mesh(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> tuple[np.ndarray, list[tuple[int, int, int, int]]]:
    cx, cy, cz = center
    sx, sy, sz = (v / 2.0 for v in size)
    verts = np.array(
        [
            [cx - sx, cy - sy, cz - sz],
            [cx + sx, cy - sy, cz - sz],
            [cx + sx, cy + sy, cz - sz],
            [cx - sx, cy + sy, cz - sz],
            [cx - sx, cy - sy, cz + sz],
            [cx + sx, cy - sy, cz + sz],
            [cx + sx, cy + sy, cz + sz],
            [cx - sx, cy + sy, cz + sz],
        ],
        dtype=float,
    )
    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (3, 2, 6, 7),
        (1, 5, 6, 2),
        (0, 3, 7, 4),
    ]
    return verts, faces


def _draw_box(
    image: Image.Image,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    color: str,
    camera: Camera,
    outline: str | None = None,
) -> None:
    verts, faces = _box_mesh(center, size)
    _draw_mesh(image, verts, faces, color, camera, outline=outline)


def _draw_sphere(
    image: Image.Image,
    center: tuple[float, float, float],
    radius: float | tuple[float, float, float],
    color: str,
    camera: Camera,
    alpha: int = 255,
    outline: str | None = None,
) -> None:
    if isinstance(radius, (int, float)):
        radii = (float(radius), float(radius), float(radius))
    else:
        radii = tuple(float(v) for v in radius)
    verts, faces = _sphere_mesh(center, radii)
    _draw_mesh(image, verts, faces, color, camera, alpha=alpha, outline=outline)


def _draw_path(
    image: Image.Image,
    points: list[tuple[float, float, float]],
    color: str,
    camera: Camera,
    width: int = 8,
    arrow: bool = False,
    alpha: int = 255,
) -> None:
    pts = np.array(points, dtype=float)
    xy, _ = _project(pts, camera)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    c = _rgb(color) + (alpha,)
    d.line([tuple(v) for v in xy], fill=c, width=width, joint="curve")
    if arrow and len(xy) >= 2:
        p1, p2 = xy[-2], xy[-1]
        v = p2 - p1
        n = np.linalg.norm(v)
        if n > 1e-6:
            v = v / n
            left = np.array([-v[1], v[0]])
            tip = p2
            base = p2 - v * 22.0
            d.polygon(
                [
                    tuple(tip),
                    tuple(base + left * 12.0),
                    tuple(base - left * 12.0),
                ],
                fill=c,
            )
    image.alpha_composite(overlay)


def _camera_for(kind: str, t: float) -> Camera:
    sway = math.sin(t * math.pi * 2.0) * 0.035
    if kind == "contact_gap":
        return Camera(yaw=0.04 + sway, pitch=-0.03, distance=7.4, focal=900.0, cy=505.0)
    if kind == "glide":
        return Camera(yaw=-0.10 + sway, pitch=-0.95, distance=10.5, focal=760.0, cy=455.0)
    if kind == "protected_drop":
        return Camera(yaw=0.05 + sway, pitch=-0.06, distance=7.8, focal=870.0, cy=510.0)
    if kind == "threshold":
        return Camera(yaw=-0.03 + sway, pitch=-0.34, distance=11.3, focal=730.0, cy=470.0)
    return Camera(yaw=0.10 + sway, pitch=-0.25, distance=9.4, focal=780.0, cy=475.0)


def _draw_plate(image: Image.Image, camera: Camera, heat: float = 1.0, x: float = 0.0, z: float = 0.0, scale: float = 1.0) -> None:
    _draw_box(image, (x, -1.65, z), (6.8 * scale, 1.05, 4.4 * scale), "#3e474f", camera, outline="#7f8b95")
    glow = "#ff3d22" if heat >= 1.2 else "#ff744c"
    _draw_box(image, (x, -1.08, z), (6.55 * scale, 0.09, 4.15 * scale), glow, camera)
    if heat > 1.0:
        inner = "#ffad57" if heat < 1.3 else "#ffd166"
        _draw_box(image, (x, -1.00, z), (5.9 * scale, 0.035, 3.7 * scale), inner, camera)


def _draw_vapor_layer(
    image: Image.Image,
    camera: Camera,
    center: tuple[float, float, float] = (0.0, -0.60, 0.0),
    spread: float = 1.0,
    thickness: float = 0.20,
    alpha: int = 155,
) -> None:
    _draw_sphere(
        image,
        center,
        (2.25 * spread, thickness, 1.55 * spread),
        "#58d6e8",
        camera,
        alpha=alpha,
        outline="#bdf7ff",
    )


def _draw_heat_arrows(
    image: Image.Image,
    camera: Camera,
    count: int = 5,
    strength: float = 1.0,
    y0: float = -1.02,
    y1: float = -0.30,
    bend: float = 0.0,
) -> None:
    xs = np.linspace(-2.2, 2.2, count)
    for x in xs:
        endx = float(x + math.copysign(bend * (0.35 + abs(x) / 3.5), x if x != 0 else 1.0))
        _draw_path(
            image,
            [(float(x), y0, 0.25), (float(x), (y0 + y1) / 2.0, 0.15), (endx, y1, 0.05)],
            "#ffd166",
            camera,
            width=max(5, int(8 * strength)),
            arrow=True,
            alpha=min(255, int(190 + 50 * strength)),
        )


def render_diagram_frame(kind: str, t: float, width: int = 980, height: int = 950) -> Image.Image:
    image = Image.new("RGBA", (width, height), (7, 13, 19, 255))
    camera = _camera_for(kind, t)
    bob = 0.07 * math.sin(t * math.pi * 2.0)
    pulse = 0.5 + 0.5 * math.sin(t * math.pi * 2.0)

    if kind == "hook_result":
        _draw_plate(image, camera, 1.30)
        _draw_vapor_layer(image, camera, spread=0.90 + 0.08 * pulse, thickness=0.18 + 0.03 * pulse)
        _draw_sphere(image, (0.0, 0.62 + bob, 0.0), 1.05, "#2c78c9", camera, outline="#d9efff")

    elif kind == "skid_contrast":
        _draw_plate(image, camera, 1.20, x=-1.8, scale=0.47)
        _draw_plate(image, camera, 1.20, x=1.8, scale=0.47)
        left_r = max(0.22, 0.72 * (1.0 - 0.70 * t))
        _draw_sphere(image, (-1.8, 0.35 + 0.15 * t, 0.0), left_r, "#417aa6", camera, alpha=210)
        glide_x = 1.35 + 0.85 * t
        _draw_vapor_layer(image, camera, center=(glide_x, -0.58, 0.0), spread=0.34, thickness=0.12)
        _draw_sphere(image, (glide_x, 0.52 + 0.05 * math.sin(t * math.pi * 4.0), 0.0), 0.72, "#2c78c9", camera, outline="#d9efff")
        _draw_path(image, [(1.1, -0.35, 0.7), (1.6, -0.28, 0.5), (2.4, -0.16, 0.1)], "#58d6e8", camera, width=8, arrow=True)

    elif kind == "expectation":
        _draw_plate(image, camera, 1.05 + 0.35 * t)
        r = max(0.32, 1.05 * (1.0 - 0.60 * t))
        _draw_sphere(image, (0.0, 0.62 + 0.10 * t, 0.0), r, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=5, strength=0.75 + 0.45 * t, y1=0.18 + 0.10 * t)

    elif kind == "question_gap":
        _draw_plate(image, camera, 1.28, x=-1.65, scale=0.50)
        _draw_plate(image, camera, 1.28, x=1.65, scale=0.50)
        left_r = 0.62 * (1.0 - 0.45 * t)
        _draw_sphere(image, (-1.65, 0.34 + 0.22 * t, 0.0), max(0.28, left_r), "#4c6d84", camera, alpha=220)
        _draw_vapor_layer(image, camera, center=(1.65, -0.58, 0.0), spread=0.38 + 0.04 * pulse, thickness=0.13)
        _draw_sphere(image, (1.65, 0.56 + bob, 0.0), 0.74, "#2c78c9", camera, outline="#d9efff")

    elif kind == "vapor_hint":
        _draw_plate(image, camera, 1.22)
        _draw_sphere(image, (0.0, 0.68 + bob, 0.0), 1.03, "#2c78c9", camera, outline="#d9efff")
        grow = 0.18 + 0.55 * t
        _draw_sphere(image, (0.0, -0.63 + 0.04 * t, 0.0), (grow, 0.10 + 0.05 * t, grow * 0.70), "#58d6e8", camera, alpha=175)

    elif kind == "vapor_birth":
        _draw_plate(image, camera, 1.22)
        _draw_sphere(image, (0.0, 0.72 + 0.06 * t, 0.0), 1.04, "#2c78c9", camera, outline="#d9efff")
        for idx, x in enumerate(np.linspace(-1.45, 1.45, 5)):
            phase = (t + idx * 0.10) % 1.0
            y0 = -0.95
            y1 = -0.72 + 0.65 * phase
            _draw_path(image, [(float(x), y0, 0.0), (float(x) * 0.94, y1, 0.0)], "#58d6e8", camera, width=10, alpha=210)
            _draw_sphere(image, (float(x) * 0.94, y1, 0.0), (0.20, 0.12, 0.16), "#9feef6", camera, alpha=170)

    elif kind == "vapor_expand":
        _draw_plate(image, camera, 1.22)
        _draw_sphere(image, (0.0, 0.72 + bob, 0.0), 1.04, "#2c78c9", camera, outline="#d9efff")
        spread = 0.45 + 0.85 * t
        for j, x in enumerate(np.linspace(-1.65, 1.65, 7)):
            wob = 0.08 * math.sin((t * 5.0 + j) * math.pi)
            _draw_sphere(image, (float(x) * spread, -0.58 + wob, 0.0), (0.48, 0.14, 0.34), "#58d6e8", camera, alpha=145)

    elif kind == "vapor_cushion":
        _draw_plate(image, camera, 1.25)
        _draw_vapor_layer(image, camera, spread=0.55 + 0.55 * t, thickness=0.14 + 0.06 * t)
        _draw_sphere(image, (0.0, 0.46 + 0.48 * t + bob, 0.0), 1.05, "#2c78c9", camera, outline="#d9efff")

    elif kind == "no_contact":
        _draw_plate(image, camera, 1.25)
        _draw_vapor_layer(image, camera, spread=1.00 + 0.05 * pulse, thickness=0.18)
        _draw_sphere(image, (0.0, 0.68 + bob, 0.0), 1.04, "#2c78c9", camera, outline="#d9efff")

    elif kind == "contact_gap":
        _draw_plate(image, camera, 1.28)
        _draw_vapor_layer(image, camera, center=(0.0, -0.42, 0.0), spread=1.22, thickness=0.16 + 0.03 * pulse)
        _draw_sphere(image, (0.0, 0.96 + 0.08 * t, 0.0), (1.75, 1.45, 1.35), "#2c78c9", camera, outline="#d9efff")

    elif kind == "heat_blocked":
        _draw_plate(image, camera, 1.35)
        _draw_vapor_layer(image, camera, spread=1.12, thickness=0.20)
        _draw_sphere(image, (0.0, 0.72 + bob, 0.0), 1.03, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=5, strength=1.0, y1=-0.40, bend=0.85 + 0.35 * pulse)

    elif kind == "paradox_shield":
        image.paste((34, 8, 7, 255), (0, 0, width, height))
        _draw_plate(image, camera, 1.45)
        _draw_vapor_layer(image, camera, spread=1.05 + 0.08 * pulse, thickness=0.19)
        _draw_sphere(image, (0.0, 0.70 + bob, 0.0), 0.95, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=5, strength=1.15, y1=-0.36, bend=0.52)

    elif kind == "protected_drop":
        _draw_plate(image, camera, 1.38)
        _draw_vapor_layer(image, camera, center=(0.0, -0.36, 0.0), spread=1.25, thickness=0.20 + 0.03 * pulse)
        _draw_sphere(image, (0.0, 1.05 + 0.12 * t, 0.0), (1.75, 1.48, 1.45), "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=3, strength=0.90, y1=-0.22)

    elif kind == "glide":
        _draw_plate(image, camera, 1.25)
        ang = -0.85 + 1.55 * t
        x = 2.15 * math.sin(ang)
        z = 1.55 * math.cos(ang)
        _draw_vapor_layer(image, camera, center=(x, -0.56, z), spread=0.46, thickness=0.12)
        _draw_sphere(image, (x, 0.50 + 0.06 * math.sin(t * math.pi * 5.0), z), 0.72, "#2c78c9", camera, outline="#d9efff")
        path = []
        for q in np.linspace(0.0, t, 18):
            a = -0.85 + 1.55 * float(q)
            path.append((2.15 * math.sin(a), -0.48, 1.55 * math.cos(a)))
        if len(path) > 1:
            _draw_path(image, path, "#58d6e8", camera, width=8, alpha=205)

    elif kind == "support_force":
        _draw_plate(image, camera, 1.30)
        _draw_vapor_layer(image, camera, spread=1.00, thickness=0.18 + 0.02 * pulse)
        _draw_sphere(image, (0.0, 0.64 + 0.18 * t + bob, 0.0), 1.02, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=3, strength=0.95, y1=-0.18 + 0.08 * t)

    elif kind == "name":
        _draw_plate(image, camera, 1.26)
        _draw_vapor_layer(image, camera, spread=1.00 + 0.05 * pulse, thickness=0.18)
        _draw_sphere(image, (0.0, 0.70 + bob, 0.0), 1.05, "#2c78c9", camera, outline="#d9efff")
        d = ImageDraw.Draw(image, "RGBA")
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        except OSError:
            font = ImageFont.load_default()
        d.text((width // 2, 110), "LEIDENFROST", fill=(225, 245, 255, 245), anchor="mm", font=font)

    elif kind == "threshold":
        for idx, (x, heat, stable) in enumerate(((-2.2, 0.9, False), (0.0, 1.1, False), (2.2, 1.38, True))):
            _draw_plate(image, camera, heat, x=x, scale=0.30)
            _draw_sphere(image, (x, 0.22 + 0.07 * math.sin((t + idx * 0.2) * math.pi * 2.0), 0.0), 0.50, "#2c78c9", camera, outline="#d9efff")
            if stable:
                _draw_vapor_layer(image, camera, center=(x, -0.46, 0.0), spread=0.34 + 0.03 * pulse, thickness=0.10)

    elif kind == "payoff":
        _draw_plate(image, camera, 1.38)
        _draw_vapor_layer(image, camera, spread=1.08 + 0.08 * pulse, thickness=0.20 + 0.03 * pulse)
        x = 0.34 * math.sin(t * math.pi * 2.0)
        _draw_sphere(image, (x, 0.74 + 0.09 * math.sin(t * math.pi * 4.0), 0.0), 1.10, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=3, strength=0.85, y1=-0.26, bend=0.35)

    else:
        raise ValueError(f"unknown 3D diagram kind: {kind}")

    return image.convert("RGB")


def render_3d_motion(
    kind: str,
    out: Path,
    duration: float = 3.2,
    fps: int = 30,
    width: int = 980,
    height: int = 950,
) -> Path:
    frames = out.parent / f"{out.stem}_frames"
    frames.mkdir(parents=True, exist_ok=True)
    total = max(2, int(duration * fps))
    for i in range(total):
        t = i / (total - 1)
        frame = render_diagram_frame(kind, t, width=width, height=height)
        frame.save(frames / f"{i:04d}.png", quality=95)

    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames / "%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out),
        ],
        check=True,
        capture_output=True,
        timeout=180,
    )
    return out
