"""EP.16 tyre blowout (pure Python + numpy). Render-world coordinates: the highway runs along +y, the red car drives in the left lane
(x = X_LANE) at 60 mph; its front-left tyre is about 30 % under-inflated (24 psi on a 35 psi tyre).

Explanation model, not calibrated to a real tyre:
- vertical stiffness grows with pressure, k = K0 + KP * p, so a low tyre deflects (bends its sidewall) more at the bottom;
- each turn bends the sidewall once: at 60 mph a 0.281 m tyre turns about 15 times a second;
- the energy lost in each bend (hysteresis) grows with the deflection squared, so the low tyre runs hotter;
- the bond between the steel belts and the rubber ages faster with heat (rate doubling every DOUBLING_C degrees), so the low tyre's
  belts separate in a small fraction of the normal life; then the tread peels and the carcass bursts;
- a tyre loses about 1 psi a month through the rubber (35 -> 24 psi in 11 months).
Simulated time t: seconds after the burst (negative = before). Debris pieces fly ballistically, bounce once and slide to a stop."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
MPH = 0.44704
V0 = 60 * MPH
R = 0.281                       # CC0 car tyre radius (m)
RIM_R = 0.19
W = 0.205                       # section width
MASS = 1400.0
LOAD = MASS * G / 4
K0, KP = 30e3, 5e3              # N/m and N/m per psi
P_SPEC, P_LOW = 35.0, 24.0
LEAK_PSI_PER_MONTH = 1.0
T_AMB = 25.0
RISE_SPEC = 25.0                # deg C above ambient at the right pressure, on the highway
DOUBLING_C = 5.0
LIFE_SPEC_H = 2000.0            # highway hours before the belt bond fails at the right pressure (order of a tyre's life)
X_LANE = -1.85
VIS_GAIN = 2.0                  # the sidewall bend is drawn twice as deep as the model's, so it reads on a phone
PEEL_START = -0.5               # the tread starts to peel half a second before the burst
TRIP_START = -1800.0            # the trip starts 30 min before the burst: the tyre warms up
HEAT_TAU = 400.0
A_DEC = 0.30 * G                # braking after the burst
PULL_M = 0.6                    # the car pulls about 0.6 m toward the blown tyre (left); the driver holds it
N_DEBRIS = 70


def deflection(p: float) -> float:
    return LOAD / (K0 + KP * p)


def revs_per_second(v: float = V0) -> float:
    return v / (2 * math.pi * R)


def temp_eq(p: float) -> float:
    return T_AMB + RISE_SPEC * (deflection(p) / deflection(P_SPEC)) ** 2


def bond_life_hours(p: float) -> float:
    return LIFE_SPEC_H * 2 ** (-(temp_eq(p) - temp_eq(P_SPEC)) / DOUBLING_C)


def pressure_after(months: float) -> float:
    return P_SPEC - LEAK_PSI_PER_MONTH * months


def temperature(t: float) -> float:
    """Inside the low tyre on this trip (deg C)."""
    if t <= TRIP_START:
        return T_AMB
    return T_AMB + (temp_eq(P_LOW) - T_AMB) * (1 - math.exp(-(t - TRIP_START) / HEAT_TAU))


def pressure(t: float) -> float:
    return P_LOW if t < 0 else P_LOW * math.exp(-t / 0.02)


def squash(t: float) -> float:
    """Drawn deflection of the front-left tyre at the bottom (m)."""
    pre = VIS_GAIN * deflection(P_LOW)
    if t < 0:
        return pre
    flat = R - RIM_R - 0.025
    return pre + (flat - pre) * (1 - math.exp(-t / 0.03))


def corner_drop(t: float) -> float:
    return 0.0 if t < 0 else (squash(t) - squash(-1.0)) * 0.9


def peel(t: float) -> tuple[float, float]:
    """(fraction of the circumference with the tread lifted, lift in m) while it peels; the strip is gone after the burst."""
    if t < PEEL_START or t >= 0:
        return 0.0, 0.0
    u = (t - PEEL_START) / -PEEL_START
    return 0.08 + 0.5 * u, 0.025 + 0.10 * u * u


def separation(t: float) -> float:
    """Gap opening between the belts and the tread, before it peels (m), for the cut-away shots."""
    return 0.010 * min(1.0, max(0.0, (t + 3.0) / 2.5))


@lru_cache(maxsize=None)
def _path() -> tuple[np.ndarray, ...]:
    dt = 0.002
    ts = np.arange(0.0, 8.0 + dt, dt)
    v = np.maximum(V0 - A_DEC * ts, 8.0)
    y = np.concatenate([[0.0], np.cumsum(v[:-1] * dt)])
    x = X_LANE - PULL_M * (ts / 0.9) ** 2 * np.exp(2 * (1 - ts / 0.9))   # pulled toward the blown side, then held back into the lane
    psi = np.arctan2(-np.gradient(x, y), 1.0)                            # heading follows the path
    return ts, x, y, psi, v


def state(t: float) -> dict:
    """Car centre, heading, speed, distance rolled and the front-left tyre's state at simulated time t."""
    if t < 0:
        x, y, psi, v, dist = X_LANE, V0 * t, 0.0, V0, V0 * t
    else:
        ts, xs, ys, ps, vs = _path()
        x, y, psi, v = (float(np.interp(t, ts, a)) for a in (xs, ys, ps, vs))
        dist = y
    span, lift = peel(t)
    return {"t": t, "x": x, "y": y, "psi": psi, "v": v, "dist": dist, "pressure": pressure(t), "squash": squash(t), "drop": corner_drop(t),
            "peel_span": span, "peel_lift": lift, "temp": temperature(t), "sep": separation(t), "burst": t >= 0}


