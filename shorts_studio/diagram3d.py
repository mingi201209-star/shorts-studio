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
    """Return a fixed camera for each 3D beat.

    ``t`` is intentionally ignored. All within-beat motion must come from the
    physical state itself (droplet, vapor, heat flow, glide path, etc.), never
    from orbiting, panning, zooming, or camera shake.
    """
    profiles = {
        "hook_result": (0.12, -0.28, 9.0, 810.0, 475.0),
        "skid_contrast": (-0.58, -0.42, 10.6, 750.0, 455.0),
        "expectation": (0.52, -0.18, 8.8, 820.0, 485.0),
        "question_gap": (-0.35, -0.62, 11.0, 760.0, 445.0),
        "vapor_hint": (0.62, -0.08, 8.0, 880.0, 510.0),
        "vapor_birth": (-0.68, -0.30, 9.4, 790.0, 480.0),
        "vapor_expand": (0.36, -0.52, 10.1, 770.0, 455.0),
        "vapor_cushion": (-0.18, -0.12, 8.2, 870.0, 505.0),
        "no_contact": (0.56, -0.38, 9.0, 810.0, 475.0),
        "contact_gap": (0.02, -0.03, 7.2, 920.0, 515.0),
        "heat_blocked": (-0.52, -0.26, 8.9, 830.0, 485.0),
        "paradox_shield": (0.68, -0.46, 10.2, 770.0, 455.0),
        "protected_drop": (0.06, -0.06, 7.6, 900.0, 515.0),
        "glide": (-0.12, -0.98, 10.5, 770.0, 455.0),
        "support_force": (-0.58, -0.18, 8.7, 840.0, 490.0),
        "name": (0.22, -0.24, 8.5, 850.0, 485.0),
        "threshold": (0.00, -0.58, 12.0, 750.0, 445.0),
        "payoff": (0.46, -0.22, 8.3, 860.0, 490.0),
    }
    yaw, pitch, distance, focal, cy = profiles.get(
        kind, (0.1, -0.25, 9.4, 780.0, 475.0)
    )
    return Camera(yaw=yaw, pitch=pitch, distance=distance, focal=focal, cy=cy)


