"""EP.30 swivel bridge (pure Python + numpy): a road bridge built beside a busy railway and turned into place over it (the Baoding
bridge of 2019: about 46,000 t, 263.6 m long, turned 52.4 degrees in 68 minutes over the Beijing-Guangzhou Railway inside a
110-minute window with no trains; reported with a spherical hinge 6.5 m across). Render-world frame: the railway runs along +x at
y = 0 (four tracks, y = -7.5..7.5), the pier stands at (0, -22) south of the tracks, z = 0 is the rail level; the deck is a T balanced
on the pier, built at heading HEAD0 (parallel to the tracks) and turned to HEAD0 + 52.4 degrees, across them.

The turn: a smooth start and stop (RAMP_S each), cruising in between, 52.4 degrees in 68 minutes. The hinge: the whole weight on one
greased spherical joint; the pull that turns it is estimated from a friction coefficient (static to start, sliding once moving) on
the joint's area; the model's figure, not a published one. The gate checks the claims in the film: the weight, almost 900 ft, the
angle and the time, about eight times slower than a clock's minute hand, inside the window, the deck high enough over the overhead
wires once turned, and nothing over the tracks before the turn. Simplified explanation model, not the builders' figures."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

FT = 0.3048
G = 9.81
MASS_T = 46000.0
LENGTH = 263.6
HALF = LENGTH / 2
DECK_W = 24.0
DECK_TOP = 16.5                          # road surface above the rails
DEPTH_PIER, DEPTH_END = 6.5, 3.0         # box girder depth at the pier and at the ends (haunched)
PIER = (0.0, -22.0)
HINGE_D = 6.5
TRACKS_Y = (-5.0, -1.7, 1.7, 5.0)
WIRE_Z = 7.0                             # overhead contact wires above the rails
HEAD0 = math.radians(90.0)               # heading of the deck when built: along +x (clockwise from +y), parallel to the tracks
TURN = math.radians(52.4)
T_TURN = 68.0 * 60.0
RAMP_S = 240.0
WINDOW = (-15.0 * 60.0, 95.0 * 60.0)     # the railway's 110-minute window with no trains
MU_STATIC, MU_SLIDE = 0.08, 0.05         # greased PTFE on steel: to start, and once it slides (the model's values)
PULL_R = 6.0                             # where the pulling force acts on the turntable


@lru_cache(maxsize=None)
def _profile():
    dt = 1.0
    ts = np.arange(0.0, T_TURN + dt, dt)

    def s(a):
        a = np.clip(a, 0.0, 1.0)
        return a * a * (3 - 2 * a)
    w = s(ts / RAMP_S) * s((T_TURN - ts) / RAMP_S)
    ang = np.concatenate([[0.0], np.cumsum(0.5 * (w[1:] + w[:-1]) * dt)])
    ang *= TURN / ang[-1]
    return ts, ang


def turned(t: float) -> float:
    """How far the bridge has turned (radians) at time t (s from the start of the turn)."""
    if t <= 0:
        return 0.0
    if t >= T_TURN:
        return TURN
    ts, ang = _profile()
    return float(np.interp(t, ts, ang))


def heading(t: float) -> float:
    return HEAD0 + turned(t)


def deck_ends(t: float) -> tuple[np.ndarray, np.ndarray]:
    h = heading(t)
    u = np.array([math.sin(h), math.cos(h)])
    p = np.array(PIER)
    return p - HALF * u, p + HALF * u


def over_tracks(t: float) -> bool:
    """Does any part of the deck's outline lie over the tracks?"""
    h = heading(t)
    u = np.array([math.sin(h), math.cos(h)])
    n = np.array([math.cos(h), -math.sin(h)])
    p = np.array(PIER)
    for a in np.linspace(-HALF, HALF, 400):
        for b in (-DECK_W / 2, DECK_W / 2):
            q = p + a * u + b * n
            if -7.5 <= q[1] <= 7.5:
                return True
    return False


def deck_bottom_z(a: float) -> float:
    """Underside height of the deck at distance a from the pier along it."""
    w = min(1.0, abs(a) / HALF)
    depth = DEPTH_END + (DEPTH_PIER - DEPTH_END) * (1 - w) ** 2
    return DECK_TOP - depth


def clearance_over_wires() -> float:
    """Lowest gap between the turned deck and the overhead wires above the tracks."""
    h = heading(T_TURN + 1)
    u = np.array([math.sin(h), math.cos(h)])
    p = np.array(PIER)
    gaps = []
    for a in np.linspace(-HALF, HALF, 2000):
        q = p + a * u
        if -7.5 <= q[1] <= 7.5:
            gaps.append(deck_bottom_z(a) - WIRE_Z)
    return min(gaps)


def pull_force(static: bool) -> float:
    """Force (N) to turn the bridge on its hinge: friction over a circular joint of diameter HINGE_D (moment 2/3 mu W R)."""
    w = MASS_T * 1000.0 * G
    mu = MU_STATIC if static else MU_SLIDE
    moment = 2.0 / 3.0 * mu * w * HINGE_D / 2
    return moment / PULL_R


def swivel_physics() -> dict:
    problems = []
    if abs(math.degrees(TURN) - 52.4) > 1e-9 or abs(T_TURN - 68 * 60) > 1e-9:
        problems.append("the turn is not 52.4 degrees in 68 minutes")
    rate = math.degrees(TURN) / (T_TURN / 60.0)
    times = 6.0 / rate
    if not 7.0 <= times <= 9.0:
        problems.append(f"the minute hand is {times:.1f} times faster (narration: about eight)")
    if not 850.0 <= LENGTH / FT < 900.0:
        problems.append(f"the bridge is {LENGTH / FT:.0f} ft (narration: almost nine hundred)")
    if not WINDOW[0] < 0 and T_TURN < WINDOW[1] and WINDOW[1] - WINDOW[0] < 120 * 60:
        problems.append("the turn does not fit the railway's window of under two hours")
    if over_tracks(-1.0):
        problems.append("the bridge stands over the tracks before it is turned")
    if not over_tracks(T_TURN + 1.0):
        problems.append("the turned bridge does not cross the tracks")
    gap = clearance_over_wires()
    if gap < 1.0:
        problems.append(f"only {gap:.2f} m between the turned deck and the overhead wires")
    w = MASS_T * 1000.0 * G
    f_start, f_slide = pull_force(True), pull_force(False)
    tip = HALF * TURN / (T_TURN / 60.0)
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "mass_t": MASS_T, "length_m": LENGTH, "length_ft": round(LENGTH / FT),
            "turn_deg": 52.4, "turn_min": 68, "deg_per_min": round(rate, 3), "minute_hand_times_faster": round(times, 1),
            "window_min": round((WINDOW[1] - WINDOW[0]) / 60), "tip_m_per_min": round(tip, 2), "wire_clearance_m": round(gap, 2),
            "hinge_ft": round(HINGE_D / FT, 1), "pull_start_share_of_weight": round(f_start / w, 4), "pull_slide_share_of_weight": round(f_slide / w, 4)}


if __name__ == "__main__":
    import json
    print(json.dumps(swivel_physics(), indent=1))
