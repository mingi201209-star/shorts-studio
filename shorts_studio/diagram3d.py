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
    lat_steps: int = 16,
    lon_steps: int = 32,
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


def _draw_screen_ellipse(
    image: Image.Image,
    center: tuple[float, float],
    radii: tuple[float, float],
    color: str,
    alpha: int = 255,
    width: int = 3,
    fill: bool = False,
) -> None:
    cx, cy = center
    rx, ry = max(1.0, radii[0]), max(1.0, radii[1])
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    box = (cx - rx, cy - ry, cx + rx, cy + ry)
    rgba = _rgb(color) + (alpha,)
    if fill:
        d.ellipse(box, fill=rgba)
    else:
        d.ellipse(box, outline=rgba, width=width)
    image.alpha_composite(overlay)


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

    # Smooth material pass: never draw every mesh edge. The old behavior
    # turned droplets and vapor into wireframe CAD objects.
    verts, faces = _sphere_mesh(center, radii)
    _draw_mesh(image, verts, faces, color, camera, alpha=alpha, outline=None)

    # Approximate the projected silhouette from the 3D center and principal
    # radii. This gives one clean rim instead of a grid over every face.
    cx, cy, cz = center
    probes = np.array(
        [
            [cx, cy, cz],
            [cx + radii[0], cy, cz],
            [cx, cy + radii[1], cz],
        ],
        dtype=float,
    )
    xy, _ = _project(probes, camera)
    rx = float(np.linalg.norm(xy[1] - xy[0]))
    ry = float(np.linalg.norm(xy[2] - xy[0]))
    if outline:
        _draw_screen_ellipse(
            image, tuple(xy[0]), (rx, ry), outline,
            alpha=min(235, max(100, alpha)), width=max(2, int(min(rx, ry) * 0.035)),
        )

    # Glossy highlight only on water-like, mostly opaque droplets. It creates
    # volume without introducing camera motion or decorative wireframes.
    if color.lower() in {"#2c78c9", "#417aa6", "#526f82", "#427da8"} and alpha >= 200:
        highlight_center = (float(xy[0][0] - rx * 0.28), float(xy[0][1] - ry * 0.32))
        _draw_screen_ellipse(
            image,
            highlight_center,
            (max(4.0, rx * 0.15), max(3.0, ry * 0.10)),
            "#e7fbff",
            alpha=170,
            width=1,
            fill=True,
        )

def _droplet_radii(
    base_radius: float,
    t: float,
    intensity: float = 0.12,
    flatten: float = 0.0,
    phase: float = 0.0,
) -> tuple[float, float, float]:
    """Art-directed liquid deformation with approximate volume preservation."""
    w1 = math.sin((t + phase) * math.pi * 2.0)
    w2 = math.sin((t * 2.05 + phase * 0.73) * math.pi * 2.0)
    lateral = 1.0 + intensity * (0.72 * w1 + 0.28 * w2) + 0.62 * flatten
    depth = 1.0 - intensity * (0.24 * w1 - 0.16 * w2) + 0.28 * flatten
    vertical = 1.0 - intensity * (0.76 * w1 + 0.16 * w2) - 0.86 * flatten
    lateral = max(0.72, min(1.38, lateral))
    depth = max(0.78, min(1.28, depth))
    vertical = max(0.62, min(1.32, vertical))
    return (base_radius * lateral, base_radius * vertical, base_radius * depth)


def _draw_droplet(
    image: Image.Image,
    center: tuple[float, float, float],
    base_radius: float,
    camera: Camera,
    t: float,
    intensity: float = 0.12,
    flatten: float = 0.0,
    phase: float = 0.0,
    color: str = "#2c78c9",
    alpha: int = 255,
) -> None:
    _draw_sphere(
        image,
        center,
        _droplet_radii(base_radius, t, intensity=intensity, flatten=flatten, phase=phase),
        color,
        camera,
        alpha=alpha,
        outline="#d9efff" if alpha >= 220 else None,
    )


