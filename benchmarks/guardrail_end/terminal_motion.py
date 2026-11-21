"""EP.13 guardrail end terminal (pure Python + numpy, no Blender): a 1,400 kg car at 60 mph hits the end of a W-beam guardrail head-on.

Energy-absorbing terminal: a steel head on the rail end is pushed down the rail by the car. The rail runs into the head, is squeezed flat
and bent out of a side slot as a ribbon that coils away from the car. The force needed to flatten and bend the steel is the force that
slows the car (built up over RAMP_M, then constant), so the car stops over STOP_M. The first posts are breakaway posts: each one snaps when
the head reaches it. Blunt end (the old design, the counterfactual): the bare rail end meets the car's front corner and goes through it;
the car stops over SPEAR_M of penetration, which is past the front of the cabin (CABIN_FROM_NOSE).

Also the geometry the renderer and the tests share: the W-beam profile, the ribbon path in the head frame (throat -> flattening bend ->
side exit -> loosening coil; its curvature falls monotonically, so by the Tait-Kneser theorem the coil never crosses itself), and the
deterministic sparks. Simplified explanation model, not calibrated to any real terminal or crash test."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
MPH = 0.44704
V0 = 60 * MPH                      # 26.8 m/s
MASS = 1400.0
CAR_LEN = 3.99                     # CC0 sedan nose 1.926 + tail 2.065
STOP_M = 9.0                       # head travel to a stop (about two car lengths)
RAMP_M = 0.25                      # the extrusion force builds up over this travel (head and first post)
F_EXTRUDE = 0.5 * MASS * V0 ** 2 / (STOP_M - RAMP_M / 2)
CRUSH_MAX = 0.12                   # local dent of the car's nose against the head plate
CRUSH_IN_M = 0.15
SPEAR_M = 2.3                      # blunt end: how far the rail goes into the car before it stops
CABIN_FROM_NOSE = 0.95             # nose structure ahead of the passenger cell (EP.04 crush length)
DT = 2e-4

# layout (world): road along +y, the car drives +y; rail face line x = RAIL_X (traffic on -x), rail centre height RAIL_Z
RAIL_X = 0.0
RAIL_Z = 0.55
CAR_X = -0.58                      # car centre line: the head meets the car's right front corner
Y0 = 0.0                           # head front face at rest (terminal site)
HEAD_L = 0.62                      # head length along the rail
HEAD_X = 0.06                      # head centre x
POST_SPACING = 1.905
POST_X = 0.27                      # post centre x (behind the blockout)
N_POSTS = 14
BREAK_LEAD = 0.30                  # a post snaps when the head front is this close to it
Y_SPEAR = 400.0                    # blunt-end site (rail starts here), far from the terminal site

# W-beam: 0.31 m tall, two corrugations 0.083 m deep facing traffic (-x)
BEAM_H = 0.312
BEAM_DEPTH = 0.083
STRIP_H = 0.46                     # height of the flattened strip


def _trap(y: np.ndarray, x: np.ndarray) -> float:
    """Trapezoid rule (Blender's bundled numpy has no np.trapezoid, newer numpy drops np.trapz)."""
    return float(np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(x)))


def w_profile(v: np.ndarray) -> np.ndarray:
    """Depth of the W-beam toward traffic at height v (m, -BEAM_H/2..BEAM_H/2): zero at the edges and the middle, full at the two peaks."""
    return 0.5 * BEAM_DEPTH * (1 - np.cos(4 * np.pi * (v + BEAM_H / 2) / BEAM_H))


# ------------------------------------------------------------------ crash motion
@lru_cache(maxsize=None)
def _terminal() -> tuple:
    x, v, t, rows = 0.0, V0, 0.0, [(0.0, 0.0, V0, 0.0)]
    while v > 0:
        f = F_EXTRUDE * min(1.0, x / RAMP_M)
        a = f / MASS
        v = max(0.0, v - a * DT)
        x += v * DT
        t += DT
        rows.append((t, x, v, a / G))
    return tuple(rows)


