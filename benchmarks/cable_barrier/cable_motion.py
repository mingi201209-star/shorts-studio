"""EP.15 median cable barrier (pure Python + numpy): a car drifts across a grass median at 60 mph, 25 degrees off the road, into three
tensioned steel wire ropes on weak posts along the median's centre line (x = 0, running along y).

The ropes act on the car as a spring across the line (stiffness K chosen so the car pushes them out about D_MAX, eight feet) with
some damping; the posts in the deflected stretch fold over. Once the car's sideways motion is spent, the stretched ropes push it back
toward its own side, and it slides to a stop on the grass along the median. Rope shape: straight from the posts on either side to a
kink at the car's front corner. Simplified explanation model, not calibrated to any real barrier or crash test."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
MPH = 0.44704
FT = 0.3048
V0 = 60 * MPH
ANGLE = math.radians(25.0)
MASS = 1400.0
D_MAX = 2.4                                      # m of rope deflection (about 8 ft)
K = 0.38 * MASS * (V0 * math.sin(ANGLE)) ** 2 / D_MAX ** 2      # N/m across the line; tuned so that, with the damping and the car turning
DAMP = 0.30 * 2 * math.sqrt(K * MASS)                            # into the ropes, it pushes them out about D_MAX (eight feet)
MU_CONTACT = 0.35                                # longitudinal drag while the ropes rub along the car
MU_GRASS = 0.45
HALF_W = 0.8
NOSE = 1.926
TAIL = 2.065
TAPER = 13.0                                     # m from the kink to where a rope is still on its line
ROPE_Z = (0.53, 0.64, 0.76)
POST_SPACING = 3.0
POST_FOLD_DEPTH = 0.20                           # a post folds once its rope point is pushed this far
DT = 2e-4
T_END = 6.5


def heading_vec(psi: float) -> np.ndarray:
    return np.array([math.sin(psi), math.cos(psi)])


@lru_cache(maxsize=None)
def _run() -> tuple:
    """Rows of (t, cx, cy, vx, vy, psi, depth, contact) from first contact (t = 0, the car's front corner on the rope line)."""
    psi = ANGLE
    h = heading_vec(psi)
    right = np.array([math.cos(psi), -math.sin(psi)])
    corner0 = NOSE * h + HALF_W * right                      # front-right corner relative to the car centre
    c = -corner0 * 1.0                                       # place the corner at the line (x = 0) with y = 0
    c[1] = 0.0 - corner0[1]
    c[0] = 0.0 - corner0[0]
    v = V0 * h
    t, rows, stuck = 0.0, [], False
    max_depth = 0.0
    while t <= T_END:
        h = heading_vec(psi)
        right = np.array([math.cos(psi), -math.sin(psi)])
        corner = c + NOSE * h + HALF_W * right
        depth = max(0.0, corner[0])
        contact = depth > 0.0 and not stuck
        ax, ay = 0.0, 0.0
        sp = float(np.hypot(*v))
        if contact:
            ax = -(K * depth + DAMP * v[0]) / MASS
            if sp > 0.1:
                ay = -MU_CONTACT * G * v[1] / sp
        elif sp > 0.05:
            ax = -MU_GRASS * G * v[0] / sp
            ay = -MU_GRASS * G * v[1] / sp
        v = v + np.array([ax, ay]) * DT
        if sp < 0.05:
            v = np.zeros(2)
        if contact and v[0] < 0 and depth < 0.02:
            stuck = True                                      # back off the ropes: they are left behind
        c = c + v * DT
        if sp > 1.0:
            target = math.atan2(v[0], v[1])
            psi += (target - psi) * min(1.0, DT * 3.0)        # the car turns toward its travel direction (tyres scrubbing)
        max_depth = max(max_depth, depth)
        rows.append((t, c[0], c[1], v[0], v[1], psi, depth, contact))
        t += DT
    return tuple(rows)


SWERVE_START, SWERVE_END = -0.95, -0.35          # the car drives straight in its lane, then drifts off toward the median


def _swerve_psi(t: float) -> float:
    u = min(1.0, max(0.0, (t - SWERVE_START) / (SWERVE_END - SWERVE_START)))
    return ANGLE * u * u * (3 - 2 * u)


@lru_cache(maxsize=None)
def _approach() -> tuple:
    """Path before contact, integrated backward from the contact pose: rows of (t, cx, cy, psi) for t from 0 down to -8 s."""
    r0 = _run()[0]
    c = np.array([r0[1], r0[2]])
    rows, t, dt = [(0.0, c[0], c[1], ANGLE)], 0.0, 0.002
    while t > -8.0:
        psi = _swerve_psi(t)
        c = c - V0 * heading_vec(psi) * dt
        t -= dt
        rows.append((t, c[0], c[1], _swerve_psi(t)))
    return tuple(rows)


def state(t: float) -> dict:
    """Car centre, velocity, heading at t seconds after first contact (negative = before: straight in its lane, then the drift)."""
    rows = _run()
    if t < 0:
        ap = _approach()
        i = min(len(ap) - 1, int(round(-t / 0.002)))
        _, cx, cy, psi = ap[i]
        v = V0 * heading_vec(psi)
        return {"t": t, "cx": cx, "cy": cy, "vx": float(v[0]), "vy": float(v[1]), "psi": psi, "depth": 0.0, "contact": False, "kink_y": None}
    i = min(len(rows) - 1, int(round(t / DT)))
    _, cx, cy, vx, vy, psi, d, ct = rows[i]
    h = heading_vec(psi)
    right = np.array([math.cos(psi), -math.sin(psi)])
    corner = np.array([cx, cy]) + NOSE * h + HALF_W * right
    return {"t": t, "cx": cx, "cy": cy, "vx": vx, "vy": vy, "psi": psi, "depth": d, "contact": ct, "kink_y": float(corner[1]), "kink_x": float(corner[0])}


@lru_cache(maxsize=None)
def _peak() -> tuple:
    rows = _run()
    i = max(range(len(rows)), key=lambda k: rows[k][6])
    return rows[i][0], rows[i][6], rows[i][2]


def rope_offset(y: np.ndarray, t: float) -> np.ndarray:
    """x of the rope line at y (all three ropes share the shape). Straight before contact; a V with its kink at the car's front corner
    while it pushes; afterwards it springs back."""
    y = np.asarray(y, float)
    st = state(t)
    if st["kink_y"] is None:
        return np.zeros_like(y)
    if st["contact"]:
        d, yk = st["depth"], st["kink_y"]
    else:
        tp, dp, _ = _peak()
        if t < tp:
            return np.zeros_like(y)
        rows = _run()
        tr = next((r[0] for r in rows if r[0] > tp and not r[7]), tp)
        d = _peak()[1] * math.exp(-max(0.0, t - tr) / 0.08) * (0.25 if t > tr else 1.0)
        yk = _peak()[2]
    return d * np.clip(1 - np.abs(y - yk) / TAPER, 0, 1)


def post_ys() -> np.ndarray:
    return np.arange(-30.0, 60.0, POST_SPACING)


@lru_cache(maxsize=None)
def post_fold_times() -> tuple:
    ys = post_ys()
    out = []
    for y in ys:
        tf = None
        for k in range(0, int(1.2 / 0.002)):
            t = k * 0.002
            if rope_offset(np.array([y]), t)[0] > POST_FOLD_DEPTH:
                tf = t
                break
        out.append(tf)
    return tuple(out)


def post_angle(i: int, t: float) -> float:
    tf = post_fold_times()[i]
    if tf is None or t < tf:
        return 0.0
    return math.radians(80) * (1 - math.exp(-(t - tf) / 0.05))


ONCOMING_X = 10.0                                 # oncoming car's lane centre on the far side of the median (model x)
ONCOMING_Y0 = 12.0                                # where it is at t = -0.35 s: it passes the impact point as the ropes catch the car


def oncoming_y(t: float) -> float:
    return ONCOMING_Y0 - V0 * (t + 0.35)


def cable_physics() -> dict:
    problems = []
    tp, dp, _ = _peak()
    if abs(dp / FT - 8) > 0.8:
        problems.append(f"peak rope deflection {dp / FT:.1f} ft (narration: about eight feet)")
    rows = _run()
    final = rows[-1]
    if final[1] > 0.5:
        problems.append("the car ends up across the line, toward the other lanes")
    if not any(r[3] < 0 for r in rows):
        problems.append("the ropes never push the car back toward its own side")
    folded = sum(1 for f in post_fold_times() if f is not None)
    if folded < 4:
        problems.append(f"only {folded} posts fold")
    peak_g = max(abs(K * r[6] + DAMP * r[3]) / MASS / G for r in rows if r[7])
    if peak_g > 8:
        problems.append(f"peak deceleration {peak_g:.1f} g is not gentle")
    lane_x = state(-3.0)["cx"]
    if not -10.5 < lane_x < -6.5:
        problems.append(f"before the drift the car is not in its lane (x {lane_x:.1f})")
    stop = next((r[0] for r in rows if abs(r[3]) < 1e-6 and abs(r[4]) < 1e-6), None)
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "peak_deflection_ft": round(dp / FT, 2), "peak_at_s": round(tp, 3),
            "peak_g": round(peak_g, 1), "posts_folded": folded, "final_x": round(final[1], 2), "final_y": round(final[2], 2),
            "stopped_at_s": None if stop is None else round(stop, 2), "K_kN_per_m": round(K / 1000, 1)}


if __name__ == "__main__":
    import json
    print(json.dumps(cable_physics(), indent=1))
