"""EP.29 wind-turbine blade lifter (pure Python + numpy): a truck carries an 85 m blade up a winding mountain road (the road of
EP.26, roller_world: forested hillside, rock cut on the left, steep slope and trees on the right). The trailer's lifter holds the
blade by its root and can tilt it up to 60 degrees above the horizontal and swing it up to 20 degrees to either side (the published
Blade Lifter figures); the truck crawls at 20 km/h. Story time t: the lifter is at arc length s(t) = S_START + V t along the right
lane.

The operator's rule in the model: keep the blade at 35 degrees on the straights, raise it to 60 degrees for the bends, and swing it
toward the road ahead (within 20 degrees). The gate checks the claims in the film: a blade lying flat would hang tens of metres off
the road in the bends and run into the rock cut and the trees; tilted and swung it stays above everything; at 60 degrees it sticks
out half as far; the blade is almost as long as a football field; 12 mph; the wind limit; and how the wind's push on a raised blade
compares with what keeps the rig upright. Simplified explanation model, not a transport plan."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from benchmarks.roller_barrier import roller_world as rw

MPH = 0.44704
FT = 0.3048
L_BLADE = 85.0
ROOT_H = 3.2                            # the blade's root axis above the road on the lifter
CHORD = 4.2                             # widest chord (near the root); the blade tapers to the tip
M_BLADE = 30000.0
ALPHA_MAX = math.radians(60.0)
ALPHA_CRUISE = math.radians(35.0)
PSI_MAX = math.radians(20.0)
V = 20.0 / 3.6                          # 20 km/h
LANE_OFF = rw.LANE / 2
S_START = 100.0                         # the lifter's arc length at t = 0 (on the straight after the first left bend)
TRACTOR_AHEAD = 9.5                     # the tractor's reference point is this far ahead of the lifter along the lane
WIND_LIMIT = 10.0                       # m/s with a lifted blade (the published limit)
RIG_MASS = 95000.0                      # tractor, lifter trailer and blade
HALF_TRACK = 1.4
TREE_TOP = 16.0                         # trees' height above the ground beside the road (for the clearance check)
FOOTBALL_FT = 300.0                     # goal line to goal line


@lru_cache(maxsize=None)
def lane():
    pts, hs, s = rw.centre_line()
    lp = pts + LANE_OFF * rw.normals(hs)
    seg = np.linalg.norm(np.diff(lp, axis=0), axis=1)
    sl = np.concatenate([[0.0], np.cumsum(seg)])
    i0 = int(np.argmin(np.abs(s)))
    sl -= sl[i0] - s[i0]
    return lp, np.unwrap(hs), sl


def at(s: float):
    lp, hs, sl = lane()
    return np.array([np.interp(s, sl, lp[:, 0]), np.interp(s, sl, lp[:, 1])]), float(np.interp(s, sl, hs))


def s_of(t: float) -> float:
    return S_START + V * t


def bendiness(s: float, ahead: float = 70.0, behind: float = 25.0) -> float:
    """How much the road turns around s (radians of heading change from `behind` to `ahead`)."""
    _, h0 = at(s - behind)
    _, h1 = at(s + ahead)
    return abs(h1 - h0)


def alpha(s: float) -> float:
    """Tilt: 35 degrees on the straights, up to 60 in the bends (smooth)."""
    b = min(1.0, bendiness(s) / math.radians(30.0))
    u = b * b * (3 - 2 * b)
    return ALPHA_CRUISE + (ALPHA_MAX - ALPHA_CRUISE) * u


def psi(s: float, a: float | None = None) -> float:
    """Swing relative to the trailer: toward the lane point the blade's shadow would reach, within +-20 degrees."""
    a = alpha(s) if a is None else a
    p, h = at(s)
    q, _ = at(s + L_BLADE * math.cos(a) * 0.75)
    want = math.atan2(q[0] - p[0], q[1] - p[1])
    d = (want - h + math.pi) % (2 * math.pi) - math.pi
    return max(-PSI_MAX, min(PSI_MAX, d))


def blade_axis(s: float, a: float, ps: float, n: int = 40) -> np.ndarray:
    """Points along the blade's axis (world x, y, z) from root to tip."""
    p, h = at(s)
    az = h + ps
    u = np.linspace(0.0, L_BLADE, n)
    x = p[0] + u * math.cos(a) * math.sin(az)
    y = p[1] + u * math.cos(a) * math.cos(az)
    z = ROOT_H + u * math.sin(a)
    return np.stack([x, y, z], 1)