def _draw_contact_shadow(
    image: Image.Image,
    camera: Camera,
    center: tuple[float, float, float],
    radius: tuple[float, float] = (1.0, 0.72),
    alpha: int = 80,
) -> None:
    cx, cy, cz = center
    probes = np.array(
        [[cx, cy, cz], [cx + radius[0], cy, cz], [cx, cy, cz + radius[1]]],
        dtype=float,
    )
    xy, _ = _project(probes, camera)
    rx = max(5.0, float(np.linalg.norm(xy[1] - xy[0])))
    ry = max(3.0, float(np.linalg.norm(xy[2] - xy[0])) * 0.52)
    _draw_screen_ellipse(
        image, tuple(xy[0]), (rx, ry), "#000000",
        alpha=max(0, min(150, alpha)), width=1, fill=True,
    )

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
    # Camera is intentionally placed closer to the subject for a more immersive
    # perspective while remaining fixed within each beat.
    profiles = {
        "hook_result": (0.12, -0.28, 8.25, 810.0, 475.0),
        "skid_contrast": (-0.58, -0.42, 8.75, 805.0, 465.0),
        "expectation": (0.52, -0.18, 8.05, 820.0, 485.0),
        "question_gap": (-0.35, -0.62, 9.00, 825.0, 455.0),
        "vapor_hint": (0.62, -0.08, 7.35, 880.0, 510.0),
        "vapor_birth": (-0.68, -0.30, 8.60, 790.0, 480.0),
        "vapor_expand": (0.36, -0.52, 9.25, 770.0, 455.0),
        "vapor_cushion": (-0.18, -0.12, 7.50, 870.0, 505.0),
        "no_contact": (0.56, -0.38, 8.25, 810.0, 475.0),
        "contact_gap": (0.02, -0.03, 6.75, 920.0, 515.0),
        "heat_blocked": (-0.52, -0.26, 8.15, 830.0, 485.0),
        "paradox_shield": (0.68, -0.46, 9.35, 770.0, 455.0),
        "protected_drop": (0.06, -0.06, 7.00, 900.0, 515.0),
        "glide": (-0.12, -0.98, 9.65, 770.0, 455.0),
        "support_force": (-0.58, -0.18, 7.95, 840.0, 490.0),
        "name": (0.22, -0.24, 7.80, 850.0, 485.0),
        "threshold": (0.00, -0.58, 9.75, 820.0, 455.0),
        "payoff": (0.46, -0.22, 7.60, 860.0, 490.0),
    }
    yaw, pitch, distance, focal, cy = profiles.get(
        kind, (0.1, -0.25, 8.6, 780.0, 475.0)
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
    # Brushed-metal body. The hot surface is no longer one giant orange slab;
    # heat is communicated by a dark metal top plus thin glowing perimeter
    # rails, which reads less like a toy/PPT object.
    _draw_box(image, (x, -1.65, z), (6.8 * scale, 1.05, 4.4 * scale), "#303840", camera, outline="#6f7b84")
    _draw_box(image, (x, -1.09, z), (6.50 * scale, 0.10, 4.10 * scale), "#575f66", camera, outline="#818b92")

    glow = "#ff3d22" if heat >= 1.2 else "#ff744c"
    hot = "#ffd166" if heat >= 1.35 else "#ffad57"
    edge = 0.10 * scale
    half_x = 3.18 * scale
    half_z = 1.98 * scale
    _draw_box(image, (x, -1.02, z - half_z), (6.35 * scale, 0.055, edge), glow, camera)
    _draw_box(image, (x, -1.02, z + half_z), (6.35 * scale, 0.055, edge), glow, camera)
    _draw_box(image, (x - half_x, -1.02, z), (edge, 0.055, 3.86 * scale), glow, camera)
    _draw_box(image, (x + half_x, -1.02, z), (edge, 0.055, 3.86 * scale), glow, camera)

    if heat > 1.0:
        # A thin central heat band gives the metal a hot sheen without
        # replacing the whole material with flat orange.
        _draw_box(image, (x, -0.99, z), (5.2 * scale, 0.025, 0.12 * scale), hot, camera)


def _draw_vapor_layer(
    image: Image.Image,
    camera: Camera,
    center: tuple[float, float, float] = (0.0, -0.60, 0.0),
    spread: float = 1.0,
    thickness: float = 0.20,
    alpha: int = 155,
    phase: float = 0.0,
    outflow: float = 0.0,
) -> None:
    # Central vapor pocket plus thinner edge outflow. Geometry is exaggerated
    # only enough to survive mobile viewing; the physical ordering is kept.
    cx, cy, cz = center
    sway_x = 0.055 * spread * math.sin(phase * math.pi * 2.0)
    sway_z = 0.040 * spread * math.sin((phase + 0.23) * math.pi * 2.0)
    _draw_sphere(
        image, (cx + sway_x * 0.35, cy, cz + sway_z * 0.25),
        (2.18 * spread, thickness * 0.78, 1.50 * spread),
        "#246f82", camera, alpha=max(58, int(alpha * 0.42)), outline=None,
    )
    _draw_sphere(
        image, (cx - sway_x * 0.20, cy + thickness * 0.08, cz - sway_z * 0.18),
        (1.68 * spread, thickness * 0.60, 1.18 * spread),
        "#57cbdc", camera, alpha=max(78, int(alpha * 0.60)), outline="#c7f9ff",
    )
    _draw_sphere(
        image, (cx + sway_x * 0.15, cy + thickness * 0.15, cz + sway_z * 0.10),
        (0.92 * spread, thickness * 0.34, 0.66 * spread),
        "#b7f7fb", camera, alpha=max(40, int(alpha * 0.27)), outline=None,
    )
    if outflow > 0.0:
        strength = max(0.0, min(1.0, outflow))
        for idx, side in enumerate((-1.0, 1.0)):
            start_x = cx + side * 1.45 * spread
            pts: list[tuple[float, float, float]] = []
            for k in range(7):
                u = k / 6.0
                curl = math.sin((phase * 1.7 + idx * 0.31 + u * 0.8) * math.pi * 2.0)
                pts.append((
                    start_x + side * (0.25 + 0.85 * u) * spread * strength,
                    cy + thickness * (0.05 + 0.18 * u) + 0.025 * curl,
                    cz + 0.15 * curl * (0.25 + 0.75 * u),
                ))
            _draw_path(
                image, pts, "#7fe9f4", camera,
                width=max(4, int(7 * strength)), arrow=False,
                alpha=int(105 + 80 * strength),
            )

def _draw_heat_arrows(
    image: Image.Image,
    camera: Camera,
    count: int = 5,
    strength: float = 1.0,
    y0: float = -1.02,
    y1: float = -0.30,
    bend: float = 0.0,
    phase: float = 0.0,
) -> None:
    """Draw animated heat shimmer streams without textbook arrowheads.

    The camera stays fixed; only the heat field itself undulates upward.
    A soft orange outer glow plus a thinner warm core reads like rising
    convection rather than diagram arrows.
    """
    xs = np.linspace(-2.2, 2.2, count)
    for idx, x in enumerate(xs):
        side = math.copysign(1.0, x if x != 0 else (idx - count / 2.0 or 1.0))
        flare = bend * (0.35 + abs(float(x)) / 3.5) * side
        points: list[tuple[float, float, float]] = []
        for k in range(8):
            u = k / 7.0
            wave = math.sin((phase * 1.65 + idx * 0.19 + u * 0.72) * math.pi * 2.0)
            drift = wave * (0.06 + 0.11 * strength) * (0.25 + 0.75 * u)
            px = float(x) + flare * u + drift
            py = y0 + (y1 - y0) * u
            pz = 0.18 + 0.10 * math.sin((phase * 1.35 + idx * 0.23 + u) * math.pi * 2.0)
            points.append((px, py, pz))
        _draw_path(
            image,
            points,
            "#ff6b35",
            camera,
            width=max(7, int(12 * strength)),
            arrow=False,
            alpha=min(155, int(95 + 45 * strength)),
        )
        _draw_path(
            image,
            points,
            "#ffc766",
            camera,
            width=max(3, int(5 * strength)),
            arrow=False,
            alpha=min(235, int(165 + 45 * strength)),
        )


def render_diagram_frame(kind: str, t: float, width: int = 980, height: int = 950) -> Image.Image:
    image = Image.new("RGBA", (width, height), _background_for(kind))
    camera = _camera_for(kind, t)
    bob = 0.18 * math.sin(t * math.pi * 2.0)
    pulse = 0.5 + 0.5 * math.sin(t * math.pi * 2.0)

    if kind == "hook_result":
        _draw_plate(image, camera, 1.30)
        x = 0.42 * math.sin(t * math.pi * 2.0)
        _draw_contact_shadow(image, camera, (x, -0.965, 0.0), (1.12, 0.78), alpha=68)
        _draw_vapor_layer(
            image, camera, center=(x, -0.58, 0.0),
            spread=0.76 + 0.30 * pulse, thickness=0.16 + 0.06 * pulse,
            phase=t, outflow=0.46 + 0.18 * pulse,
        )
        _draw_droplet(
            image, (x, 0.68 + bob, 0.0), 1.08, camera, t,
            intensity=0.115, flatten=0.035 + 0.025 * pulse,
        )
        _draw_heat_arrows(image, camera, count=3, strength=0.72 + 0.18 * pulse, y1=-0.34, bend=0.26, phase=t)

    elif kind == "skid_contrast":
        _draw_plate(image, camera, 1.20, x=-1.62, scale=0.54)
        _draw_plate(image, camera, 1.20, x=1.62, scale=0.54)
        left_r = max(0.25, 0.82 * (1.0 - 0.70 * t))
        _draw_sphere(image, (-1.62, 0.40 + 0.15 * t, 0.0), left_r, "#417aa6", camera, alpha=210)
        glide_x = 1.18 + 0.82 * t
        _draw_vapor_layer(image, camera, center=(glide_x, -0.58, 0.0), spread=0.34, thickness=0.12)
        _draw_sphere(image, (glide_x, 0.58 + 0.05 * math.sin(t * math.pi * 4.0), 0.0), 0.82, "#2c78c9", camera, outline="#d9efff")
        _draw_path(image, [(1.1, -0.35, 0.7), (1.6, -0.28, 0.5), (2.4, -0.16, 0.1)], "#58d6e8", camera, width=8, arrow=True)

    elif kind == "expectation":
        _draw_plate(image, camera, 1.05 + 0.35 * t)
        r = max(0.32, 1.05 * (1.0 - 0.60 * t))
        _draw_sphere(image, (0.0, 0.62 + 0.10 * t, 0.0), r, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=5, strength=0.75 + 0.45 * t, y1=0.18 + 0.10 * t, phase=t)

    elif kind == "question_gap":
        _draw_plate(image, camera, 1.10 + 0.25 * t, x=-1.78, z=-0.55, scale=0.50)
        _draw_plate(image, camera, 1.34, x=1.78, z=0.48, scale=0.60)
        left_r = max(0.24, 0.82 * (1.0 - 0.65 * t))
        _draw_sphere(image, (-1.78, 0.24 + 0.34 * t, -0.55), left_r, "#526f82", camera, alpha=220)
        right_y = 0.38 + 0.54 * t + 0.10 * math.sin(t * math.pi * 4.0)
        _draw_vapor_layer(image, camera, center=(1.78, -0.50, 0.48), spread=0.34 + 0.34 * t, thickness=0.11 + 0.08 * t)
        _draw_sphere(image, (1.78, right_y, 0.48), 0.92, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=3, strength=0.85, y1=0.12, bend=-0.22, phase=t)

    elif kind == "vapor_hint":
        _draw_plate(image, camera, 1.22, x=-0.55, z=0.35, scale=0.88)
        _draw_contact_shadow(image, camera, (-0.55, -0.965, 0.35), (1.20, 0.82), alpha=72)
        _draw_droplet(
            image, (-0.55, 0.90 + 0.16 * math.sin(t * math.pi * 2.0), 0.35),
            1.28, camera, t, intensity=0.105, flatten=max(0.0, 0.11 * (1.0 - t)),
        )
        _draw_vapor_layer(
            image, camera, center=(-0.55, -0.52 + 0.06 * t, 0.35),
            spread=max(0.10, 0.22 + 0.62 * t), thickness=0.07 + 0.12 * t,
            alpha=145 + int(35 * t), phase=t, outflow=0.15 + 0.45 * t,
        )

    elif kind == "vapor_birth":
        _draw_plate(image, camera, 1.24, x=0.35, z=-0.35, scale=0.94)
        birth = t * t * (3.0 - 2.0 * t)
        _draw_contact_shadow(image, camera, (0.35, -0.965, -0.35), (1.02, 0.74), alpha=int(92 - 30 * birth))
        _draw_vapor_layer(
            image, camera, center=(0.35, -0.53 + 0.05 * birth, -0.35),
            spread=0.18 + 0.76 * birth, thickness=0.055 + 0.16 * birth,
            alpha=120 + int(60 * birth), phase=t, outflow=0.08 + 0.72 * birth,
        )
        _draw_droplet(
            image, (0.35, 0.68 + 0.34 * birth, -0.35), 1.00, camera, t,
            intensity=0.13, flatten=0.14 * (1.0 - birth), phase=0.12,
        )

    elif kind == "vapor_expand":
        _draw_plate(image, camera, 1.24, x=0.0, z=0.30)
        _draw_contact_shadow(image, camera, (0.0, -0.965, 0.30), (1.08, 0.76), alpha=60)
        _draw_vapor_layer(
            image, camera, center=(0.0, -0.48, 0.30),
            spread=0.48 + 0.92 * t, thickness=0.10 + 0.10 * t,
            alpha=150, phase=t, outflow=0.42 + 0.48 * t,
        )
        _draw_droplet(
            image, (0.0, 0.84 + 0.22 * t + 0.10 * math.sin(t * math.pi * 2.0), 0.30),
            0.98, camera, t, intensity=0.115, flatten=0.04 * (1.0 - t), phase=0.18,
        )

    elif kind == "vapor_cushion":
        _draw_plate(image, camera, 1.28, z=-0.35, scale=1.02)
        _draw_contact_shadow(image, camera, (0.0, -0.965, -0.35), (1.30, 0.88), alpha=56)
        _draw_vapor_layer(
            image, camera, center=(0.0, -0.42, -0.35),
            spread=0.38 + 0.92 * t, thickness=0.10 + 0.16 * t,
            phase=t, outflow=0.34 + 0.52 * t,
        )
        _draw_droplet(
            image, (0.0, 0.30 + 0.84 * t + 0.08 * math.sin(t * math.pi * 4.0), -0.35),
            1.12, camera, t, intensity=0.13, flatten=0.10 * (1.0 - t), phase=0.07,
        )

    elif kind == "no_contact":
        _draw_plate(image, camera, 1.25, x=-0.72, z=0.45, scale=0.90)
        gap = 0.48 + 0.34 * pulse
        _draw_vapor_layer(image, camera, center=(-0.72, -0.48, 0.45), spread=0.88 + 0.18 * pulse, thickness=0.16)
        _draw_sphere(image, (-0.72, 0.58 + gap, 0.45), 0.98, "#2c78c9", camera, outline="#d9efff")
        _draw_path(image, [(1.65, -0.92, 0.35), (1.65, -0.35, 0.35), (1.65, 0.34, 0.35)], "#d9efff", camera, width=7, arrow=True, alpha=210)

    elif kind == "contact_gap":
        _draw_plate(image, camera, 1.28)
        _draw_contact_shadow(image, camera, (0.0, -0.965, 0.0), (1.58, 1.02), alpha=52)
        _draw_vapor_layer(
            image, camera, center=(0.0, -0.42, 0.0),
            spread=1.22, thickness=0.16 + 0.03 * pulse, phase=t, outflow=0.62,
        )
        _draw_droplet(
            image, (0.0, 0.96 + 0.08 * t, 0.0), 1.58, camera, t,
            intensity=0.09, flatten=0.10, phase=0.21,
        )

    elif kind == "heat_blocked":
        _draw_plate(image, camera, 1.40, x=0.75, z=-0.25, scale=0.96)
        _draw_contact_shadow(image, camera, (0.75, -0.965, -0.25), (1.04, 0.72), alpha=50)
        _draw_vapor_layer(
            image, camera, center=(0.75, -0.44, -0.25),
            spread=1.08, thickness=0.23, phase=t, outflow=0.58,
        )
        _draw_droplet(
            image, (0.75, 0.88 + 0.14 * math.sin(t * math.pi * 2.0), -0.25),
            0.96, camera, t, intensity=0.105, flatten=0.035, phase=0.15,
        )
        xs = (-2.1, -1.1, 0.0, 1.2, 2.2)
        for idx, x in enumerate(xs):
            bend = (-1.1 if idx < 2 else 1.1 if idx > 2 else 0.0) * (0.65 + 0.45 * pulse)
            pts = []
            for k in range(8):
                u = k / 7.0
                wave = 0.13 * math.sin((t * 1.6 + idx * 0.21 + u * 0.8) * math.pi * 2.0)
                pts.append((x + bend * u + wave * u, -1.02 + 0.84 * u, 0.12 + 0.06 * math.sin((t + u) * math.pi * 2.0)))
            _draw_path(image, pts, "#ff6b35", camera, width=13, arrow=False, alpha=130)
            _draw_path(image, pts, "#ffc766", camera, width=5, arrow=False, alpha=220)

    elif kind == "paradox_shield":
        image.paste((34, 8, 7, 255), (0, 0, width, height))
        _draw_plate(image, camera, 1.45)
        _draw_vapor_layer(image, camera, spread=1.05 + 0.08 * pulse, thickness=0.19)
        _draw_sphere(image, (0.0, 0.70 + bob, 0.0), 0.95, "#2c78c9", camera, outline="#d9efff")
        _draw_heat_arrows(image, camera, count=5, strength=1.15, y1=-0.36, bend=0.52, phase=t)

    elif kind == "protected_drop":
        _draw_plate(image, camera, 1.38)
        _draw_contact_shadow(image, camera, (0.0, -0.965, 0.0), (1.52, 0.98), alpha=46)
        _draw_vapor_layer(
            image, camera, center=(0.0, -0.36, 0.0),
            spread=1.25, thickness=0.20 + 0.03 * pulse, phase=t, outflow=0.72,
        )
        _draw_droplet(
            image, (0.0, 1.05 + 0.12 * t, 0.0), 1.55, camera, t,
            intensity=0.10, flatten=0.055, phase=0.31,
        )
        _draw_heat_arrows(image, camera, count=3, strength=0.90, y1=-0.22, phase=t)

    elif kind == "glide":
        _draw_plate(image, camera, 1.25)
        ang = -0.85 + 1.55 * t
        x = 2.15 * math.sin(ang)
        z = 1.55 * math.cos(ang)
        _draw_contact_shadow(image, camera, (x, -0.965, z), (0.72, 0.50), alpha=58)
        _draw_vapor_layer(
            image, camera, center=(x, -0.56, z),
            spread=0.46, thickness=0.12, phase=t, outflow=0.55,
        )
        _draw_droplet(
            image, (x, 0.50 + 0.06 * math.sin(t * math.pi * 5.0), z),
            0.72, camera, t, intensity=0.16, flatten=0.035, phase=0.27,
        )
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
        _draw_heat_arrows(image, camera, count=3, strength=0.70, y1=-0.48, bend=0.18, phase=t)

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
            _draw_heat_arrows(image, camera, count=2 + idx, strength=0.55 + 0.18 * idx, y1=-0.42 + 0.10 * idx, phase=t)
            if idx == 1:
                for dx in (-0.28, 0.28):
                    _draw_sphere(image, (x + dx, -0.52 + 0.10 * pulse, z), (0.16, 0.08, 0.12), "#79eaf5", camera, alpha=170)
            if stable:
                _draw_vapor_layer(image, camera, center=(x, -0.40, z), spread=0.38 + 0.16 * pulse, thickness=0.12 + 0.04 * pulse)

    elif kind == "payoff":
        _draw_plate(image, camera, 1.40, z=0.25)
        x = -1.25 + 2.50 * t
        z = 0.55 * math.sin(t * math.pi * 2.0)
        _draw_contact_shadow(image, camera, (x, -0.965, z), (1.05, 0.74), alpha=50)
        _draw_vapor_layer(
            image, camera, center=(x, -0.46, z),
            spread=0.72 + 0.22 * pulse, thickness=0.18 + 0.05 * pulse,
            phase=t, outflow=0.66,
        )
        _draw_droplet(
            image, (x, 0.82 + 0.16 * math.sin(t * math.pi * 4.0), z),
            1.08, camera, t, intensity=0.14, flatten=0.045, phase=0.22,
        )
        _draw_path(image, [(-1.9, -0.34, -0.3), (-0.7, -0.18, 0.45), (0.6, -0.24, -0.35), (1.8, -0.12, 0.25)], "#6ee8f5", camera, width=11, alpha=215)
        _draw_heat_arrows(image, camera, count=3, strength=0.88, y1=-0.30, bend=0.42, phase=t)

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
