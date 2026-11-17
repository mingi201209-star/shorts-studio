"""EP.04 cameras as plain data plus a pinhole projection that matches Blender's world_to_camera_view (horizontal sensor fit, 36 mm, lens shift in sensor-width units).
The renderer places its cameras from these numbers, and the Python tests project the real sedan vertices through the same numbers: a camera problem (action under the captions,
subject out of frame) shows up in a test in milliseconds instead of in a 17-minute preview."""
from __future__ import annotations

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm

SENSOR_W = 36.0
PANEL_PX = {"full": (1080, 1920), "stack": (1080, 960), "sequential": (1080, 1920)}


#: The only on-screen words besides the narration captions: one word per car in the comparison, as a 3D sign on the road under each car.
#: Placed (by search) in the free band between the tyres and the caption rows of BOTH stacked panels, away from the Shorts interface zones.
SIGN = {"pos": (-1.4, -1.6, 0.32), "size": 0.18, "char_w": 0.75, "words": {"crumple": "CRUMPLE", "rigid": "RIGID"}}
FRAME_W, FRAME_H = 1080, 1920
CAPTION_ROWS = (1408, 1540)
#: mobile safe area of a 1080x1920 Short: keep clear of the top ~8 %, the bottom ~20 % and the right ~11 % (like/comment buttons)
SAFE = {"left": 54, "right": 960, "top": 150, "bottom": 1540}
PANEL_OFFSET = {"crumple": 0, "rigid": 960}


def sign_boxes(frame: int = 30) -> dict:
    """Frame-pixel box (rows, cols) of each comparison sign: billboard facing the camera, width = chars * size * char_w."""
    cam = camera("compare", frame)
    c = np.array(SIGN["pos"], float)
    toc = np.array(cam["loc"]) - c
    toc /= np.linalg.norm(toc)
    rr = np.cross([0, 0, 1], toc)
    rr /= np.linalg.norm(rr)
    uu = np.cross(toc, rr)
    out = {}
    for kind, word in SIGN["words"].items():
        w, h = len(word) * SIGN["size"] * SIGN["char_w"], SIGN["size"]
        pts = np.array([c + sx * rr * w / 2 + sy * uu * h / 2 for sx in (-1, 1) for sy in (-1, 1)])
        layout = cm.segment_at(frame)["layout"]
        p = project(pts, cam, "sequential" if layout == "sequential" else "stack")
        rows = (1 - p[:, 1]) * 1920 if layout == "sequential" else PANEL_OFFSET[kind] + (1 - p[:, 1]) * 960
        out[kind] = {"rows": (float(rows.min()), float(rows.max())), "cols": (float(p[:, 0].min() * 1080), float(p[:, 0].max() * 1080))}
    return out


def _base_camera(kind: str, frame: int = 1) -> dict:
    """{'loc', 'target', 'lens', 'shift_y'} for a camera kind at a film frame."""
    if kind == "hero":
        return {"loc": (-2.7, -2.3, 0.8), "target": (0.0, -0.25, 0.5), "lens": 34.0, "shift_y": 0.0}
    if kind == "compare":
        return {"loc": (-3.4, -2.8, 1.0), "target": (0.0, -0.7, 0.5), "lens": 30.0, "shift_y": -0.25}
    if kind == "xray":
        seg = cm.segment_at(frame)
        seg_len = seg["last"] - seg["first"] + 1
        k = min(1.0, max(0.0, (frame - seg["first"]) / max(74.0, seg_len)))      # slow push-in that keeps going over the whole X-ray segment (the first segment keeps its original 74-frame span)
        loc = tuple(float(v) * (1 - 0.06 * k) for v in (-5.0, -5.2, 2.4))        # found by a search that keeps nose, rails and cell inside the frame for every X-ray frame
        return {"loc": loc, "target": (0.0, -1.3, 0.45), "lens": 34.0, "shift_y": 0.0}
    raise ValueError(kind)


ORBIT_DEG = 16.0      # replay segments: the camera sweeps this many degrees around the subject over the segment (the first three segments keep their validated fixed cameras)


def camera(kind: str, frame: int = 1) -> dict:
    """Camera of a film frame: the base camera of its kind, plus a slow orbit in the replay segments (the replays are long slow motion; without camera motion the picture changes too little from frame to frame)."""
    cam = _base_camera(kind, frame)
    seg = cm.segment_at(frame)
    if seg["id"] in ("H", "C", "X"):
        return cam
    duration = seg["last"] - seg["first"]
    if kind == "compare":
        crumple = next(s for s in cm.SEGMENTS if s["id"] == "C2")
        duration = crumple["last"] - crumple["first"]
    k = min(1.0, (frame - seg["first"]) / max(1, duration))
    a = np.radians(ORBIT_DEG * (k - 0.5))
    tx, ty, _ = cam["target"]
    x, y, z = cam["loc"]
    dx, dy = x - tx, y - ty
    loc = (tx + dx * np.cos(a) - dy * np.sin(a), ty + dx * np.sin(a) + dy * np.cos(a), z)
    return {**cam, "loc": tuple(float(v) for v in loc)}


def project(points: np.ndarray, cam: dict, layout: str) -> np.ndarray:
    """(N, 3) world points -> (N, 3): x, y in [0, 1] (y up, like world_to_camera_view) and depth (> 0 in front of the camera)."""
    w, h = PANEL_PX[layout]
    loc, target = np.array(cam["loc"], float), np.array(cam["target"], float)
    f = target - loc
    f /= np.linalg.norm(f)
    right = np.cross(f, np.array([0.0, 0.0, 1.0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, f)
    d = np.asarray(points, float) - loc
    xc, yc, zc = d @ right, d @ up, d @ f
    sensor_h = SENSOR_W * h / w
    x = 0.5 + cam["lens"] * xc / (zc * SENSOR_W)
    y = 0.5 + cam["lens"] * yc / (zc * sensor_h) - cam["shift_y"] * (w / h)
    return np.column_stack([x, y, zc])
