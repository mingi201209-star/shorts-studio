from __future__ import annotations

import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


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


def _projected_ellipse_geometry(
    center: tuple[float, float, float],
    radii: tuple[float, float, float],
    camera: Camera,
) -> tuple[tuple[float, float], float, float]:
    cx, cy, cz = center
    rx, ry, rz = radii
    probes = np.array(
        [
            [cx, cy, cz],
            [cx + rx, cy, cz],
            [cx - rx, cy, cz],
            [cx, cy + ry, cz],
            [cx, cy - ry, cz],
            [cx, cy, cz + rz],
            [cx, cy, cz - rz],
        ],
        dtype=float,
    )
    xy, _ = _project(probes, camera)
    center_xy = xy[0]
    screen_rx = max(1.0, float(np.max(np.abs(xy[1:, 0] - center_xy[0]))))
    screen_ry = max(1.0, float(np.max(np.abs(xy[1:, 1] - center_xy[1]))))
    return (float(center_xy[0]), float(center_xy[1])), screen_rx, screen_ry


def _draw_soft_projected_ellipse(
    image: Image.Image,
    center: tuple[float, float, float],
    radii: tuple[float, float, float],
    color: str,
    camera: Camera,
    alpha: int,
    blur: float,
) -> None:
    center_xy, rx, ry = _projected_ellipse_geometry(center, radii, camera)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    cx, cy = center_xy
    d.ellipse(
        (cx - rx, cy - ry, cx + rx, cy + ry),
        fill=_rgb(color) + (max(0, min(255, alpha)),),
    )
    if blur > 0.0:
        overlay = overlay.filter(ImageFilter.GaussianBlur(blur))
    image.alpha_composite(overlay)



def _draw_soft_projected_polygon(
    image: Image.Image,
    points: list[tuple[float, float, float]],
    color: str,
    camera: Camera,
    alpha: int,
    blur: float,
) -> None:
    xy, _ = _project(np.array(points, dtype=float), camera)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    d.polygon(
        [tuple(v) for v in xy],
        fill=_rgb(color) + (max(0, min(255, alpha)),),
    )
    if blur > 0.0:
        overlay = overlay.filter(ImageFilter.GaussianBlur(blur))
    image.alpha_composite(overlay)

