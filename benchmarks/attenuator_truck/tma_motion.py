"""EP.32 truck-mounted attenuator (pure Python + numpy). Render-world coordinates: a two-lane one-way highway along +y (traffic drives
toward +y); the right lane is closed for road work. The protective truck is parked in the right lane (x = LANE_R), braked, its rear
frame at y = 0 before the crash. Its crash cushion hangs behind it from a hinge on the rear frame: deployed it lies level from
y = -CUSHION_L to 0, stowed it stands upright behind the truck ("folds down like a tail"). Inside are three blocks of aluminum honeycomb
in series, the softest at the back: each crushes at its own steady force, so a hit crushes them row by row from the back.

The red car (CC0 sedan, 1,400 kg) drives into the closed lane at 62 mph and meets the cushion's rear face at t = 0. While the car is
faster than the truck the crushing block pushes both apart with its plateau force (the car slows, the truck is shoved forward against
its brakes); when the speeds meet, the crush is over and car and truck slide on together until the truck's brakes stop them (the
roll-ahead). The test case is the 5,000 lb pickup (MASH 2270P) at 62 mph: it must stop inside the cushion's stroke.
Simplified explanation model; not a crash-test simulation."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
MPH = 0.44704
LB = 0.45359237
FT = 0.3048
V0 = 62 * MPH
LANE_W = 3.65
LANE_L, LANE_R = -LANE_W / 2, LANE_W / 2
# protective truck (22,000 lb), parked with its brakes on: rear axles only, so the friction is about 0.40 of its weight
TRUCK_MASS = 22000 * LB
TRUCK_MU = 0.40
TRUCK_LEN = 8.2                 # rear frame (y = 0) to the front bumper
# cushion: rear face plate, three honeycomb blocks (back to front), the mount frame at the hinge
STAGE_FORCE = (120e3, 200e3, 380e3)   # N: the plateau force of each block, softest at the back
STAGE_STROKE = (1.0, 1.0, 1.2)        # m each block can crush (85 % of its length; the rest is the crushed aluminum)
BLOCK_LEN = tuple(s / 0.85 for s in STAGE_STROKE)
FACE_T, MOUNT_L = 0.12, 0.30
CUSHION_L = FACE_T + sum(BLOCK_LEN) + MOUNT_L
CUSHION_W, CUSHION_Z0, CUSHION_Z1 = 2.30, 0.32, 1.22
HINGE = (0.0, 0.92)                   # (y, z) of the hinge on the truck's rear frame
STROKE = sum(STAGE_STROKE)
FOLD_START, FOLD_TIME = 0.4, 3.0      # the deploy shot: the cushion swings down from upright in 3 s
# red car (CC0 sedan) and the test pickup
CAR_MASS = 1400.0
NOSE, TAIL = 1.926, 2.065
PICKUP_MASS = 5000 * LB
PICKUP_NOSE, PICKUP_TAIL = 2.95, 2.85
DT = 0.0002


def stage_edges() -> list[float]:
    e = [0.0]
    for s in STAGE_STROKE:
        e.append(e[-1] + s)
    return e


def crush_force(c: float) -> float:
    """Plateau force of the block being crushed at total crush c; beyond the stroke the cushion is solid (bottomed out)."""
    e = stage_edges()
    for k, f in enumerate(STAGE_FORCE):
        if c < e[k + 1]:
            return f
    return 1e7


def stage_crush(c: float) -> tuple[float, ...]:
    """How far each block (back to front) has crushed at total crush c: the back one first, row by row."""
    e = stage_edges()
    return tuple(min(max(c - e[k], 0.0), STAGE_STROKE[k]) for k in range(len(STAGE_STROKE)))


@lru_cache(maxsize=None)
def _crash(mass: float):
    """Rows (t, car travel past contact x1, truck roll x2, car speed v1, truck speed v2, contact force) from contact to rest, and the
    time the crush ends."""
    x1 = x2 = 0.0
    v1, v2 = V0, 0.0
    fb = TRUCK_MU * TRUCK_MASS * G
    t, rows, t_crush, together = 0.0, [], None, False
    while True:
        c = x1 - x2
        if not together and v1 > v2:
            fc = crush_force(c)
            a1 = -fc / mass
            fr = fb if v2 > 1e-9 else min(fb, fc)
            a2 = (fc - fr) / TRUCK_MASS
        else:
            if not together:
                together, t_crush = True, t
            fc = 0.0
            if v2 <= 1e-9:
                rows.append((t, x1, x2, 0.0, 0.0, 0.0))
                break
            a1 = a2 = -fb / (mass + TRUCK_MASS)
        rows.append((t, x1, x2, v1, v2, fc))
        v1, v2 = max(0.0, v1 + a1 * DT), max(0.0, v2 + a2 * DT)
        if together:
            v1 = v2
        x1 += v1 * DT
        x2 += v2 * DT
        t += DT
    return tuple(rows), t_crush


def car_crash():
    return _crash(CAR_MASS)


def pickup_crash():
    return _crash(PICKUP_MASS)


def _at(rows, t):
    i = min(len(rows) - 1, max(0, int(round(t / DT))))
    return rows[i]


def vehicle_state(t: float, pickup: bool = False) -> dict:
    """Vehicle reference y, the cushion's crush, the truck's roll and both speeds at simulated time t (t = 0: first touch)."""
    nose = PICKUP_NOSE if pickup else NOSE
    face0 = -CUSHION_L
    if t < 0:
        return {"t": t, "y": face0 + V0 * t - nose, "crush": 0.0, "roll": 0.0, "speed": V0, "truck_speed": 0.0, "force": 0.0}
    rows, _ = pickup_crash() if pickup else car_crash()
    _, x1, x2, v1, v2, f = _at(rows, t)
    return {"t": t, "y": face0 + x1 - nose, "crush": x1 - x2, "roll": x2, "speed": v1, "truck_speed": v2, "force": f}


def car_state(t: float) -> dict:
    return vehicle_state(t, False)


def pickup_state(t: float) -> dict:
    return vehicle_state(t, True)


def fold_angle(t: float) -> float:
    """Cushion angle above level (rad): upright (pi/2) when stowed, swung down to level over FOLD_TIME (deploy shot)."""
    u = min(1.0, max(0.0, (t - FOLD_START) / FOLD_TIME))
    return (math.pi / 2) * (1.0 - u * u * (3 - 2 * u))


def car_nose_crush(t: float, pickup: bool = False) -> float:
    """The vehicle's own bumper and nose give a little against the stiffest block (visual only)."""
    st = vehicle_state(t, pickup)
    if t <= 0:
        return 0.0
    k = 0.10 + 0.14 * min(1.0, max(0.0, (st["crush"] - stage_edges()[2]) / STAGE_STROKE[2]))
    return min(k, 0.10 + 0.14) * min(1.0, t / 0.02)


