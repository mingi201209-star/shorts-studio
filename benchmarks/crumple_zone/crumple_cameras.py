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


def _key(t, loc, target, lens=34.0, at=0.40, rel=False, cut=False):
    """at: fraction of the frame height, from the top, where the look-at point lands (lens shift is derived from it): the subject sits in the upper-middle, above the captions."""
    return {"t": float(t), "loc": tuple(float(v) for v in loc), "target": tuple(float(v) for v in target), "lens": float(lens), "at": float(at), "rel": rel if rel == "car" else bool(rel), "cut": bool(cut)}


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


CAR_NOSE_M = 1.926      # nose of the real sedan in its own frame (fixture geom["nose"]; a test checks it)
DRV_SIDE = ((-2.0, 0.8, 0.95), (0.0, 0.8, 0.95))      # driver's seat, side view (camera x, y, z; target), relative to the cabin (rel="car")


def _orbit_car(t0, t1, pivot, radius, z0, z1, a0, a1, lens, n=6, at=0.42, target_z=0.95):
    """Orbit round the driver's seat (rel="car" keys); angle 0 = camera on the -X side looking +X, positive turns towards -Y."""
    out = []
    for k in range(n + 1):
        u = k / n
        a = np.radians(a0 + (a1 - a0) * u)
        loc = (pivot[0] - radius * np.cos(a), pivot[1] - radius * np.sin(a), z0 + (z1 - z0) * u)
        out.append(_key(t0 + (t1 - t0) * u, loc, (pivot[0], pivot[1], target_z), lens, at, rel="car"))
    return out


def paths() -> dict:
    cue = cm.cue_start
    k = lambda s: _seg_tau(s, "K")
    r = lambda s: _seg_tau(s, "R")
    c = lambda s: _seg_tau(s, "C")
    t_b2, t_b3, t_b4, t_b5 = cue("The hood buckles"), cue("as the hidden rails"), cue(cm.CABIN_BEAT), cue(cm.RIGID_BEAT)
    near = dict(lens=34)      # poses are relative to the front of the car (rel=True) unless noted
    t_slow, t_fold, t_en = cue("and we slow that"), cue("and the front folds back"), cue("energy over a longer")
    K = [
        _key(0.0, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),                      # 1 run-up: tracking three-quarter view, the wall rushes towards the nose
        _key(cm.HOOK_CONTACT_S - 0.01, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),
        _key(cm.HOOK_CONTACT_S, (-3.2, -0.9, 0.65), (0.0, -0.9, 0.5), 28, at=0.45, cut=True),        # 2 CUT at contact ("A car hits a wall"): fixed low side profile
        _key(k(t_slow) - 0.01, (-3.2, -0.9, 0.65), (0.0, -0.9, 0.5), 28, at=0.45),
        _key(k(t_slow), (-2.0, -1.7, 1.45), (0.0, -0.2, 0.5), 34, at=0.45, rel=True, cut=True),      # 3 CUT ("and we slow that"): high three-quarter view of the hood and the front wheel
        _key(k(t_b2) - 0.01, (-2.0, -1.7, 1.45), (0.0, -0.2, 0.5), 34, at=0.45, rel=True),
        _key(k(t_b2), (-1.7, -1.3, 1.3), (0.0, -0.1, 0.85), 34, at=0.45, rel=True, cut=True),       # 4 CUT ("The hood buckles"): raised front-left view that sees the hood top and the nose
        _key(k(t_fold) - 0.01, (-1.7, -1.3, 1.3), (0.0, -0.1, 0.85), 34, at=0.45, rel=True),
        _key(k(t_fold), (-2.4, -0.15, 0.7), (0.0, -1.3, 0.6), 30, at=0.45, cut=True),                # 5 CUT ("the front folds back"): from the wall looking back along the folding flank
        _key(k(t_b3) - 0.4, (-2.4, -0.15, 0.7), (0.0, -1.3, 0.6), 30, at=0.45),
        _key(k(t_b3) + 0.6, (-2.7, -2.3, 1.5), (0.0, -0.55, 0.5), 42, at=0.46, rel=True),             # step out (never through the car) to a close three-quarter view of the front while the scan line passes: the rails fill the frame
        _key(k(t_b3) + 2.8, (-2.4, -2.6, 2.3), (0.0, -0.6, 0.45), 44, at=0.46, rel=True),             # higher, still close view: the folds of the rails seen from above and the side
        _key(k(t_en) - 0.01, (-2.4, -2.6, 2.3), (0.0, -0.6, 0.45), 44, at=0.46, rel=True),
        _key(k(t_en), DRV_SIDE[0], DRV_SIDE[1], 32, at=0.42, rel="car", cut=True),                     # CUT ("energy over a longer stop"): only the driver's seat, side view through the see-through cabin
        _key(k(t_b4) - 0.71, (-1.85, 0.8, 0.95), DRV_SIDE[1], 32, at=0.42, rel="car"),                  # slow push-in
    ]
    _o = _orbit_car(k(t_b4) - 0.7, k(t_b5) - 0.01, (-0.36, 0.55), 1.7, 0.95, 1.1, 0.0, -22.0, 36, n=8, at=0.42)
    _o[0]["cut"] = True      # CUT ("quietly keeps its"): slow orbit round the driver's seat towards the front
    K += _o
    r_con = r(cue(cm.RIGID_CONTACT_CUE))
    R = [
        _key(0.0, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),                      # the same run-up camera as the first crash: the blue car rolls towards the wall
        _key(r_con - 0.01, (-2.9, -2.5, 0.95), (0.0, -0.85, 0.5), 28, at=0.45, rel=True),
        _key(r_con, DRV_SIDE[0], DRV_SIDE[1], 32, at=0.42, rel="car", cut=True),                      # CUT at the contact ("stops almost instantly"): the SAME driver's-seat view as the first crash, the driver lunges at the wheel
        _key(r_con + 0.01, (-1.85, 0.8, 0.95), DRV_SIDE[1], 32, at=0.42, rel="car"),
        _key(r_con + 1.4 - 0.01, (-1.85, 0.8, 0.95), DRV_SIDE[1], 32, at=0.42, rel="car"),              # slow push-in while the car stops and turns round
        _key(r_con + 1.4, (-1.9, 1.05, 1.0), (0.0, 0.7, 0.95), 32, at=0.42, rel="car", cut=True),          # CUT ("and bounces back"): driver's seat from the front-left while the car leaves the wall
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
    off_car = np.array([0.0, ny + cm.pose(frame)["s"] - CAR_NOSE_M, 0.0])      # rel="car": car-frame coordinates (nose at +CAR_NOSE_M, driver's hip at y 0.08): the camera follows the cabin while the nose crushes

    def absolute(key, name):
        v = np.array(key[name], float)
        if key["rel"] == "car":
            return v + off_car
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
        w = 0.0 if b.get("cut") else _smooth((tau - a["t"]) / (b["t"] - a["t"]))      # a cut keeps the old shot until its own time, then jumps
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
