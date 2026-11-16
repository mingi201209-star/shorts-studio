"""EP.04 explanatory 3D primitives (pure data, no Blender): stopping-distance and stopping-time bars on the road, average-force arrows, the simplified occupant with belt and airbag.
The renderer materialises exactly these primitives each frame, and the Python tests project the same primitives through the camera data, so presence / position / size of every
explanatory object is checked without rendering. All of it is EXPLANATORY: bar and arrow lengths are linear in simulated quantities of an illustrative model (not a crash test)."""
from __future__ import annotations

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm

LAYER_X = {"dist": -1.38, "time": -1.68}      # lanes of the bars on the road, on the camera side of the car (half width 0.8, wheels to 0.8)
SEAT_X = -0.38


def _prim(id_, shape, mat, frame="world", **kw):
    return {"id": id_, "shape": shape, "mat": mat, "frame": frame, **kw}


def bars(profile: str, rec: dict, i: int, nose: float) -> list[dict]:
    """Distance bar (how far the car travelled while stopping) and time bar (how long it took), both growing from the cabin line at first contact."""
    dist, tim = cm.stopping_distance_time(rec, i)
    y0 = -(nose - (nose - cm.CRUSH_LENGTH))            # the cabin line (firewall) when the nose touches the wall: 0.95 m behind the barrier face
    out = [_prim(f"{profile}.start", "box", "bar_line", center=(-1.53, y0, 0.011), size=(0.62, 0.035, 0.022))]
    if dist > 1e-4:
        out.append(_prim(f"{profile}.distance_bar", "box", "bar_dist", center=(LAYER_X["dist"], y0 + dist / 2, 0.015), size=(0.2, dist, 0.03)))
        L = cm.TIME_BAR_SCALE * tim
        out.append(_prim(f"{profile}.time_bar", "box", "bar_time", center=(LAYER_X["time"], y0 + L / 2, 0.015), size=(0.2, max(L, 1e-4), 0.03)))
    return out


def force_arrow(profile: str, rec: dict, i: int) -> list[dict]:
    """Average stopping force of this car as an arrow on the road beside the nose, pointing back along the car (the barrier pushes the car backwards): linear in kN."""
    contact, _ = cm.stop_phase(rec)
    if i < contact:
        return []
    length = cm.ARROW_PER_KN * cm.average_force_kn(profile)
    grow = min(1.0, float(rec["t"][i] - rec["t"][contact]) / 0.004)
    L = max(0.02, length * grow)
    head = min(0.16, L)
    shaft = max(L - head, 0.0)
    x, z = -1.0, 0.5
    prims = [_prim(f"{profile}.force_head", "cone", "arrow", p0=(x, -L + head, z), p1=(x, -L, z), radius=0.09)]
    if shaft > 1e-3:
        prims.append(_prim(f"{profile}.force_shaft", "cyl", "arrow", p0=(x, 0.0, z), p1=(x, -shaft, z), radius=0.035))
    return prims


def occupant(rec: dict, occ: dict, i: int, nose: float) -> list[dict]:
    """Simplified driver in the car frame: torso, head, seat, belt (two straps), airbag. The occupant moves forward by x relative to the car."""
    cabin_y = nose - cm.CRUSH_LENGTH
    seat_y = cabin_y - 1.05
    x = float(occ["x"][i])
    open_ = float(occ["bag_open"][i])
    torso_c = (SEAT_X, seat_y + 0.6 * x, 0.86)
    head_c = (SEAT_X, seat_y + 0.05 + 1.25 * x, 1.3)
    chest = (SEAT_X + 0.2, torso_c[1] + 0.1, 0.98)
    wheel_c = (SEAT_X, cabin_y - 0.5, 0.96)
    prims = [
        _prim("seat", "box", "seat", frame="car", center=(SEAT_X, seat_y - 0.2, 0.55), size=(0.46, 0.12, 0.62)),
        _prim("occupant.torso", "box", "occupant", frame="car", center=torso_c, size=(0.36, 0.22, 0.52)),
        _prim("occupant.head", "sphere", "occupant", frame="car", center=head_c, radius=0.115),
        _prim("seat_belt.upper", "cyl", "belt", frame="car", p0=(SEAT_X - 0.34, seat_y - 0.18, 1.28), p1=chest, radius=0.018),
        _prim("seat_belt.lower", "cyl", "belt", frame="car", p0=chest, p1=(SEAT_X - 0.1, seat_y - 0.05, 0.58), radius=0.018),
    ]
    if open_ > 0:
        prims.append(_prim("airbag", "sphere", "airbag", frame="car", center=wheel_c, radius=0.1 + 0.2 * open_))
    return prims


def center_of(p: dict) -> np.ndarray:
    if "center" in p:
        return np.array(p["center"], float)
    return (np.array(p["p0"], float) + np.array(p["p1"], float)) / 2