def obstacle_top(pts_xy: np.ndarray) -> np.ndarray:
    """Height of whatever stands under a point beside the road: the land, plus trees where they grow."""
    d, _ = rw.signed_offset(pts_xy)
    ground = rw.ground_z(d, pts_xy[:, 0], pts_xy[:, 1])
    trees = (d > rw.TREE_CLEAR[0]) | (d < rw.TREE_CLEAR[1])
    return np.maximum(ground, 0.0) + np.where(trees, TREE_TOP, 0.0) * 1.0 + np.where(d < -4.9, 0.0, 0.0), d


def clearance(s: float, mode: str) -> tuple[float, float]:
    """(how far the blade's shadow reaches past the road edge, lowest gap over what stands there) for 'lifted' or 'flat'."""
    if mode == "flat":
        a, ps = 0.0, 0.0
    else:
        a = alpha(s)
        ps = psi(s, a)
    pts = blade_axis(s, a, ps)
    top, d = obstacle_top(pts[:, :2])
    off = np.maximum(0.0, np.abs(d) - (rw.HALF + 1.0))
    outside = off > 0
    gap = float(np.min(pts[outside, 2] - top[outside])) if outside.any() else 99.0
    return float(off.max()), gap


def wind_moment(a: float, wind: float) -> float:
    """Overturning moment (N m) of the wind's push on the raised blade about the rig's downwind wheels."""
    q = 0.5 * 1.2 * wind * wind
    area = L_BLADE * CHORD * 0.55                                       # the blade's side area (tapering)
    f = q * area * 1.2
    h = ROOT_H + 0.45 * L_BLADE * math.sin(a)
    return f * h


def blade_physics() -> dict:
    problems = []
    ts = np.arange(0.0, 35.0, 0.5)                                    # the story: through both bends
    worst_flat, worst_flat_gap, worst_lift, worst_lift_gap = 0.0, 99.0, 0.0, 99.0
    for t in ts:
        s = s_of(t)
        off, gap = clearance(s, "flat")
        worst_flat = max(worst_flat, off)
        worst_flat_gap = min(worst_flat_gap, gap)
        off2, gap2 = clearance(s, "lifted")
        worst_lift = max(worst_lift, off2)
        worst_lift_gap = min(worst_lift_gap, gap2)
    if not worst_flat_gap < 0:
        problems.append("a blade lying flat would not run into anything in these bends")
    if not worst_lift_gap > 1.0:
        problems.append(f"the lifted blade passes only {worst_lift_gap:.1f} m over the cliffs and trees")
    if abs(math.cos(ALPHA_MAX) - 0.5) > 1e-9:
        problems.append("at the top tilt the blade does not stick out half as far")
    if not 0.85 * FOOTBALL_FT <= L_BLADE / FT < FOOTBALL_FT:
        problems.append(f"the blade is {L_BLADE / FT:.0f} ft (narration: almost a football field)")
    if not 11.5 <= V / MPH <= 13.0:
        problems.append(f"the truck goes {V / MPH:.1f} mph (narration: about twelve)")
    if not 20.0 <= WIND_LIMIT / MPH <= 25.0:
        problems.append(f"the wind limit is {WIND_LIMIT / MPH:.0f} mph (narration: over twenty)")
    keep = RIG_MASS * 9.81 * HALF_TRACK
    m_lim = wind_moment(ALPHA_MAX, WIND_LIMIT)
    if not m_lim < keep:
        problems.append("the rig would tip in the wind it is allowed to drive in")
    m_gust = wind_moment(ALPHA_MAX, 2.2 * WIND_LIMIT)
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "blade_m": L_BLADE, "blade_ft": round(L_BLADE / FT),
            "tilt_max_deg": 60, "swing_max_deg": 20, "flat_overhang_m": round(worst_flat, 1), "flat_lowest_gap_m": round(worst_flat_gap, 1),
            "lifted_overhang_m": round(worst_lift, 1), "lifted_lowest_gap_m": round(worst_lift_gap, 1), "speed_mph": round(V / MPH, 1),
            "wind_limit_mph": round(WIND_LIMIT / MPH, 1), "tip_height_m": round(ROOT_H + L_BLADE * math.sin(ALPHA_MAX), 1),
            "wind_moment_at_limit_share": round(m_lim / keep, 2), "wind_moment_double_gust_share": round(m_gust / keep, 2)}


if __name__ == "__main__":
    import json
    print(json.dumps(blade_physics(), indent=1))
