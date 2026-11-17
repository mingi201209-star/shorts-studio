"""EP.04 cameras as plain data plus a pinhole projection that matches Blender's world_to_camera_view (horizontal sensor fit, 36 mm, lens shift in sensor-width units).
The renderer places its cameras from these numbers, and the Python tests project the real sedan vertices through the same numbers: a camera problem (action under the captions,
subject out of frame) shows up in a test in milliseconds instead of in a 17-minute preview.

v2: three camera paths (K = the crumple crash, R = the rigid crash, C = the closing view), each a list of keys in film seconds since the segment start. A key's pose is either
relative to the nose line of the car (rel: the camera follows the car into the wall) or absolute; poses are blended with smoothstep easing, orbits by arc keys."""
from __future__ import annotations

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm

SENSOR_W = 36.0
PANEL_PX = {"full": (1080, 1920)}
FRAME_W, FRAME_H = 1080, 1920
CAPTION_ROWS = (1408, 1540)
#: mobile safe area of a 1080x1920 Short: keep clear of the top ~8 %, the bottom ~20 % and the right ~11 % (like/comment buttons)
SAFE = {"left": 54, "right": 960, "top": 150, "bottom": 1540}
NO_SCENE_TEXT = True      # the owner banned on-screen words other than the narration captions: the renderer creates no text objects (gate: no_scene_text)


def _key(t, loc, target, lens=34.0, at=0.40, rel=False):
    """at: fraction of the frame height, from the top, where the look-at point lands (lens shift is derived from it): the subject sits in the upper-middle, above the captions."""
    return {"t": float(t), "loc": tuple(float(v) for v in loc), "target": tuple(float(v) for v in target), "lens": float(lens), "at": float(at), "rel": bool(rel)}


def _orbit(t0, t1, pivot, radius, z0, z1, a0, a1, lens, n=6, at=0.40, target_z=0.55):
    """Keys on an arc around a pivot (angles in degrees, 0 = camera on the -X side looking +X, positive turns towards -Y)."""
    out = []
    for k in range(n + 1):
        u = k / n
        a = np.radians(a0 + (a1 - a0) * u)
        loc = (pivot[0] - radius * np.cos(a), pivot[1] - radius * np.sin(a), z0 + (z1 - z0) * u)
        out.append(_key(t0 + (t1 - t0) * u, loc, (pivot[0], pivot[1], target_z), lens, at))
    return out


def _seg_tau(seconds: float, seg_id: str) -> float:
    """Spoken moment (film seconds from the start of the film) -> film seconds since the start of segment seg_id."""
    seg = next(s for s in cm.SEGMENTS if s["id"] == seg_id)
    return seconds - (seg["first"] - 1) / cm.FPS


def paths() -> dict:
    cue = cm.cue_start
    k = lambda s: _seg_tau(s, "K")
    r = lambda s: _seg_tau(s, "R")
    c = lambda s: _seg_tau(s, "C")
    t_b2, t_b3, t_b4, t_b5 = cue("to watch the hood"), cue("Hidden rails"), cue(cm.CABIN_BEAT), cue(cm.RIGID_BEAT)
    near = dict(lens=34)      # poses are relative to the front of the car (rel=True) unless noted
    K = [
        _key(0.0, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),                      # run-up: tracking three-quarter view, the wall rushes towards the nose
        _key(cm.HOOK_CONTACT_S, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),
        _key(k(t_b2) + 0.3, (-2.0, -1.7, 1.45), (0.0, -0.2, 0.5), 34, at=0.45, rel=True),             # close high three-quarter view of the hood and the front wheel
        _key(k(t_b3) - 0.4, (-2.0, -1.7, 1.45), (0.0, -0.3, 0.5), 34, at=0.45, rel=True),
        _key(k(t_b3) + 0.6, (-3.2, -3.2, 2.6), (0.0, -0.7, 0.45), 34, at=0.48, rel=True),             # step out and up (never through the car) while the scan line passes
        _key(k(t_b3) + 2.8, (-2.2, -4.3, 3.6), (0.0, -1.0, 0.4), 36, at=0.50, rel=True),             # high chase view over the folding rails, the whole car in frame
        _key(k(t_b4) - 0.2, (-2.2, -4.3, 3.6), (0.0, -1.0, 0.4), 36, at=0.50, rel=True),
    ]
    K += _orbit(k(t_b4) - 0.2, k(t_b5) - 0.01, (0.0, -1.6), 4.1, 3.6, 1.5, 51.0, -15.0, 34, n=8, at=0.45)[1:]      # slow orbit from behind-left round to the crushed front
    R = [
        _key(0.0, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),                      # the same run-up camera as the first crash
        _key(r(cue(cm.RIGID_CONTACT_CUE)) - 0.4, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),
        _key(r(cue(cm.RIGID_CONTACT_CUE)) + 0.3, (-2.0, -1.7, 1.45), (0.0, -0.2, 0.5), 34, at=0.45, rel=True),   # the same close view of the nose as the first crash
        _key(r(cue(cm.RIGID_CONTACT_CUE)) + 2.4, (-3.0, -3.0, 1.4), (0.0, 1.0, 0.6), 30, at=0.45, rel=True),     # the camera follows the car as it moves away, looking back at the wall
    ]
    C = [
        _key(0.0, (-2.6, -3.0, 1.5), (0.0, -0.9, 0.5), 34, at=0.45),
        _key(c(cue(cm.CLOSE_BEAT)) + 2.0, (-3.0, -2.8, 1.6), (0.0, -1.0, 0.5), 34, at=0.45),
        _key(c(cm.TARGET_S), (-3.4, -2.6, 1.7), (0.0, -1.1, 0.5), 34, at=0.45),
    ]
    return {"K": K, "R": R, "C": C}


_PATHS = None


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def camera(kind: str, frame: int = 1) -> dict:
    """{'loc', 'target', 'lens', 'shift_y'} of a film frame for the camera path `kind` of its segment."""
    global _PATHS
    if _PATHS is None:
        _PATHS = paths()
    keys = _PATHS[kind]
    seg = cm.segment_at(frame)
    tau = (frame - seg["first"]) / cm.FPS
    ny = cm.nose_y(frame)
    off = np.array([0.0, ny, 0.0])

    def absolute(key, name):
        v = np.array(key[name], float)
        return v + off if key["rel"] else v

    if tau <= keys[0]["t"]:
        a = b = keys[0]
        w = 0.0
    elif tau >= keys[-1]["t"]:
        a = b = keys[-1]
        w = 0.0
    else:
        i = next(j for j in range(len(keys) - 1) if keys[j]["t"] <= tau < keys[j + 1]["t"])
        a, b = keys[i], keys[i + 1]
        w = _smooth((tau - a["t"]) / (b["t"] - a["t"]))
    loc = absolute(a, "loc") * (1 - w) + absolute(b, "loc") * w
    target = absolute(a, "target") * (1 - w) + absolute(b, "target") * w
    at = a["at"] * (1 - w) + b["at"] * w
    return {"loc": tuple(float(v) for v in loc), "target": tuple(float(v) for v in target), "lens": a["lens"] * (1 - w) + b["lens"] * w,
            "shift_y": (0.5 - (1.0 - at)) * (PANEL_PX["full"][1] / PANEL_PX["full"][0])}


def project(points: np.ndarray, cam: dict, layout: str = "full") -> np.ndarray:
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