N_DEBRIS = 64
SLIDE_DEC = 6.0
SPARK_LIFE = 0.35


@lru_cache(maxsize=None)
def debris() -> tuple:
    """Pieces thrown at the impact: torn aluminum skin from the cushion's face, the car's bumper plastic and headlamp glass.
    (spawn time, position, velocity, size, spin, kind). Thrown back and to the sides: the car is pushing into the cushion."""
    rng = np.random.default_rng(3232)
    out = []
    face = -CUSHION_L
    for k in range(N_DEBRIS):
        kind = "foil" if k < 26 else "glass" if k < 44 else "plastic"
        tb = float(rng.uniform(0.0, 0.06))
        pos = np.array([LANE_R + rng.uniform(-1.0, 1.0), face - 0.05 + rng.uniform(0.0, 0.4), rng.uniform(0.35, 1.15)])
        side = rng.choice((-1.0, 1.0))
        vel = np.array([side * rng.uniform(1.5, 6.0), rng.uniform(-2.5, 4.0), rng.uniform(1.5, 6.5)])
        if kind == "foil":
            size = (rng.uniform(0.08, 0.22), rng.uniform(0.06, 0.16), 0.006)
        elif kind == "glass":
            size = (rng.uniform(0.03, 0.06),) * 3
        else:
            size = (rng.uniform(0.08, 0.24), rng.uniform(0.05, 0.12), 0.012)
        out.append((tb, pos, vel, size, rng.uniform(-14, 14, 3), kind))
    return tuple(out)