WHEEL_OFFSET = (-0.72, 1.08)     # front-left wheel centre from the car centre (car frame: x right, y forward); checked by the renderer


def wheel_world(t: float) -> np.ndarray:
    s = state(t)
    c, sn = math.cos(s["psi"]), math.sin(s["psi"])
    ox, oy = WHEEL_OFFSET
    return np.array([s["x"] + ox * c - oy * sn, s["y"] + ox * sn + oy * c, R - s["drop"]])


@lru_cache(maxsize=None)
def debris() -> tuple:
    """Rubber pieces torn off at the burst: (spawn time, start position, velocity, size (l, w, h), spin, kind)."""
    rng = np.random.default_rng(1616)
    out = []
    for k in range(N_DEBRIS):
        tb = 0.0 if k == 0 else float(rng.uniform(0.0, 0.10))
        wc = wheel_world(tb)
        a = rng.uniform(-0.3, 2.2)                              # angle around the wheel from the top, toward the rear
        pos = wc + np.array([rng.uniform(-0.12, -0.08), -R * math.sin(a), R * math.cos(a)])      # from the outer face, outside the body
        pos[2] = max(pos[2], 0.05)
        s = state(tb)
        fwd = s["v"] * rng.uniform(0.35, 0.85)
        vel = np.array([-rng.uniform(1.0, 5.0), fwd, rng.uniform(2.5, 6.0)])
        if k == 0:
            size, vel = (0.75, 0.17, 0.014), np.array([-3.0, s["v"] * 0.55, 3.2])     # the tread strip
        else:
            size = (rng.uniform(0.06, 0.22), rng.uniform(0.04, 0.12), rng.uniform(0.010, 0.02))
        out.append((tb, pos, vel, size, rng.uniform(-14, 14, 3), "strip" if k == 0 else "chunk"))
    return tuple(out)


SLIDE_DEC = 7.0
RESTITUTION = 0.3


