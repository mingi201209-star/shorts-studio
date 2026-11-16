"""EP.04 cameras as plain data plus a pinhole projection that matches Blender's world_to_camera_view (horizontal sensor fit, 36 mm, lens shift in sensor-width units).
The renderer places its cameras from these numbers, and the Python tests project the real sedan vertices through the same numbers: a camera problem (action under the captions,
subject out of frame) shows up in a test in milliseconds instead of in a 17-minute preview."""
from __future__ import annotations

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm

SENSOR_W = 36.0
PANEL_PX = {"full": (1080, 1920), "stack": (1080, 960)}


def camera(kind: str, frame: int = 1) -> dict:
    """{'loc', 'target', 'lens', 'shift_y'} for a camera kind at a film frame."""
    if kind == "hero":
        return {"loc": (-2.7, -2.3, 0.8), "target": (0.0, -0.25, 0.5), "lens": 34.0, "shift_y": 0.0}
    if kind == "compare":
        return {"loc": (-3.4, -2.8, 1.0), "target": (0.0, -0.7, 0.5), "lens": 30.0, "shift_y": -0.25}
    if kind == "xray":
        k = min(1.0, max(0.0, (frame - cm.XRAY_RAMP[0]) / (cm.TOTAL_FRAMES - cm.XRAY_RAMP[0])))
        loc = tuple(float(v) * (1 - 0.06 * k) for v in (-5.0, -5.2, 2.4))        # found by a search that keeps nose, rails and cell inside the frame for every X-ray frame
        return {"loc": loc, "target": (0.0, -1.3, 0.45), "lens": 34.0, "shift_y": 0.0}
    raise ValueError(kind)


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