def debris_pose(k: int, t: float):
    tb, p0, v0, size, spin, kind = debris()[k]
    tau = t - tb
    if tau < 0:
        return None
    h0 = size[2] / 2
    vz, z0 = v0[2], p0[2] - h0
    t1 = (vz + math.sqrt(vz * vz + 2 * G * z0)) / G
    drag = 0.6 if kind == "foil" else 1.0                       # thin foil flutters down more slowly
    if tau <= t1 / drag:
        tt = tau * drag
        return p0 + v0 * tt + np.array([0, 0, -0.5 * G * tt * tt]), spin * tau, True
    p1 = p0 + v0 * t1 + np.array([0, 0, -0.5 * G * t1 * t1])
    vh = v0[:2] * 0.4
    sp = float(np.hypot(*vh))
    d = min(tau - t1 / drag, sp / SLIDE_DEC)
    dist = sp * d - 0.5 * SLIDE_DEC * d * d
    dirn = vh / max(sp, 1e-9)
    return np.array([p1[0] + dirn[0] * dist, p1[1] + dirn[1] * dist, h0]), np.array([0, 0, spin[2] * t1]), False


def airborne_count(t: float) -> int:
    return sum(1 for k in range(N_DEBRIS) if (p := debris_pose(k, t)) is not None and p[2])


def tma_physics() -> dict:
    """Every number the narration says, from the model."""
    problems = []
    rows, t_crush = car_crash()
    crush = max(r[1] - r[2] for r in rows)
    roll = rows[-1][2]
    peak = max(r[5] for r in rows)
    if not 7.0 <= crush / FT <= 9.0:
        problems.append(f"the car crushes {crush / FT:.1f} ft of cushion (narration: about eight feet)")
    if not 3.0 <= roll / FT <= 6.5:
        problems.append(f"the truck rolls {roll / FT:.1f} ft (narration: only a few feet)")
    if crush > STROKE:
        problems.append("the car bottoms out the cushion")
    # row by row: each block starts only when the one behind it is fully crushed
    e = stage_edges()
    order_ok = all(stage_crush(c)[k] == 0.0 or stage_crush(c)[k - 1] >= STAGE_STROKE[k - 1] - 1e-9
                   for c in np.linspace(0.0, STROKE, 200) for k in range(1, 3))
    if not order_ok or not STAGE_FORCE[0] < STAGE_FORCE[1] < STAGE_FORCE[2]:
        problems.append("the blocks do not crush row by row from the back")
    used = sum(1 for k in range(3) if stage_crush(crush)[k] > 0.05)
    if used < 3:
        problems.append(f"the car reaches only {used} of the 3 rows")
    prows, pt = pickup_crash()
    pcrush = max(r[1] - r[2] for r in prows)
    if pcrush >= STROKE or max(r[5] for r in prows) >= 1e7:
        problems.append("the 5,000 lb pickup at 62 mph is not stopped inside the stroke")
    if abs(PICKUP_MASS / LB - 5000) > 1 or abs(V0 / MPH - 62) > 1e-9:
        problems.append("the test case is not a 5,000 lb pickup at 62 mph")
    if abs(fold_angle(0.0) - math.pi / 2) > 1e-9 or fold_angle(FOLD_START + FOLD_TIME) > 1e-9:
        problems.append("the cushion does not swing down from upright to level")
    for k in range(N_DEBRIS):
        for t in np.arange(0.0, 3.0, 0.01):
            p = debris_pose(k, float(t))
            if p is not None and p[0][2] < debris()[k][3][2] / 2 - 1e-6:
                problems.append(f"piece {k} goes into the ground")
                break
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "speed_mph": 62, "cushion_ft": round(CUSHION_L / FT, 1),
            "car_crush_ft": round(crush / FT, 1), "car_crush_m": round(crush, 2), "crush_time_s": round(t_crush, 3), "truck_roll_ft": round(roll / FT, 1),
            "car_peak_g": round(peak / CAR_MASS / G, 1), "car_mean_g": round(V0 / t_crush / G, 1) if t_crush else None,
            "pickup_lb": round(PICKUP_MASS / LB), "pickup_crush_ft": round(pcrush / FT, 1), "stroke_ft": round(STROKE / FT, 1),
            "pickup_roll_ft": round(prows[-1][2] / FT, 1), "rows": [round(f / 1e3) for f in STAGE_FORCE]}


if __name__ == "__main__":
    import json
    print(json.dumps(tma_physics(), indent=1))