def _draw_glossy_water(
    image: Image.Image,
    center: tuple[float, float, float],
    radii: tuple[float, float, float],
    color: str,
    camera: Camera,
    alpha: int,
    outline: str | None,
    deform_t: float | None = None,
    deform_phase: float = 0.0,
    deform_strength: float = 0.0,
) -> None:
    """Render a smooth dielectric with optional low-order liquid silhouette modes."""
    (cx, cy), rx, ry = _projected_ellipse_geometry(center, radii, camera)
    pad = 5
    left = max(0, int(math.floor(cx - rx * 1.12 - pad)))
    top = max(0, int(math.floor(cy - ry * 1.12 - pad)))
    right = min(image.width, int(math.ceil(cx + rx * 1.12 + pad)))
    bottom = min(image.height, int(math.ceil(cy + ry * 1.12 + pad)))
    if right <= left or bottom <= top:
        return

    yy, xx = np.mgrid[top:bottom, left:right]
    dx = (xx - cx) / max(rx, 1.0)
    dy = (yy - cy) / max(ry, 1.0)
    radial = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(dy, dx)

    if deform_t is not None and deform_strength > 0.0:
        ph = (deform_t + deform_phase) * math.pi * 2.0
        boundary = (
            1.0
            + deform_strength * 0.55 * np.sin(3.0 * theta + ph)
            + deform_strength * 0.30 * np.sin(5.0 * theta - 0.72 * ph)
            + deform_strength * 0.15 * np.cos(2.0 * theta + 0.35 * ph)
        )
        boundary = np.clip(boundary, 0.86, 1.14)
        q = radial / boundary
    else:
        q = radial

    mask = q <= 1.0
    nz = np.sqrt(np.clip(1.0 - q * q, 0.0, 1.0))

    light = np.clip(0.42 + 0.50 * (-0.40 * dx - 0.62 * dy + 0.72 * nz), 0.18, 1.0)
    fresnel = np.power(np.clip(1.0 - nz, 0.0, 1.0), 2.15)
    base = np.array(_rgb(color), dtype=float)
    cool = np.array((126.0, 221.0, 247.0), dtype=float)
    rgb = base[None, None, :] * (0.62 + 0.48 * light[..., None])
    rgb += cool[None, None, :] * (0.23 * fresnel[..., None])
    rgb *= (1.0 - 0.12 * np.clip(dy, 0.0, 1.0)[..., None])

    spec_a = np.exp(-(((dx + 0.33) / 0.14) ** 2 + ((dy + 0.38) / 0.10) ** 2))
    spec_b = np.exp(-(((dx - 0.24) / 0.11) ** 2 + ((dy - 0.08) / 0.060) ** 2))
    rgb += spec_a[..., None] * np.array((194.0, 231.0, 247.0))[None, None, :] * 0.80
    rgb += spec_b[..., None] * np.array((96.0, 183.0, 222.0))[None, None, :] * 0.24

    rim = np.array(_rgb(outline or "#bdeeff"), dtype=float)
    edge = mask & (q >= 0.958)
    rgb[edge] = rgb[edge] * 0.58 + rim * 0.42
    rgb = np.clip(rgb, 0.0, 255.0)

    a = np.zeros_like(q, dtype=float)
    base_alpha = max(0, min(255, alpha))
    a[mask] = base_alpha * (0.90 + 0.10 * fresnel[mask])
    rgba = np.zeros((bottom - top, right - left, 4), dtype=np.uint8)
    rgba[..., :3] = rgb.astype(np.uint8)
    rgba[..., 3] = np.clip(a, 0.0, 255.0).astype(np.uint8)
    image.alpha_composite(Image.fromarray(rgba, mode="RGBA"), (left, top))


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

    water_colors = {"#2c78c9", "#417aa6", "#526f82", "#427da8"}
    if color.lower() in water_colors and alpha >= 200:
        _draw_glossy_water(image, center, radii, color, camera, alpha, outline)
        return

    verts, faces = _sphere_mesh(center, radii)
    _draw_mesh(image, verts, faces, color, camera, alpha=alpha, outline=None)

    if outline:
        center_xy, rx, ry = _projected_ellipse_geometry(center, radii, camera)
        _draw_screen_ellipse(
            image,
            center_xy,
            (rx, ry),
            outline,
            alpha=min(225, max(100, alpha)),
            width=max(2, int(min(rx, ry) * 0.025)),
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
    radii = _droplet_radii(
        base_radius,
        t,
        intensity=intensity,
        flatten=flatten,
        phase=phase,
    )
    organic = min(0.082, 0.030 + intensity * 0.26 + flatten * 0.08)
    _draw_glossy_water(
        image,
        center,
        radii,
        color,
        camera,
        alpha,
        "#d9efff" if alpha >= 220 else None,
        deform_t=t,
        deform_phase=phase,
        deform_strength=organic,
    )


def _draw_contact_shadow(
    image: Image.Image,
    camera: Camera,
    center: tuple[float, float, float],
    radius: tuple[float, float] = (1.0, 0.72),
    alpha: int = 80,
) -> None:
    _draw_soft_projected_ellipse(
        image,
        center,
        (radius[0], 0.035, radius[1]),
        "#000000",
        camera,
        alpha=max(0, min(135, alpha)),
        blur=max(5.0, 0.07 * camera.focal / max(camera.distance, 1.0)),
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



def _draw_soft_path(
    image: Image.Image,
    points: list[tuple[float, float, float]],
    color: str,
    camera: Camera,
    width: int = 8,
    alpha: int = 160,
    blur: float = 5.0,
) -> None:
    pts = np.array(points, dtype=float)
    xy, _ = _project(pts, camera)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    d.line(
        [tuple(v) for v in xy],
        fill=_rgb(color) + (max(0, min(255, alpha)),),
        width=max(1, width),
        joint="curve",
    )
    if blur > 0.0:
        overlay = overlay.filter(ImageFilter.GaussianBlur(blur))
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
        # Three intentionally distinct lighting states make the mechanism
        # progression legible at phone size: vapor is born in a dark field,
        # expansion lights the whole scene, then the final cushion resolves
        # back to a darker high-contrast state. Camera geometry stays fixed.
        "vapor_birth": (4, 17, 34, 255),
        "vapor_expand": (5, 48, 55, 255),
        "vapor_cushion": (3, 22, 30, 255),
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
    # Solid metal body first. Heat is a soft surface emission, never a red CAD
    # perimeter, so the plate reads as an object rather than an outlined diagram.
    _draw_box(image, (x, -1.65, z), (6.8 * scale, 1.05, 4.4 * scale), "#303840", camera, outline=None)

    if heat > 1.0:
        h = max(0.0, min(1.0, (heat - 1.0) / 0.45))
        corners = [
            (x - 3.28 * scale, -1.055, z - 2.02 * scale),
            (x + 3.28 * scale, -1.055, z - 2.02 * scale),
            (x + 3.28 * scale, -1.055, z + 2.02 * scale),
            (x - 3.28 * scale, -1.055, z + 2.02 * scale),
        ]
        _draw_soft_projected_polygon(
            image,
            corners,
            "#ff4a2b" if heat >= 1.25 else "#ff7954",
            camera,
            alpha=int(30 + 42 * h),
            blur=16.0,
        )

    _draw_box(image, (x, -1.09, z), (6.50 * scale, 0.10, 4.10 * scale), "#575f66", camera, outline=None)

    # Stable brushed-metal reflections.
    _draw_box(image, (x, -1.035, z - 0.62 * scale), (5.65 * scale, 0.018, 0.055 * scale), "#707980", camera)
    _draw_box(image, (x, -1.033, z + 0.58 * scale), (4.90 * scale, 0.016, 0.035 * scale), "#646d74", camera)

    if heat > 1.0:
        h = max(0.0, min(1.0, (heat - 1.0) / 0.45))
        _draw_soft_projected_ellipse(
            image,
            (x, -1.005, z),
            (2.55 * scale, 0.040, 1.45 * scale),
            "#ff6b3a" if heat >= 1.25 else "#ff9a68",
            camera,
            alpha=int(24 + 36 * h),
            blur=9.0,
        )


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
    # Render the cushion as a soft translucent film, not a stack of faceted
    # cyan solids. A denser center plus faint edge leakage keeps the physical
    # structure legible without turning it into a diagram arrow.
    cx, cy, cz = center
    sway_x = 0.055 * spread * math.sin(phase * math.pi * 2.0)
    sway_z = 0.040 * spread * math.sin((phase + 0.23) * math.pi * 2.0)
    _draw_soft_projected_ellipse(
        image,
        (cx + sway_x * 0.30, cy, cz + sway_z * 0.20),
        (2.16 * spread, max(0.045, thickness * 0.76), 1.48 * spread),
        "#1d6678",
        camera,
        alpha=max(42, int(alpha * 0.38)),
        blur=9.0,
    )
    _draw_soft_projected_ellipse(
        image,
        (cx - sway_x * 0.18, cy + thickness * 0.08, cz - sway_z * 0.15),
        (1.66 * spread, max(0.035, thickness * 0.54), 1.16 * spread),
        "#58dbe8",
        camera,
        alpha=max(72, int(alpha * 0.68)),
        blur=4.0,
    )
    _draw_soft_projected_ellipse(
        image,
        (cx + sway_x * 0.12, cy + thickness * 0.14, cz + sway_z * 0.08),
        (0.88 * spread, max(0.025, thickness * 0.30), 0.63 * spread),
        "#b7fbff",
        camera,
        alpha=max(46, int(alpha * 0.36)),
        blur=2.0,
    )

    if outflow > 0.0:
        strength=max(0.0,min(1.0,outflow))
        for idx,side in enumerate((-1.0,1.0)):
            start_x=cx+side*1.42*spread
            pts=[]
            for k in range(7):
                u=k/6.0
                curl=math.sin((phase*1.7+idx*0.31+u*0.8)*math.pi*2.0)
                pts.append((
                    start_x+side*(0.18+0.72*u)*spread*strength,
                    cy+thickness*(0.04+0.14*u)+0.018*curl,
                    cz+0.11*curl*(0.25+0.75*u),
                ))
            _draw_soft_path(
                image,
                pts,
                "#77e6ef",
                camera,
                width=max(3,int(5*strength)),
                alpha=int(80+65*strength),
                blur=4.5,
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
        _draw_soft_path(
            image,
            points,
            "#ff6b35",
            camera,
            width=max(8, int(13 * strength)),
            alpha=min(130, int(82 + 38 * strength)),
            blur=5.0,
        )
        _draw_path(
            image,
            points,
            "#ffc766",
            camera,
            width=max(2, int(2.5 * strength)),
            arrow=False,
            alpha=min(145, int(100 + 28 * strength)),
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
        _draw_droplet(
            image, (glide_x, 0.58 + 0.05 * math.sin(t * math.pi * 4.0), 0.0),
            0.82, camera, t, intensity=0.14, flatten=0.04, phase=0.19,
        )
        _draw_soft_path(
            image, [(1.1, -0.35, 0.7), (1.6, -0.28, 0.5), (2.4, -0.16, 0.1)],
            "#58d6e8", camera, width=7, alpha=95, blur=5.0,
        )

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
        _draw_contact_shadow(image, camera, (0.0, -0.965, 0.30), (1.08, 0.76), alpha=48)

        # A broad vapor front sweeps across the hot surface. This is a real
        # physical state change, not a crop/zoom: the illuminated gas occupies
        # a much larger fraction of the frame as it spreads outward.
        front = t * t * (3.0 - 2.0 * t)
        _draw_soft_projected_ellipse(
            image,
            (0.0, -0.60 + 0.05 * math.sin(t * math.pi * 2.0), 0.30),
            (1.55 + 1.65 * front, 0.085 + 0.055 * front, 1.02 + 0.92 * front),
            "#78eef5",
            camera,
            alpha=72 + int(42 * front),
            blur=11.0 - 3.0 * front,
        )
        _draw_soft_projected_ellipse(
            image,
            (0.0, -0.51, 0.30),
            (0.82 + 1.35 * front, 0.052 + 0.045 * front, 0.56 + 0.76 * front),
            "#c5fbff",
            camera,
            alpha=58 + int(52 * front),
            blur=5.5,
        )
        _draw_vapor_layer(
            image, camera, center=(0.0, -0.48, 0.30),
            spread=0.42 + 1.12 * t, thickness=0.09 + 0.13 * t,
            alpha=168, phase=t, outflow=0.48 + 0.52 * t,
        )
        _draw_droplet(
            image,
            (0.0, 0.66 + 0.62 * t + 0.12 * math.sin(t * math.pi * 2.0), 0.30),
            0.98, camera, t, intensity=0.125, flatten=0.07 * (1.0 - t), phase=0.18,
        )

    elif kind == "vapor_cushion":
        _draw_plate(image, camera, 1.28, z=-0.35, scale=1.02)
        _draw_contact_shadow(image, camera, (0.0, -0.965, -0.35), (1.30, 0.88), alpha=42)

        # The expanding cloud resolves into a thinner, brighter load-bearing
        # cushion. The darkened lighting state makes this a clear second beat.
        settle = t * t * (3.0 - 2.0 * t)
        _draw_soft_projected_ellipse(
            image,
            (0.0, -0.43, -0.35),
            (2.35 + 0.35 * pulse, 0.075 + 0.025 * pulse, 1.42 + 0.20 * pulse),
            "#bafcff",
            camera,
            alpha=105 + int(35 * pulse),
            blur=3.8,
        )
        _draw_vapor_layer(
            image, camera, center=(0.0, -0.42, -0.35),
            spread=0.82 + 0.38 * settle, thickness=0.12 + 0.08 * pulse,
            alpha=188, phase=t, outflow=0.58 + 0.28 * pulse,
        )
        _draw_droplet(
            image,
            (0.0, 0.82 + 0.42 * settle + 0.11 * math.sin(t * math.pi * 4.0), -0.35),
            1.12, camera, t, intensity=0.13, flatten=0.055 * (1.0 - settle), phase=0.07,
        )

    elif kind == "no_contact":
        _draw_plate(image, camera, 1.25, x=-0.72, z=0.45, scale=0.90)
        gap = 0.48 + 0.34 * pulse
        _draw_vapor_layer(image, camera, center=(-0.72, -0.48, 0.45), spread=0.88 + 0.18 * pulse, thickness=0.16)
        _draw_droplet(
            image, (-0.72, 0.58 + gap, 0.45), 0.98, camera, t,
            intensity=0.105, flatten=0.035, phase=0.13,
        )
        _draw_soft_path(
            image, [(1.65, -0.92, 0.35), (1.65, -0.35, 0.35), (1.65, 0.34, 0.35)],
            "#d9efff", camera, width=6, alpha=90, blur=4.0,
        )

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
            _draw_soft_path(image, pts, "#ff6b35", camera, width=13, alpha=105, blur=6.0)
            _draw_path(image, pts, "#ffc766", camera, width=2, arrow=False, alpha=105)

    elif kind == "paradox_shield":
        image.paste((34, 8, 7, 255), (0, 0, width, height))
        _draw_plate(image, camera, 1.45)
        _draw_vapor_layer(image, camera, spread=1.05 + 0.08 * pulse, thickness=0.19)
        _draw_droplet(
            image, (0.0, 0.70 + bob, 0.0), 0.95, camera, t,
            intensity=0.12, flatten=0.045, phase=0.17,
        )
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
            _draw_soft_path(image, path, "#58d6e8", camera, width=7, alpha=105, blur=5.0)

    elif kind == "support_force":
        _draw_plate(image, camera, 1.32, x=-0.25, z=0.35)
        _draw_vapor_layer(
            image, camera, center=(-0.25, -0.44, 0.35),
            spread=0.92 + 0.24 * pulse, thickness=0.20, phase=t, outflow=0.56,
        )
        _draw_droplet(
            image, (-0.25, 0.62 + 0.62 * t + 0.10 * math.sin(t * math.pi * 4.0), 0.35),
            1.00, camera, t, intensity=0.13, flatten=0.05 * (1.0 - t), phase=0.09,
        )
        for x in (-1.35, -0.25, 0.85):
            _draw_soft_path(
                image, [(x, -0.82, 0.35), (x, -0.10 + 0.22 * t, 0.35)],
                "#72e8f5", camera, width=9, alpha=110, blur=5.0,
            )
        _draw_heat_arrows(image, camera, count=3, strength=0.70, y1=-0.48, bend=0.18, phase=t)

    elif kind == "name":
        _draw_plate(image, camera, 1.26, x=0.0, z=0.55, scale=0.82)
        _draw_vapor_layer(image, camera, center=(0.0, -0.40, 0.25), spread=1.28 + 0.18 * pulse, thickness=0.18)
        _draw_droplet(
            image, (0.0, 0.92 + 0.26 * math.sin(t * math.pi * 2.0), 0.25),
            1.38, camera, t, intensity=0.11, flatten=0.05, phase=0.25,
        )
        _draw_soft_path(
            image, [(-2.4, -0.35, 0.0), (0.0, -0.08, 0.65), (2.4, -0.35, 0.0)],
            "#58d6e8", camera, width=10, alpha=95, blur=5.0,
        )
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
        _draw_soft_path(
            image, [(-1.9, -0.34, -0.3), (-0.7, -0.18, 0.45), (0.6, -0.24, -0.35), (1.8, -0.12, 0.25)],
            "#6ee8f5", camera, width=9, alpha=105, blur=5.0,
        )
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