def debris_pose(k: int, t: float) -> tuple[np.ndarray, np.ndarray, bool] | None:
    """Position, rotation (euler) and airborne flag of piece k at time t; None before it is torn off."""
    tb, p0, v0, size, spin, _ = debris()[k]
    tau = t - tb
    if tau < 0:
        return None
    h0 = size[2] / 2
    vz, z0 = v0[2], p0[2] - h0
    t1 = (vz + math.sqrt(vz * vz + 2 * G * z0)) / G               # first landing
    if tau <= t1:
        p = p0 + v0 * tau + np.array([0, 0, -0.5 * G * tau * tau])
        return p, spin * tau, True
    p1 = p0 + v0 * t1 + np.array([0, 0, -0.5 * G * t1 * t1])
    vh = v0[:2] * 0.6
    vz2 = (G * t1 - vz) * RESTITUTION
    t2 = 2 * vz2 / G
    if tau <= t1 + t2:
        d = tau - t1
        p = np.array([p1[0] + vh[0] * d, p1[1] + vh[1] * d, h0 + vz2 * d - 0.5 * G * d * d])
        return p, spin * (t1 + 0.5 * d), True
    p2 = np.array([p1[0] + vh[0] * t2, p1[1] + vh[1] * t2, h0])
    sp = float(np.hypot(*vh))
    d = tau - t1 - t2
    ts = sp / SLIDE_DEC
    d = min(d, ts)
    dist = sp * d - 0.5 * SLIDE_DEC * d * d
    dirn = vh / max(sp, 1e-9)
    rot = spin * (t1 + 0.5 * t2)
    rot = np.array([0.0, 0.0, rot[2]])                             # lying flat on the road
    return np.array([p2[0] + dirn[0] * dist, p2[1] + dirn[1] * dist, h0]), rot, False


def airborne_count(t: float) -> int:
    return sum(1 for k in range(N_DEBRIS) if (p := debris_pose(k, t)) is not None and p[2])


def blowout_physics() -> dict:
    problems = []
    rps = revs_per_second()
    if not 14.5 <= rps <= 15.5:
        problems.append(f"{rps:.1f} turns a second at 60 mph (narration: fifteen)")
    d_ratio = deflection(P_LOW) / deflection(P_SPEC)
    if d_ratio < 1.2:
        problems.append("the low tyre does not bend noticeably more")
    dT = temp_eq(P_LOW) - temp_eq(P_SPEC)
    if dT < 15:
        problems.append(f"the low tyre runs only {dT:.0f} C hotter")
    life_ratio = bond_life_hours(P_SPEC) / bond_life_hours(P_LOW)
    if life_ratio < 10:
        problems.append(f"heat shortens the belt bond's life only {life_ratio:.1f}x")
    months = (P_SPEC - P_LOW) / LEAK_PSI_PER_MONTH
    if abs(pressure_after(months) - P_LOW) > 1e-9 or not 6 <= months <= 14:
        problems.append("the leak rate does not take the tyre to its low pressure within a year")
    ts, xs, ys, ps, vs = _path()
    if abs(xs[-1] - X_LANE) > 1.2:
        problems.append(f"the car leaves its lane ({xs[-1] - X_LANE:+.2f} m)")
    for k in range(N_DEBRIS):
        for t in np.arange(0.0, 6.0, 0.01):
            p = debris_pose(k, float(t))
            if p is not None and p[0][2] < debris()[k][3][2] / 2 - 1e-6:
                problems.append(f"piece {k} goes into the road")
                break
    early = airborne_count(0.05)
    if early < 25:
        problems.append(f"only {early} pieces in the air in the opening")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "turns_per_s": round(rps, 2),
            "deflection_mm": {"35psi": round(1000 * deflection(P_SPEC), 1), "24psi": round(1000 * deflection(P_LOW), 1)},
            "temp_C": {"35psi": round(temp_eq(P_SPEC), 1), "24psi": round(temp_eq(P_LOW), 1)}, "bond_life_ratio": round(life_ratio, 1),
            "months_35_to_24": months, "airborne_at_0.05s": early, "lane_offset_end_m": round(float(xs[-1] - X_LANE), 2)}


if __name__ == "__main__":
    import json
    print(json.dumps(blowout_physics(), indent=1))
