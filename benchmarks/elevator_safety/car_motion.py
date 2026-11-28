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