@lru_cache(maxsize=None)
def _spear() -> tuple:
    a = V0 ** 2 / (2 * SPEAR_M)
    x, v, t, rows = 0.0, V0, 0.0, [(0.0, 0.0, V0, 0.0)]
    while v > 0:
        v = max(0.0, v - a * DT)
        x += v * DT
        t += DT
        rows.append((t, x, v, a / G))
    return tuple(rows)


def stop_time(kind: str = "terminal") -> float:
    return (_terminal() if kind == "terminal" else _spear())[-1][0]


def _sample(rows, t):
    if t >= rows[-1][0]:
        r = rows[-1]
        return r[1], 0.0, 0.0
    i = int(t / DT)
    r0, r1 = rows[i], rows[min(i + 1, len(rows) - 1)]
    u = (t - r0[0]) / DT
    return r0[1] + (r1[1] - r0[1]) * u, r0[2] + (r1[2] - r0[2]) * u, r0[3]


def terminal_state(t: float) -> dict:
    """t = seconds after the car touches the head (negative = approaching at V0). x = how far the car (cabin) has moved past the contact
    position; crush = dent of the nose; head_d = how far the head has been pushed down the rail."""
    if t < 0:
        return {"t": t, "x": V0 * t, "v": V0, "g": 0.0, "crush": 0.0, "head_d": 0.0, "contact": False}
    x, v, g = _sample(_terminal(), t)
    crush = CRUSH_MAX * min(1.0, x / CRUSH_IN_M)
    return {"t": t, "x": x, "v": v, "g": g, "crush": crush, "head_d": max(0.0, x - crush), "contact": True}


def spear_state(t: float) -> dict:
    """Blunt end: p = how far the rail end is inside the car, measured from the front of the car."""
    if t < 0:
        return {"t": t, "x": V0 * t, "v": V0, "p": 0.0, "contact": False}
    x, v, g = _sample(_spear(), t)
    return {"t": t, "x": x, "v": v, "p": x, "g": g, "contact": True}


def post_y(k: int) -> float:
    return Y0 + 0.30 + k * POST_SPACING


@lru_cache(maxsize=None)
def post_break_times() -> tuple:
    """Simulated time at which each post snaps (None if the head never reaches it)."""
    rows = _terminal()
    out = []
    for k in range(N_POSTS):
        need = post_y(k) - BREAK_LEAD
        tk = None
        for r in rows:
            crush = CRUSH_MAX * min(1.0, r[1] / CRUSH_IN_M)
            if Y0 + r[1] - crush >= need:
                tk = r[0]
                break
        out.append(tk)
    return tuple(out)


def post_fall(k: int, t: float) -> tuple[float, float]:
    """Post k after it snaps: (tilt away from the road, rad; sideways kick, m). Struck at about 26 m/s it is knocked over fast (time
    constant 18 ms) and thrown a little away from the road, so it clears the head."""
    tk = post_break_times()[k]
    if tk is None or t < tk:
        return 0.0, 0.0
    tau = t - tk
    return math.radians(84) * (1 - math.exp(-tau / 0.018)), 0.35 * (1 - math.exp(-tau / 0.02))


# ------------------------------------------------------------------ ribbon (head frame: origin at the head front face centre, rail height)
L_IN = 0.36                         # straight run inside the head, from the throat at the back
R_BEND = 0.13                       # flattening bend toward the side slot
L_OUT = 1.60                        # straight lead-out: the coil forms clear of the posts still standing ahead of the head
R0, BETA = 0.34, 0.10               # coil: radius R0 at the start, loosening by BETA per metre (an open spiral, like a party blower)
S_BEND = L_IN + 0.5 * math.pi * R_BEND
S_COIL = S_BEND + L_OUT
S_REST = S_BEND + 0.12              # material already past the throat before the hit (ends just inside the side slot)
THROAT = np.array([RAIL_X - HEAD_X, HEAD_L, 0.0])