def _background_for(kind: str) -> tuple[int, int, int, int]:
    backgrounds = {
        "hook_result": (7, 13, 19, 255),
        "skid_contrast": (9, 13, 28, 255),
        "expectation": (26, 11, 7, 255),
        "question_gap": (7, 12, 31, 255),
        "vapor_hint": (3, 25, 31, 255),
        "vapor_birth": (4, 17, 34, 255),
        "vapor_expand": (3, 29, 38, 255),
        "vapor_cushion": (4, 35, 39, 255),
        "no_contact": (9, 18, 31, 255),
        "contact_gap": (4, 23, 29, 255),
        "heat_blocked": (30, 10, 6, 255),
        "paradox_shield": (38, 7, 5, 255),
        "protected_drop": (3, 23, 31, 255),
        "glide": (8, 12, 17, 255),
        "support_force": (3, 29, 34, 255),
        "name": (5, 16, 32, 255),
        "threshold": (24, 12, 7, 255),
        "payoff": (4, 24, 30, 255),
    }
    return backgrounds.get(kind, (7, 13, 19, 255))


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
    image = Image.new("RGBA", (width, height), _background_for(kind))
    camera = _camera_for(kind, t)
    bob = 0.18 * math.sin(t * math.pi * 2.0)
    pulse = 0.5 + 0.5 * math.sin(t * math.pi * 2.0)

    if kind == "hook_result":
        _draw_plate(image, camera, 1.30)
        x = 0.42 * math.sin(t * math.pi * 2.0)
        _draw_vapor_layer(image, camera, center=(x, -0.58, 0.0), spread=0.76 + 0.30 * pulse, thickness=0.16 + 0.06 * pulse)
        _draw_sphere(image, (x, 0.68 + bob, 0.0), 1.08, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=3, strength=0.72 + 0.18 * pulse, y1=-0.34, bend=0.26)

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
        _draw_plate(image, camera, 1.10 + 0.25 * t, x=-2.05, z=-0.65, scale=0.42)
        _draw_plate(image, camera, 1.34, x=2.05, z=0.55, scale=0.52)
        left_r = max(0.20, 0.72 * (1.0 - 0.65 * t))
        _draw_sphere(image, (-2.05, 0.18 + 0.34 * t, -0.65), left_r, "#526f82", camera, alpha=220)
        right_y = 0.38 + 0.54 * t + 0.10 * math.sin(t * math.pi * 4.0)
        _draw_vapor_layer(image, camera, center=(2.05, -0.52, 0.55), spread=0.28 + 0.30 * t, thickness=0.10 + 0.07 * t)
        _draw_sphere(image, (2.05, right_y, 0.55), 0.80, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=3, strength=0.85, y1=0.12, bend=-0.22)

    elif kind == "vapor_hint":
        _draw_plate(image, camera, 1.22, x=-0.55, z=0.35, scale=0.88)
        _draw_sphere(image, (-0.55, 0.98 + 0.20 * math.sin(t * math.pi * 2.0), 0.35), 1.28, "#2c78c9", camera, outline="#d9efff")
        grow = 0.16 + 0.88 * t
        _draw_sphere(image, (-0.55, -0.48 + 0.10 * t, 0.35), (grow, 0.12 + 0.12 * t, grow * 0.62), "#58d6e8", camera, alpha=185)
        _draw_path(image, [(-1.8, -0.92, 0.6), (-1.1, -0.60, 0.5), (-0.55, -0.34, 0.35)], "#8eeef8", camera, width=9, arrow=True)

    elif kind == "vapor_birth":
        _draw_plate(image, camera, 1.24, x=0.35, z=-0.35, scale=0.94)
        _draw_sphere(image, (0.35, 0.96 + 0.12 * t, -0.35), 1.00, "#2c78c9", camera, outline="#d9efff")
        for idx, x in enumerate(np.linspace(-1.55, 1.55, 6)):
            phase = (t * 1.8 + idx * 0.13) % 1.0
            y0 = -0.98
            y1 = -0.82 + 1.02 * phase
            z = -0.75 + (idx % 3) * 0.72
            _draw_path(image, [(float(x), y0, z), (float(x) * 0.82, y1, z * 0.7)], "#58d6e8", camera, width=12, alpha=220)
            _draw_sphere(image, (float(x) * 0.82, y1, z * 0.7), (0.24, 0.16, 0.20), "#a8f4fb", camera, alpha=185)

    elif kind == "vapor_expand":
        _draw_plate(image, camera, 1.24, x=0.0, z=0.30)
        _draw_sphere(image, (0.0, 1.08 + 0.16 * math.sin(t * math.pi * 2.0), 0.30), 0.92, "#2c78c9", camera, outline="#d9efff")
        spread = 0.55 + 1.20 * t
        for j, x in enumerate(np.linspace(-1.65, 1.65, 8)):
            wob = 0.16 * math.sin((t * 4.0 + j * 0.22) * math.pi)
            z = -0.85 + (j % 4) * 0.56
            _draw_sphere(image, (float(x) * spread, -0.46 + wob, z), (0.58, 0.18, 0.44), "#58d6e8", camera, alpha=155)
        _draw_path(image, [(-2.6, -0.44, -0.4), (0.0, -0.28, 0.15), (2.6, -0.44, 0.6)], "#aaf5fb", camera, width=10, alpha=190)

    elif kind == "vapor_cushion":
        _draw_plate(image, camera, 1.28, z=-0.35, scale=1.02)
        _draw_vapor_layer(image, camera, center=(0.0, -0.42, -0.35), spread=0.38 + 0.92 * t, thickness=0.10 + 0.16 * t)
        _draw_sphere(image, (0.0, 0.28 + 0.88 * t + 0.10 * math.sin(t * math.pi * 4.0), -0.35), 1.12, "#2c78c9", camera, outline="#d9efff")
        for x in (-1.4, 0.0, 1.4):
            _draw_path(image, [(x, -0.94, -0.35), (x * 0.72, -0.18 + 0.16 * t, -0.35)], "#79eaf5", camera, width=11, arrow=True, alpha=210)

    elif kind == "no_contact":
        _draw_plate(image, camera, 1.25, x=-0.72, z=0.45, scale=0.90)
        gap = 0.48 + 0.34 * pulse
        _draw_vapor_layer(image, camera, center=(-0.72, -0.48, 0.45), spread=0.88 + 0.18 * pulse, thickness=0.16)
        _draw_sphere(image, (-0.72, 0.58 + gap, 0.45), 0.98, "#2c78c9", camera, outline="#d9efff")
        _draw_path(image, [(1.65, -0.92, 0.35), (1.65, -0.35, 0.35), (1.65, 0.34, 0.35)], "#d9efff", camera, width=7, arrow=True, alpha=210)

    elif kind == "contact_gap":
        _draw_plate(image, camera, 1.28)
        _draw_vapor_layer(image, camera, center=(0.0, -0.42, 0.0), spread=1.22, thickness=0.16 + 0.03 * pulse)
        _draw_sphere(image, (0.0, 0.96 + 0.08 * t, 0.0), (1.75, 1.45, 1.35), "#2c78c9", camera, outline="#d9efff")

    elif kind == "heat_blocked":
        _draw_plate(image, camera, 1.40, x=0.75, z=-0.25, scale=0.96)
        _draw_vapor_layer(image, camera, center=(0.75, -0.44, -0.25), spread=1.08, thickness=0.23)
        _draw_sphere(image, (0.75, 0.88 + 0.14 * math.sin(t * math.pi * 2.0), -0.25), 0.96, "#2c78c9", camera, outline="#d9efff")
        xs = (-2.1, -1.1, 0.0, 1.2, 2.2)
        for idx, x in enumerate(xs):
            bend = (-1.1 if idx < 2 else 1.1 if idx > 2 else 0.0) * (0.65 + 0.45 * pulse)
            _draw_path(image, [(x, -1.02, 0.15), (x, -0.56, 0.08), (x + bend, -0.18, 0.02)], "#ffd166", camera, width=11, arrow=True, alpha=235)

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
        _draw_plate(image, camera, 1.32, x=-0.25, z=0.35)
        _draw_vapor_layer(image, camera, center=(-0.25, -0.44, 0.35), spread=0.92 + 0.24 * pulse, thickness=0.20)
        _draw_sphere(image, (-0.25, 0.62 + 0.62 * t + 0.10 * math.sin(t * math.pi * 4.0), 0.35), 1.00, "#2c78c9", camera, outline="#d9efff")
        for x in (-1.35, -0.25, 0.85):
            _draw_path(image, [(x, -0.82, 0.35), (x, -0.10 + 0.22 * t, 0.35)], "#72e8f5", camera, width=14, arrow=True, alpha=235)
        _draw_heat_arrows(image, camera, count=3, strength=0.70, y1=-0.48, bend=0.18)

    elif kind == "name":
        _draw_plate(image, camera, 1.26, x=0.0, z=0.55, scale=0.82)
        _draw_vapor_layer(image, camera, center=(0.0, -0.40, 0.25), spread=1.28 + 0.18 * pulse, thickness=0.18)
        _draw_sphere(image, (0.0, 0.92 + 0.26 * math.sin(t * math.pi * 2.0), 0.25), 1.38, "#2c78c9", camera, outline="#d9efff")
        _draw_path(image, [(-2.4, -0.35, 0.0), (0.0, -0.08, 0.65), (2.4, -0.35, 0.0)], "#58d6e8", camera, width=12, alpha=210)
        d = ImageDraw.Draw(image, "RGBA")
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        except OSError:
            font = ImageFont.load_default()
        d.text((width // 2, 110), "LEIDENFROST", fill=(225, 245, 255, 245), anchor="mm", font=font)

    elif kind == "threshold":
        # Three states are all visible from frame zero so semantic QA samples
        # the actual contrast: touching/shrinking -> hotter -> lifted on vapor.
        states = (
            (-2.45, 0.88, 0.34, 0.12, False),
            (0.0, 1.15, 0.46, 0.30, False),
            (2.45, 1.45, 0.62, 0.88, True),
        )
        for idx, (x, heat, radius, y, stable) in enumerate(states):
            z = (-0.55, 0.25, 0.70)[idx]
            _draw_plate(image, camera, heat, x=x, z=z, scale=0.31 + 0.03 * idx)
            rr = radius * (1.0 - 0.28 * t if idx == 0 else 1.0)
            yy = y + (0.08 * math.sin((t + idx * 0.23) * math.pi * 2.0))
            _draw_sphere(image, (x, yy, z), max(0.22, rr), "#2c78c9", camera, outline="#d9efff")
            _draw_heat_arrows(image, camera, count=2 + idx, strength=0.55 + 0.18 * idx, y1=-0.42 + 0.10 * idx)
            if idx == 1:
                for dx in (-0.28, 0.28):
                    _draw_sphere(image, (x + dx, -0.52 + 0.10 * pulse, z), (0.16, 0.08, 0.12), "#79eaf5", camera, alpha=170)
            if stable:
                _draw_vapor_layer(image, camera, center=(x, -0.40, z), spread=0.38 + 0.16 * pulse, thickness=0.12 + 0.04 * pulse)

    elif kind == "payoff":
        _draw_plate(image, camera, 1.40, z=0.25)
        x = -1.25 + 2.50 * t
        z = 0.55 * math.sin(t * math.pi * 2.0)
        _draw_vapor_layer(image, camera, center=(x, -0.46, z), spread=0.72 + 0.22 * pulse, thickness=0.18 + 0.05 * pulse)
        _draw_sphere(image, (x, 0.82 + 0.16 * math.sin(t * math.pi * 4.0), z), 1.08, "#2c78c9", camera, outline="#d9efff")
        _draw_path(image, [(-1.9, -0.34, -0.3), (-0.7, -0.18, 0.45), (0.6, -0.24, -0.35), (1.8, -0.12, 0.25)], "#6ee8f5", camera, width=11, alpha=215)
        _draw_heat_arrows(image, camera, count=3, strength=0.88, y1=-0.30, bend=0.42)

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

    # Fail closed if a future edit accidentally reintroduces camera motion.
    fixed_camera = _camera_for(kind, 0.0)
    for probe_t in (0.25, 0.5, 0.75, 1.0):
        if _camera_for(kind, probe_t) != fixed_camera:
            raise RuntimeError(
                f"3D camera must remain fixed within a beat: {kind} at t={probe_t}"
            )

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
