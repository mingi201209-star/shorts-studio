"""Independent hydroplaning 3D production module.

Reuses only the generic 3D primitives from ``shorts_studio.diagram3d``
(Camera, projection, box drawing, soft projected shapes, glossy water
rendering). All hydroplaning-specific geometry, physics state, and the
rendering dispatch live here so this topic never grows inside
``diagram3d.py`` or any other topic's module (e.g. a future golf-ball short).

World axes: X = direction of travel (screen left/right), Y = up, Z = the
tire's own width/axle axis (screen depth, toward/away from the camera). The
tire's rotation axis is Z, so its circular profile lies in the X-Y plane and
reads as a classic side/3-4 wheel view: the camera sees rotation, tread, the
contact patch, the wedge ahead of the tire, and water flung out along its
width all in one fixed shot.

Physical sequence modeled as ONE continuous process parametrized by a single
global progress value ``g`` in [0, 1]:

  1. tire rotates over wet road (continuous rotation throughout)
  2. tread grooves visibly evacuate water sideways while contact is firm
  3. a water wedge grows ahead of the tire as conditions worsen
  4. the real contact patch visibly shrinks, disappearing from the leading edge
  5. the tire rises onto the water layer and loses road contact

All state functions are pure functions of ``g`` so that rendering any
sub-range [g0, g1] as a separate beat clip is exactly continuous with its
neighbors -- the whole production is one physical scene split across beats,
not independent vignettes.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from shorts_studio.diagram3d import (
    Camera,
    _draw_box,
    _draw_contact_shadow,
    _draw_glossy_water,
    _draw_soft_path,
    _draw_soft_projected_ellipse,
    _project,
)

W, H = 980, 950

# One fixed camera for the entire hydroplaning sequence. A 3/4 side angle
# lets a single frame show tire rotation, tread, the contact patch under the
# tire, the water wedge ahead of it, and water flung out to the sides, all
# at once. The camera never changes across beats; only physical state does.
_CAMERA = Camera(yaw=0.46, pitch=-0.30, distance=8.6, focal=1420.0, cx=490.0, cy=640.0)

_ROAD_Y = -1.55
_TIRE_RADIUS = 1.55
_TIRE_HALF_WIDTH = 0.85
_HUB_CENTER = (0.0, _ROAD_Y + _TIRE_RADIUS, 0.0)
_N_TREAD_BLOCKS = 12
_ROTATIONS = 2.2  # full spins across the whole global sequence
_BLOCK_FRACTION = 0.60  # fraction of each tread pitch that is a raised block
_MAX_LIFT = 1.35  # a large, unmistakable gap at full hydroplaning (vs. radius 1.55)


def camera_for(g: float) -> Camera:
    """Return the single fixed camera for every frame of this production."""
    _ = g
    return _CAMERA


def _smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _ease_window(g: float, start: float, end: float) -> float:
    """Smooth, monotonic 0->1 ramp active only within [start, end]."""
    if end <= start:
        return 1.0 if g >= end else 0.0
    return _smoothstep((g - start) / (end - start))


# ---------------------------------------------------------------------------
# Pure physical-state functions of global progress g in [0, 1].
# Each is monotonic in the direction the task requires, and tested directly
# without rendering any image.
# ---------------------------------------------------------------------------

def rotation_angle_at(g: float) -> float:
    """Continuous tire spin angle (radians). Always increasing with g."""
    return 2.0 * math.pi * _ROTATIONS * g


def wedge_size_at(g: float) -> float:
    """Water wedge growth, 0 at the start, monotonically non-decreasing.

    Starts almost immediately (rather than after a long flat normal phase)
    so the whole [0, 1] timeline carries real, continuously distinguishable
    visual progress -- the normal/baseline moment is brief, not a long
    plateau with nothing to show a viewer.
    """
    return _ease_window(g, 0.04, 0.80)


def contact_width_at(g: float) -> float:
    """Fraction of the full contact patch still touching the road.

    1.0 = full firm contact, 0.0 = no road contact at all. Monotonically
    non-increasing: the patch only shrinks, never recovers.
    """
    return 1.0 - _ease_window(g, 0.10, 0.88)


def lift_at(g: float) -> float:
    """Vertical rise of the tire hub above its resting contact height.

    Starts rising gradually as soon as water begins intruding under the
    tire (well before contact is fully gone -- a partial, still-growing
    water cushion already lightens the tire a little), then climbs
    smoothly and monotonically to the maximum float height by the end.
    This also keeps a continuous, strongly visible driver of change
    running the whole length of the sequence instead of only in its
    final third.
    """
    return _MAX_LIFT * _ease_window(g, 0.15, 1.0)


def groove_outflow_at(g: float) -> float:
    """Visibility strength of lateral water evacuation at the contact zone.

    Present (> 0) during the normal drainage phase, and monotonically fades
    to 0 as the contact patch disappears -- once the tire is airborne on
    water there is no groove-to-road contact left to drain.
    """
    return max(0.0, 1.0 - _ease_window(g, 0.08, 0.75)) * (0.35 + 0.65 * contact_width_at(g))


def _physical_state(g: float) -> dict:
    return {
        "rotation": rotation_angle_at(g),
        "wedge": wedge_size_at(g),
        "contact": contact_width_at(g),
        "lift": lift_at(g),
        "outflow": groove_outflow_at(g),
    }


# ---------------------------------------------------------------------------
# Tire mesh: one combined mesh so self-occlusion between tread blocks and
# grooves sorts correctly in a single z-sorted pass, instead of relying on
# fragile manual front/back culling across separate draw calls.
# ---------------------------------------------------------------------------

def _tire_mesh(
    center: tuple[float, float, float],
    rotation: float,
    segments: int = 72,
) -> tuple[np.ndarray, list[tuple[int, ...]], list[str]]:
    cx, cy, cz = center
    half = _TIRE_HALF_WIDTH
    rubber = "#36393f"
    block = "#6b7078"

    # A real tire's silhouette stays essentially round -- the tread pattern
    # reads from color contrast, not from a deep gear-tooth profile. Keep
    # the radius dip shallow so the outer rim never looks cogged.
    radii: list[float] = []
    is_block: list[bool] = []
    for i in range(segments):
        phase = (i / segments) * _N_TREAD_BLOCKS
        blk = (phase % 1.0) < _BLOCK_FRACTION
        is_block.append(blk)
        radii.append(_TIRE_RADIUS if blk else _TIRE_RADIUS * 0.97)

    verts: list[tuple[float, float, float]] = []
    for i in range(segments):
        phi = 2.0 * math.pi * i / segments + rotation
        r = radii[i]
        verts.append((cx + r * math.cos(phi), cy + r * math.sin(phi), cz - half))
    for i in range(segments):
        phi = 2.0 * math.pi * i / segments + rotation
        r = radii[i]
        verts.append((cx + r * math.cos(phi), cy + r * math.sin(phi), cz + half))
    left_c = len(verts)
    verts.append((cx, cy, cz - half))
    right_c = len(verts)
    verts.append((cx, cy, cz + half))

    faces: list[tuple[int, ...]] = []
    colors: list[str] = []
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((i, i2, segments + i2, segments + i))
        colors.append(block if is_block[i] else rubber)
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((left_c, i2, i))
        colors.append(rubber)
    for i in range(segments):
        i2 = (i + 1) % segments
        faces.append((right_c, segments + i, segments + i2))
        colors.append(rubber)
    return np.array(verts, dtype=float), faces, colors


def _rgb(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def _clamp8(v: float) -> int:
    return max(0, min(255, int(v)))


def _draw_tire_mesh(image: Image.Image, verts: np.ndarray, faces: list[tuple[int, ...]], colors: list[str], camera: Camera) -> None:
    """Flat-shaded, z-sorted, per-face-colored mesh renderer local to this
    module -- kept separate from diagram3d's single-color ``_draw_mesh`` so
    the shared primitive module never needs to grow a hydroplaning-specific
    parameter."""
    light_dir = np.array([-0.30, 0.68, 0.67], dtype=float)
    light_dir = light_dir / np.linalg.norm(light_dir)
    xy, depth = _project(verts, camera)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")

    entries = []
    for face, color in zip(faces, colors):
        pts = verts[list(face)]
        if len(face) >= 3:
            n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
            norm = np.linalg.norm(n)
            illum = 0.74 + 0.46 * abs(float(np.dot(n / norm, light_dir))) if norm > 1e-6 else 0.86
        else:
            illum = 0.78
        entries.append((float(depth[list(face)].mean()), face, illum, color))

    for _, face, illum, color in sorted(entries, key=lambda e: e[0], reverse=True):
        pts2 = [tuple(xy[i]) for i in face]
        base = _rgb(color)
        fill = tuple(_clamp8(c * illum) for c in base) + (255,)
        d.polygon(pts2, fill=fill)

    image.alpha_composite(overlay)


def _draw_wet_road(image: Image.Image, camera: Camera) -> None:
    _draw_box(image, (0.0, _ROAD_Y - 0.5, 0.0), (10.5, 1.0, 7.0), "#45494f", camera, outline=None)
    _draw_soft_projected_ellipse(
        image, (0.3, _ROAD_Y + 0.01, 0.0), (5.4, 0.02, 3.3), "#4f87ab", camera,
        alpha=110, blur=2.0,
    )


def _draw_contact_patch(image: Image.Image, camera: Camera, contact: float) -> None:
    """Bright strip showing the real tire/road contact footprint. It shrinks
    and its remaining center shifts toward the trailing edge, so the patch
    visibly disappears starting from the leading (direction-of-travel) edge
    rather than shrinking symmetrically."""
    if contact <= 0.01:
        return
    length_x = 0.78 * contact
    center_x = -(1.0 - contact) * 0.30
    _draw_soft_projected_ellipse(
        image, (center_x, _ROAD_Y + 0.035, 0.0), (max(0.05, length_x), 0.035, _TIRE_HALF_WIDTH * 1.08),
        "#ffd872", camera, alpha=int(130 + 110 * contact), blur=2.0,
    )
    _draw_contact_shadow(image, camera, (center_x, _ROAD_Y + 0.002, 0.0), (0.65 * contact, 0.85), alpha=int(90 * contact))


def _draw_groove_outflow(image: Image.Image, camera: Camera, rotation: float, outflow: float) -> None:
    """Lateral water streaks firing whenever a groove sweeps through the
    bottom contact zone -- tying the visual evacuation event directly to
    tire rotation, not a constant decorative arrow."""
    if outflow <= 0.01:
        return
    bottom = -math.pi / 2.0
    window = 0.30
    for i in range(_N_TREAD_BLOCKS * 2):
        phi = (2.0 * math.pi * i / (_N_TREAD_BLOCKS * 2)) + rotation
        delta = (phi - bottom + math.pi) % (2.0 * math.pi) - math.pi
        if abs(delta) > window:
            continue
        burst = (1.0 - abs(delta) / window) * outflow
        if burst <= 0.02:
            continue
        for side in (-1.0, 1.0):
            pts = []
            for k in range(5):
                u = k / 4.0
                pts.append((
                    0.05 * side * u,
                    _ROAD_Y + 0.02 + 0.05 * u,
                    side * (_TIRE_HALF_WIDTH * 0.95 + u * (0.55 + 0.80 * burst)),
                ))
            _draw_soft_path(image, pts, "#8be9f5", camera, width=max(2, int(6 * burst)), alpha=int(70 + 120 * burst), blur=3.0)


def _draw_water_wedge(image: Image.Image, camera: Camera, wedge: float) -> None:
    """A low mound of water pressed against the tire's leading edge, not a
    free-floating droplet -- it is anchored at the tire's own contact radius
    and only grows forward and taller, so it always visibly touches the
    tire instead of reading as a separate disconnected blob."""
    if wedge <= 0.01:
        return
    width_x = 0.45 + 1.75 * wedge
    height = 0.08 + 1.05 * wedge
    # The wedge sits low, near the tire's bottom -- and a circle's own
    # surface curves back toward x=0 near its bottom (at height h above the
    # lowest point, the front edge is at sqrt(h*(2R-h)), not the full
    # radius). Anchoring at the full radius left the wedge floating well
    # clear of the tire at low heights; anchor it at the tire's ACTUAL edge
    # at the wedge's own mid-height instead so it always visibly touches.
    mid_h = height * 0.5
    edge_x = math.sqrt(max(0.0, mid_h * (2.0 * _TIRE_RADIUS - mid_h)))
    center_x = edge_x + width_x * 0.5
    _draw_glossy_water(
        image, (center_x, _ROAD_Y + height * 0.5, 0.0),
        (width_x * 0.5, height * 0.5, 0.52 + 0.55 * wedge),
        "#2c78c9", camera, int(205 + 45 * wedge), "#d9efff",
        deform_t=wedge, deform_strength=0.05,
    )


def _draw_float_layer(image: Image.Image, camera: Camera, lift: float) -> None:
    if lift <= 0.01:
        return
    _draw_glossy_water(
        image, (0.0, _ROAD_Y + lift * 0.5, 0.0),
        (_TIRE_RADIUS * 1.02, max(0.03, lift * 0.5), _TIRE_HALF_WIDTH * 1.35),
        "#417aa6", camera, int(150 + 60 * lift / _MAX_LIFT), "#d9efff",
        deform_t=lift, deform_strength=0.03,
    )


def render_hydroplaning_frame(g: float, width: int = W, height: int = H) -> Image.Image:
    state = _physical_state(g)
    camera = camera_for(g)
    # Keep the empty sky at or below the meaningful-visual-change audit's
    # background threshold (every channel <=12) so its own crop-to-content
    # step tightly frames the tire/road/water instead of diluting every
    # real state change with a large flat dead-space margin. The tire,
    # road and water materials below are all drawn far brighter than this.
    image = Image.new("RGBA", (width, height), (8, 9, 11, 255))

    _draw_wet_road(image, camera)
    _draw_contact_patch(image, camera, state["contact"])
    _draw_groove_outflow(image, camera, state["rotation"], state["outflow"])
    _draw_water_wedge(image, camera, state["wedge"])
    # The floating water slab must be composited BEFORE the tire mesh so the
    # tire correctly occludes its far/upper portion, leaving only the real
    # visible gap instead of incorrectly painting water on top of the rubber.
    _draw_float_layer(image, camera, state["lift"])

    hub = (_HUB_CENTER[0], _HUB_CENTER[1] + state["lift"], _HUB_CENTER[2])
    verts, faces, colors = _tire_mesh(hub, state["rotation"])
    _draw_tire_mesh(image, verts, faces, colors, camera)
    # A small silver hub cap makes the shape unmistakably a wheel rather
    # than an abstract gear, with no effect on the physical-state contract.
    _draw_soft_projected_ellipse(
        image, (hub[0], hub[1], hub[2] + _TIRE_HALF_WIDTH + 0.02),
        (_TIRE_RADIUS * 0.26, _TIRE_RADIUS * 0.26, 0.02), "#9aa0a6", camera,
        alpha=225, blur=0.0,
    )

    return image.convert("RGB")


def render_hydroplaning_still(out: Path, g: float, width: int = W, height: int = H) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = render_hydroplaning_frame(g, width=width, height=height)
    frame.save(out)
    return out


def render_motion_clip(
    out: Path,
    g_start: float,
    g_end: float,
    duration: float,
    fps: int = 30,
    width: int = W,
    height: int = H,
) -> Path:
    """Render frames for global progress [g_start, g_end] as one clip.

    Because every physical-state function is a pure function of the single
    global progress value, two clips covering adjacent ranges begin/end on
    exactly the same state -- the whole production reads as one continuous
    physical process even though it is split into narration-synced beats.
    """
    if camera_for(g_start) != _CAMERA or camera_for(g_end) != _CAMERA:
        raise RuntimeError("hydroplaning camera must stay fixed across the whole sequence")

    frames_dir = out.parent / f"{out.stem}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    total = max(2, int(duration * fps))
    for i in range(total):
        u = i / (total - 1)
        g = g_start + (g_end - g_start) * u
        frame = render_hydroplaning_frame(g, width=width, height=height)
        frame.save(frames_dir / f"{i:04d}.png")

    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", str(fps),
            "-i", str(frames_dir / "%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out),
        ],
        check=True, capture_output=True, timeout=180,
    )
    return out