def ribbon_path(s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Centre line (N, 3) and heading angle (N,) of the strip at path length s from the throat. Heading 0 = +x; inside the head the strip
    runs toward -y (heading -pi/2), bends to +x, leads out, then coils counter-clockwise with radius growing from R0."""
    s = np.asarray(s, float)
    pts = np.zeros((len(s), 3))
    hd = np.zeros(len(s))
    for i, si in enumerate(s):
        if si <= L_IN:
            p, h = THROAT + np.array([0.0, -si, 0.0]), -0.5 * math.pi
        elif si <= S_BEND:
            a = (si - L_IN) / R_BEND                       # turned angle
            c = THROAT + np.array([R_BEND, -L_IN, 0.0])     # bend centre
            p = c + np.array([-R_BEND * math.cos(a), -R_BEND * math.sin(a), 0.0])
            h = -0.5 * math.pi + a
        elif si <= S_COIL:
            e = THROAT + np.array([R_BEND, -L_IN - R_BEND, 0.0])
            p, h = e + np.array([si - S_BEND, 0.0, 0.0]), 0.0
        else:
            u = si - S_COIL
            start = THROAT + np.array([R_BEND + L_OUT, -L_IN - R_BEND, 0.0])
            # heading grows by the integral of 1/(R0 + BETA u); position by integrating the heading numerically
            n = max(2, int(u / 0.02) + 2)
            us = np.linspace(0.0, u, n)
            hs = np.log((R0 + BETA * us) / R0) / BETA
            dx = _trap(np.cos(hs), us)
            dy = _trap(np.sin(hs), us)
            droop = 0.22 * u / (u + 3.0)
            p, h = start + np.array([dx, dy, -droop]), hs[-1]
        pts[i], hd[i] = p, h
    return pts, hd


def ribbon_length(head_d: float) -> float:
    return S_REST + head_d


def flatten(s: np.ndarray) -> np.ndarray:
    """1 inside the straight run (full W-beam), falling to 0.12 through the bend (a little waviness stays)."""
    s = np.asarray(s, float)
    u = np.clip((s - L_IN) / (S_BEND - L_IN), 0.0, 1.0)
    return 1.0 - 0.88 * u * u * (3 - 2 * u)


def ribbon_mesh(head_d: float, ds: float = 0.03, nv: int = 13) -> tuple[np.ndarray, list]:
    """Vertices (head frame) and quad faces of the strip from the throat to its free end."""
    L = ribbon_length(head_d)
    n = max(2, int(math.ceil(L / ds)) + 1)
    s = np.linspace(0.0, L, n)
    c, h = ribbon_path(s)
    k = flatten(s)
    v = np.linspace(-0.5, 0.5, nv)
    verts = np.zeros((n, nv, 3))
    for i in range(n):
        height = BEAM_H + (STRIP_H - BEAM_H) * (1 - k[i])
        vv = v * height
        depth = k[i] * w_profile(v * BEAM_H)                     # corrugation (toward the traffic side of the strip)
        nrm = np.array([math.sin(h[i]), -math.cos(h[i]), 0.0])   # left normal of the heading; inside the head it points to -x (traffic)
        verts[i, :, :] = c[i] + np.outer(depth, nrm) + np.outer(vv, [0.0, 0.0, 1.0])
    faces = [(i * nv + j, i * nv + j + 1, (i + 1) * nv + j + 1, (i + 1) * nv + j) for i in range(n - 1) for j in range(nv - 1)]
    return verts.reshape(-1, 3), faces


def ribbon_min_clearance(head_d: float) -> float:
    """Smallest distance between strip centre-line points more than 1.5 m apart along the path (self-contact check)."""
    L = ribbon_length(head_d)
    s = np.arange(S_COIL, L, 0.05)
    if len(s) < 3:
        return float("inf")
    c, _ = ribbon_path(s)
    best = float("inf")
    for i in range(len(s)):
        far = np.abs(s - s[i]) > 1.5
        if far.any():
            best = min(best, float(np.min(np.linalg.norm(c[far][:, :2] - c[i, :2], axis=1))))
    return best


# ------------------------------------------------------------------ sparks (deterministic)
@lru_cache(maxsize=None)
def sparks() -> tuple:
    """(birth time, birth point in world, velocity, life) for every spark thrown from the side slot and the throat while the head moves."""
    rng = np.random.default_rng(13)
    out = []
    t, t_end = 0.004, stop_time()
    while t < t_end:
        st = terminal_state(t)
        rate = 650.0 * st["v"] / V0
        hy = Y0 + st["head_d"]
        if rng.random() < 0.7:
            p = np.array([HEAD_X + 0.20, hy + 0.18, RAIL_Z + rng.uniform(-0.15, 0.15)])
            vel = np.array([rng.uniform(1.5, 6.0), rng.uniform(-3.0, 4.0) + 0.5 * st["v"], rng.uniform(0.5, 5.0)])
        else:
            p = np.array([RAIL_X, hy + HEAD_L, RAIL_Z + rng.uniform(-0.12, 0.12)])
            vel = np.array([rng.uniform(-2.5, 2.5), rng.uniform(2.0, 6.0) + 0.7 * st["v"], rng.uniform(0.5, 4.0)])
        out.append((t, tuple(p), tuple(vel), float(rng.uniform(0.12, 0.38))))
        t += 1.0 / max(rate, 60.0)
    return tuple(out)


def spark_points(t: float) -> list[tuple[np.ndarray, np.ndarray]]:
    pts = []
    for tb, p, vel, life in sparks():
        tau = t - tb
        if 0 <= tau <= life:
            p, vel = np.array(p), np.array(vel)
            pos = p + vel * tau + np.array([0.0, 0.0, -0.5 * G * tau * tau])
            if pos[2] < 0.01:
                continue
            pts.append((pos, vel + np.array([0.0, 0.0, -G * tau])))
    return pts


# ------------------------------------------------------------------ gate
def terminal_physics() -> dict:
    problems = []
    stop = _terminal()[-1][1]
    head_stop = stop - CRUSH_MAX
    if not 1.8 <= head_stop / CAR_LEN <= 2.6:
        problems.append(f"the car stops over {head_stop:.1f} m = {head_stop / CAR_LEN:.1f} car lengths (narration: about two)")
    avg_g = V0 ** 2 / (2 * stop) / G
    if CRUSH_MAX >= CABIN_FROM_NOSE:
        problems.append("the terminal case crushes into the cabin")
    if SPEAR_M <= CABIN_FROM_NOSE + 0.5:
        problems.append("the blunt rail end does not reach into the cabin")
    broken = [k for k, tk in enumerate(post_break_times()) if tk is not None]
    if len(broken) < 3:
        problems.append("fewer than three posts snap")
    clear = ribbon_min_clearance(head_stop)
    if clear < 0.06:
        problems.append(f"the ribbon coil touches itself ({clear:.3f} m)")
    c, _ = ribbon_path(np.arange(S_COIL, ribbon_length(head_stop), 0.05))
    if np.min(c[:, 0] + HEAD_X) < POST_X + STRIP_H / 2:
        problems.append("the ribbon coil swings back into the posts and the rail")
    if np.min(c[:, 2] + RAIL_Z) < STRIP_H / 2:
        problems.append("the ribbon goes into the ground")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "stop_m": round(stop, 2), "car_lengths": round(head_stop / CAR_LEN, 2),
            "stop_s": round(stop_time(), 3), "avg_g": round(avg_g, 2), "force_kN": round(F_EXTRUDE / 1000, 1), "spear_stop_s": round(stop_time("spear"), 3),
            "posts_snapped": len(broken), "sparks": len(sparks()), "ribbon_m": round(ribbon_length(head_stop), 2), "ribbon_clearance_m": round(clear, 3)}


if __name__ == "__main__":
    import json
    print(json.dumps(terminal_physics(), indent=1))
