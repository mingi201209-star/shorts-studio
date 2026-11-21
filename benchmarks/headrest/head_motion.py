"""EP.12 one difference: the headrest. The same car is hit from behind at a red light (rear impact, the struck car gains DV in a
half-sine pulse of T seconds). The seat pushes the torso forward with the car; the head, sitting on the neck, lags behind and rotates
backward (neck extension) under its own inertia. Head: rigid body on a pivot at the base of the neck with a linear rotational spring and
damper for the neck muscles and ligaments. With the headrest up and close, the back of the head meets it after BACKSET metres of rearward
travel and is caught by the foam (stiff spring); with the headrest low, its top is below the head, so nothing catches the head.
Simplified explanation model, not calibrated to any crash test or dummy. Pure Python."""
from __future__ import annotations

import math
from functools import lru_cache

G = 9.81
MPH = 0.44704
DV = 10 * MPH                  # struck-car speed change (m/s): a low-speed rear-end hit
T_PULSE = 0.10                 # s
A_PEAK = DV * math.pi / (2 * T_PULSE)
HEAD_M = 4.5                   # kg
R_CG = 0.10                    # m, neck pivot to head centre of mass
J = HEAD_M * R_CG ** 2 + 0.020 # kg m^2 about the neck pivot
K_NECK = 15.0                  # N m / rad
C_NECK = 0.9                   # N m s / rad
R_CONTACT = 0.15               # m, neck pivot to where the back of the head meets the headrest
BACKSET = 0.04                 # m, gap between the back of the head and a well set headrest
K_FOAM = 1800.0                # N m / rad once the head presses into the headrest
C_FOAM = 6.0
DT = 1e-5
T_END = 0.40
WHIPLASH_DEG = 30.0            # extension the film calls a whip (for the colour of the neck: green below, red above)


def car_accel(t: float) -> float:
    return A_PEAK * math.sin(math.pi * t / T_PULSE) if 0.0 <= t <= T_PULSE else 0.0


def car_speed(t: float) -> float:
    """Speed gained by the struck car (m/s) t seconds after the hit (it was standing at the light)."""
    if t <= 0:
        return 0.0
    if t >= T_PULSE:
        return DV
    return DV * 0.5 * (1 - math.cos(math.pi * t / T_PULSE))


def car_travel(t: float) -> float:
    if t <= 0:
        return 0.0
    if t >= T_PULSE:
        return DV * (T_PULSE / 2) + DV * (t - T_PULSE)
    return DV * 0.5 * (t - T_PULSE / math.pi * math.sin(math.pi * t / T_PULSE))


@lru_cache(maxsize=None)
def _run(kind: str) -> tuple:
    th, w, rows = 0.0, 0.0, []
    theta_c = BACKSET / R_CONTACT
    n = int(round(T_END / DT))
    for i in range(n + 1):
        t = i * DT
        a = car_accel(t)
        torque = HEAD_M * a * R_CG * math.cos(th) - K_NECK * th - C_NECK * w
        if kind == "high" and th > theta_c:
            torque -= K_FOAM * (th - theta_c) + C_FOAM * w
        w += torque / J * DT
        th += w * DT
        if i % 10 == 0:
            rows.append((t, th, w, a))
    return tuple(rows)


def at(kind: str, t: float) -> dict:
    """t = seconds after the hit (negative = waiting at the light). theta = neck extension (rad, head tipped back)."""
    if t < 0:
        return {"t": t, "theta": 0.0, "deg": 0.0, "car_v": 0.0, "car_x": 0.0, "accel_g": 0.0, "caught": False}
    rows = _run(kind)
    i = min(len(rows) - 1, int(round(t / (DT * 10))))
    tt, th, w, a = rows[i]
    return {"t": t, "theta": th, "deg": math.degrees(th), "car_v": car_speed(t), "car_x": car_travel(t), "accel_g": a / G,
            "caught": kind == "high" and th > BACKSET / R_CONTACT}


def peak(kind: str) -> tuple[float, float]:
    rows = _run(kind)
    i = max(range(len(rows)), key=lambda k: rows[k][1])
    return math.degrees(rows[i][1]), rows[i][0]


def head_travel_cm(kind: str) -> float:
    return 100 * R_CONTACT * math.radians(peak(kind)[0])


def head_physics() -> dict:
    problems = []
    hi, t_hi = peak("high")
    lo, t_lo = peak("low")
    if not lo >= 2.5 * hi:
        problems.append(f"low headrest extension {lo:.0f} deg is not far beyond the high one {hi:.0f} deg")
    if not 50 <= lo <= 75:
        problems.append(f"low headrest peak {lo:.0f} deg outside the 50-75 deg the film shows")
    if hi > 22:
        problems.append(f"high headrest still lets the neck bend {hi:.0f} deg")
    if not 0.07 <= t_lo <= 0.16:
        problems.append(f"the whip peaks at {t_lo * 1000:.0f} ms (narration: about a tenth of a second)")
    contact = next(r[0] for r in _run("high") if r[1] > BACKSET / R_CONTACT)
    if not contact < 0.08:
        problems.append("the high headrest catches the head late")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "peak_deg": {"high": round(hi, 1), "low": round(lo, 1)},
            "peak_ms": {"high": round(1000 * t_hi), "low": round(1000 * t_lo)}, "catch_ms": round(1000 * contact), "accel_peak_g": round(A_PEAK / G, 1),
            "dv_mph": round(DV / MPH, 1), "backset_cm": 100 * BACKSET}


if __name__ == "__main__":
    import json
    print(json.dumps(head_physics(), indent=1))
