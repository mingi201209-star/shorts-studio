"""EP.37 elevator safety gear (pure Python), started with EP.36 so its opening could be EP.36's teaser (owner, 2026-11-28:
attach the teaser from the very first build). Render-world coordinates: the hoistway's centre line along +z (up), the car's floor
at z = car_z; the guide rails at x = +-RAIL_X; the landing doors on the -y wall.

The car is coming down at its rated speed when every hoist rope breaks. It falls freely; the overspeed governor at the top of the
shaft trips at 115 % of the rated speed and grips its rope; the rope, stopped, pulls the safety lever on the car, which drives the
progressive safety gear's wedges up against the guide rails after a short pull-through; the wedges squeeze the rails through
springs and the friction brings the car to a stop at a set retardation (progressive gear: an average deceleration between 0.2 g
and 1 g, required above 1 m/s).

Simplified explanation model; not a product's test data."""
from __future__ import annotations

import math

from functools import lru_cache

G = 9.81
FT = 0.3048
RATED = 2.0                       # m/s (about 400 ft/min)
TRIP = 1.15 * RATED               # the governor trips at 115 % of the rated speed
PULL_THROUGH_S = 0.08             # the stopped governor rope pulling the lever up, the wedges closing on the rails
DECEL_G = 0.6                     # the progressive gear's set average retardation
CAR_KG = 1200.0
LOAD_KG = 8 * 75.0                # "full of people": eight passengers
SNAP_Z = 0.0                      # the car floor's height when the ropes break
DT = 0.0005


@lru_cache(maxsize=None)
def fall() -> tuple:
    """Rows (t, z, v, a, phase) from the ropes breaking (t = 0): v is the downward speed, a the deceleration (+ = slowing), phase
    "free", "pull" (governor tripped, wedges closing) or "grip" (wedges on the rails), ending stopped."""
    t, z, v = 0.0, SNAP_Z, RATED
    rows = []
    t_trip = None
    while True:
        if t_trip is None and v >= TRIP:
            t_trip = t
        if t_trip is None or t < t_trip + PULL_THROUGH_S:
            phase, a = ("free" if t_trip is None else "pull"), -G
        else:
            phase, a = "grip", DECEL_G * G
        rows.append((t, z, v, a, phase))
        if phase == "grip" and v <= 0.0:
            break
        v = max(0.0, v - a * DT)
        z -= v * DT
        t += DT
    return tuple(rows)


def state(t: float) -> dict:
    """The car at time t after the ropes break (t < 0: still running down on its ropes at the rated speed)."""
    rows = fall()
    if t < 0:
        return {"t": t, "car_z": SNAP_Z - RATED * t, "speed": RATED, "decel_g": 0.0, "phase": "roped", "wedge": 0.0, "gripping": False}
    i = min(len(rows) - 1, int(round(t / DT)))
    _, z, v, a, phase = rows[i]
    t_trip = next(r[0] for r in rows if r[4] != "free")
    wedge = 0.0 if phase == "free" else min(1.0, (t - t_trip) / PULL_THROUGH_S)
    return {"t": t, "car_z": z, "speed": v, "decel_g": a / G, "phase": phase, "wedge": wedge, "gripping": phase == "grip" and v > 0}


def stop_time() -> float:
    return fall()[-1][0]


def car_physics() -> dict:
    rows = fall()
    problems = []
    v_max = max(r[2] for r in rows)
    drop = SNAP_Z - rows[-1][1]
    grip = [r for r in rows if r[4] == "grip"]
    avg = (grip[0][2] ** 2) / (2 * (grip[0][1] - grip[-1][1])) / G if grip else 0.0
    if not 0.2 <= avg <= 1.0:
        problems.append(f"average deceleration {avg:.2f} g outside the progressive gear's 0.2-1 g")
    if drop > 3 * FT * 1.5:
        problems.append(f"the car drops {drop / FT:.1f} ft before it stops")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "rated_mps": RATED, "trip_mps": round(TRIP, 2),
            "max_speed_mps": round(v_max, 2), "drop_m": round(drop, 2), "drop_ft": round(drop / FT, 1), "avg_g": round(avg, 2),
            "stop_s": round(rows[-1][0], 3), "mass_kg": CAR_KG + LOAD_KG}


if __name__ == "__main__":
    import json
    print(json.dumps(car_physics(), indent=1))


GOV_R = 0.30                       # governor sheave radius (m); the rope runs over it at the car's speed
FLY_OPEN_FROM = 0.85 * RATED       # the flyweights start to swing out above 85 % of the rated speed, fully out at the trip speed
OTIS_PITCH = 0.30                  # 1854: the guide posts' tooth spacing (m)
OTIS_Z0 = 3.0                      # the platform's height when the rope is cut (m)


def travel(t: float) -> float:
    """Rope run past the governor since the break (m, + = car going down); before the break the car runs at the rated speed."""
    return RATED * t if t < 0 else SNAP_Z - state(t)["car_z"]


def governor(t: float) -> dict:
    """The governor sheave: it turns with the rope until the trip, when the pawl catches a tooth and holds it (the rope stops and
    the still-falling car pulls the safety lever). Flyweights swing out with speed, fully out at the trip speed."""
    st = state(t)
    tripped = st["phase"] not in ("roped", "free")
    t_trip = next(r[0] for r in fall() if r[4] != "free")
    turned = travel(min(t, t_trip)) / GOV_R
    v = st["speed"] if not tripped else TRIP
    fly = 1.0 if tripped else min(1.0, max(0.0, (v - FLY_OPEN_FROM) / (TRIP - FLY_OPEN_FROM)))
    return {"angle": turned, "fly": fly, "locked": tripped, "rope_speed": 0.0 if tripped else st["speed"]}


def otis(t: float) -> dict:
    """1854: the rope is cut at t = 0; the platform falls free until the wagon spring's pawls catch the next teeth, half a tooth
    pitch down on average, then stops."""
    drop = 0.5 * OTIS_PITCH
    t_catch = math.sqrt(2 * drop / G)
    if t < 0:
        return {"z": OTIS_Z0, "cut": False, "caught": False, "speed": 0.0}
    if t < t_catch:
        return {"z": OTIS_Z0 - 0.5 * G * t * t, "cut": True, "caught": False, "speed": G * t}
    return {"z": OTIS_Z0 - drop, "cut": True, "caught": True, "speed": 0.0}
