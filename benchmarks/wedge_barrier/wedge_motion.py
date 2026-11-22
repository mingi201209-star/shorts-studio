"""EP.18 wedge (anti-ram) barrier (pure Python + numpy). Render-world coordinates: a two-lane gate road along +y; the barrier line is
y = 0. Each lane has a steel plate hinged on the protected side (y = PLATE_L) over a concrete pit; in an emergency two hydraulic
cylinders swing its front edge up to about 0.9 m in about a second, and a striped steel skirt closes the face below it.

The red car (lane A, x = LANE_A) drives in at 50 mph and hits the raised face at t = 0. Its nose crushes at a constant deceleration
until the car stops (crush stroke = the CC0 car's crushable nose, crumple_motion), and the impact, below the car's centre of mass,
pitches it about its front contact: the rear lifts and drops back. The plate does not move; the force goes through the cylinders and
hinge into the concrete foundation. A 15,000 lb box truck (lane B) is the test-standard case (ASTM F2656 M50: 15,000 lb at 50 mph,
P1 = at most 1 m past the barrier). Simplified explanation model; not a crash-test simulation."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
MPH = 0.44704
LB = 0.45359237
FT = 0.3048
V0 = 50 * MPH
LANE_A, LANE_B = -1.9, 1.9
PLATE_L = 1.8                    # hinge to front edge
PLATE_W = 3.3
PHI_MAX = math.asin(0.9 / PLATE_L)
RISE_START, RISE_TIME = -1.25, 1.0
PIT_DEPTH = 1.0
# car (CC0 sedan, from base.load_source_car)
CAR_MASS = 1400.0
NOSE, TAIL = 1.926, 2.065
CAR_CRUSH = 0.95 * 0.75          # crumple_motion.CRUSH_LENGTH * COMPACTION: the stroke the nose can give
CG_H, CONTACT_H = 0.55, 0.45     # impact force acts a little below the centre of mass
K_CG = 1.25                      # pitch radius of gyration
# truck (15,000 lb box truck)
TRUCK_MASS = 15000 * LB
TRUCK_NOSE, TRUCK_TAIL = 0.6, 6.4   # from its reference point (front axle) to the bumper and to the rear of the box
TRUCK_CRUSH = 0.85
TRUCK_CG_H, TRUCK_CONTACT_H, TRUCK_K = 1.15, 0.95, 2.2
DT = 0.0005


def plate_angle(t: float) -> float:
    u = min(1.0, max(0.0, (t - RISE_START) / RISE_TIME))
    return PHI_MAX * (u * u * (3 - 2 * u))


def plate_front(t: float) -> tuple[float, float]:
    """(y, z) of the plate's front edge."""
    phi = plate_angle(t)
    return PLATE_L * (1 - math.cos(phi)), PLATE_L * math.sin(phi)


FACE_Y = PLATE_L * (1 - math.cos(PHI_MAX))     # where the raised face stands


@lru_cache(maxsize=None)
def _crash(mass, crush, cg_h, contact_h, k, nose):
    """Rows (t, travel past contact s, speed, pitch theta (rear up), pitch rate) from contact to 4 s."""
    a = V0 * V0 / (2 * crush)
    t_stop = V0 / a
    w = V0 * (cg_h - contact_h) / (k * k)                       # pitch rate from the angular impulse about the centre of mass
    th = 0.0
    dh, dv = nose, cg_h - 0.30                                  # pivot (front contact, low) to the centre of mass
    kp2 = k * k + dh * dh + dv * dv
    rows, t = [], 0.0
    while t <= 4.0:
        s = V0 * t - 0.5 * a * t * t if t < t_stop else crush
        v = max(0.0, V0 - a * t)
        rows.append((t, s, v, th, w))
        alpha = -G * (dh * math.cos(th) - dv * math.sin(th)) / kp2
        w += alpha * DT
        th += w * DT
        if th < 0.0:                                            # lands on its wheels: a small bounce, then rests
            th, w = 0.0, -0.25 * w if abs(w) > 0.2 else 0.0
        t += DT
    return tuple(rows), a, t_stop


def car_crash():
    return _crash(CAR_MASS, CAR_CRUSH, CG_H, CONTACT_H, K_CG, NOSE)


def truck_crash():
    return _crash(TRUCK_MASS, TRUCK_CRUSH, TRUCK_CG_H, TRUCK_CONTACT_H, TRUCK_K, TRUCK_NOSE + 1.4)


def _at(rows, t):
    i = min(len(rows) - 1, max(0, int(round(t / DT))))
    return rows[i]


def car_state(t: float) -> dict:
    """Car reference point (y), crush stroke, pitch (rear up, rad) and the pivot it pitches about."""
    if t < 0:
        y_nose = FACE_Y + V0 * t
        return {"t": t, "y": y_nose - NOSE, "crush": 0.0, "pitch": 0.0, "speed": V0, "pivot": (FACE_Y, 0.30)}
    rows, _, _ = car_crash()
    _, s, v, th, _ = _at(rows, t)
    return {"t": t, "y": FACE_Y - NOSE + s, "crush": s, "pitch": th, "speed": v, "pivot": (FACE_Y, 0.30)}


def truck_state(t: float) -> dict:
    if t < 0:
        return {"t": t, "y": FACE_Y + V0 * t - TRUCK_NOSE, "crush": 0.0, "pitch": 0.0, "speed": V0, "pivot": (FACE_Y, 0.30)}
    rows, _, _ = truck_crash()
    _, s, v, th, _ = _at(rows, t)
    return {"t": t, "y": FACE_Y - TRUCK_NOSE + s, "crush": s, "pitch": th, "speed": v, "pivot": (FACE_Y, 0.30)}


def impact_force(t: float, truck: bool = False) -> float:
    rows, a, t_stop = truck_crash() if truck else car_crash()
    return (TRUCK_MASS if truck else CAR_MASS) * a if 0 <= t < t_stop else 0.0


N_DEBRIS = 60
SLIDE_DEC = 6.0


@lru_cache(maxsize=None)
def debris() -> tuple:
    """Pieces thrown at the impact: bumper and grille plastic, headlamp glass, and sparks from the steel face.
    (spawn time, position, velocity, size, spin, kind)."""
    rng = np.random.default_rng(1818)
    out = []
    for k in range(N_DEBRIS):
        kind = "spark" if k < 18 else "glass" if k < 38 else "plastic"
        tb = float(rng.uniform(0.0, 0.05))
        x = LANE_A + rng.uniform(-0.75, 0.75)
        pos = np.array([x, FACE_Y - 0.05, rng.uniform(0.35, 0.85)])
        if kind == "spark":
            vel = np.array([rng.uniform(-4, 4), rng.uniform(-3, 4), rng.uniform(1, 6)])
            size = (0.02, 0.02, 0.02)
        else:
            vel = np.array([rng.uniform(-3.5, 3.5), V0 * rng.uniform(0.15, 0.45), rng.uniform(2.0, 6.5)])
            size = (rng.uniform(0.03, 0.07),) * 3 if kind == "glass" else (rng.uniform(0.08, 0.25), rng.uniform(0.05, 0.12), 0.012)
        out.append((tb, pos, vel, size, rng.uniform(-15, 15, 3), kind))
    return tuple(out)


SPARK_LIFE = 0.35


def debris_pose(k: int, t: float):
    tb, p0, v0, size, spin, kind = debris()[k]
    tau = t - tb
    if tau < 0 or (kind == "spark" and tau > SPARK_LIFE):
        return None
    h0 = size[2] / 2
    vz, z0 = v0[2], p0[2] - h0
    t1 = (vz + math.sqrt(vz * vz + 2 * G * z0)) / G
    if tau <= t1:
        return p0 + v0 * tau + np.array([0, 0, -0.5 * G * tau * tau]), spin * tau, True
    p1 = p0 + v0 * t1 + np.array([0, 0, -0.5 * G * t1 * t1])
    vh = v0[:2] * 0.5
    sp = float(np.hypot(*vh))
    d = min(tau - t1, sp / SLIDE_DEC)
    dist = sp * d - 0.5 * SLIDE_DEC * d * d
    dirn = vh / max(sp, 1e-9)
    return np.array([p1[0] + dirn[0] * dist, p1[1] + dirn[1] * dist, h0]), np.array([0, 0, spin[2] * t1]), False


def airborne_count(t: float) -> int:
    return sum(1 for k in range(N_DEBRIS) if (p := debris_pose(k, t)) is not None and p[2])


def wedge_physics() -> dict:
    problems = []
    h = plate_front(10.0)[1]
    if abs(h / FT - 3.0) > 0.25:
        problems.append(f"raised height {h / FT:.2f} ft (narration: nearly three feet)")
    if not 0.8 <= RISE_TIME <= 1.5:
        problems.append("the plate does not rise in about a second")
    rows, a, t_stop = car_crash()
    if rows[-1][2] > 0 or t_stop > 0.2:
        problems.append("the car is not stopped dead")
    th = np.array([r[3] for r in rows])
    lift = (NOSE + TAIL) * math.sin(th.max())
    if lift < 0.6:
        problems.append(f"the rear lifts only {lift:.2f} m (narration: flips into the air)")
    if th[-1] > 1e-3:
        problems.append("the car does not come back down on its wheels")
    if th.max() > math.radians(40):
        problems.append("the car flips over")
    trows, ta, tts = truck_crash()
    penetration = TRUCK_CRUSH            # the barrier face stays put: the truck's front goes at most its crush stroke past first contact
    if penetration > 1.0 or trows[-1][2] > 0:
        problems.append(f"the truck goes {penetration:.2f} m past the face (ASTM P1: at most 1 m)")
    if abs(TRUCK_MASS / LB - 15000) > 1:
        problems.append("the truck is not 15,000 lb")
    for k in range(N_DEBRIS):
        for t in np.arange(0.0, 3.0, 0.01):
            p = debris_pose(k, float(t))
            if p is not None and p[0][2] < debris()[k][3][2] / 2 - 1e-6:
                problems.append(f"piece {k} goes into the ground")
                break
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "raised_ft": round(h / FT, 2), "rise_s": RISE_TIME,
            "car_decel_g": round(a / G, 1), "car_stop_s": round(t_stop, 3), "rear_lift_m": round(lift, 2), "max_pitch_deg": round(math.degrees(th.max()), 1),
            "truck_lb": round(TRUCK_MASS / LB), "truck_decel_g": round(ta / G, 1), "truck_penetration_m": penetration,
            "car_force_kN": round(CAR_MASS * a / 1000), "truck_force_kN": round(TRUCK_MASS * ta / 1000)}


if __name__ == "__main__":
    import json
    print(json.dumps(wedge_physics(), indent=1))
