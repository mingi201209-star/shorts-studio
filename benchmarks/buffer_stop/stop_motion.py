"""EP.36 friction buffer stop (pure Python). Render-world coordinates: the track runs along +y, the rails' top at z = 0; the buffer
stop's buffer faces sit at y = 0 at rest and the stop slides toward +y; the train comes in from -y.

The stop is a steel frame on the rails, clamped to them by friction shoes (pairs of shoes bolted onto the rail head, Rawie's
"rail brake" and Oleo's sliding friction design). Two hydraulic buffers on its front take the first hit. When the force through
them exceeds the shoes' grip, the whole stop slides along the rails, and the shoes' friction turns the train's motion into heat.
The number of shoe pairs is chosen so a six-car train of 246 t at 25 km/h (15.5 mph) stops in about 18 m (59 ft), as in Oleo's
sliding friction data (6 cars, 246 t: about 7 m at 10 km/h, 18 m at 25 km/h); each pair grips with at most 50 kN (Oleo).

Two-body model: the train (mass M) and the stop (mass m) joined through the buffers while in contact: a gas spring k and the oil
c, the force capped by the oil's relief pressure (a hydraulic buffer's flat top). The stop stays put while the buffer force is
within the shoes' static grip and slides against their kinetic friction once it exceeds it; kicking the light stop up to the
train's speed is the peak of the stop. Two comparisons: the same train into a solid wall, stopped by crushing its front by
WALL_CRUSH ("would wreck it"), and a car stopping as hard as it can on dry pavement ("gentler than slamming on the brakes").
(A first script said the cab's coffee would not spill; this model showed a cup with 15 mm of headroom would, so the line went.)

Simplified explanation model; not a product's test data."""
from __future__ import annotations

import math
from functools import lru_cache

G = 9.81
MPH = 0.44704
FT = 0.3048
KMH = 1 / 3.6
SHORT_TON = 907.18474
CARS = 6
TRAIN_KG = 246000.0                # Oleo: 6 cars, 246 t
V0 = 25 * KMH                      # 6.94 m/s = 15.5 mph: "fifteen miles an hour"
STOP_KG = 4500.0                   # the stop's frame, buffers and shoes
SHOE_PAIRS = 8                     # four on each rail
PAIR_MAX_N = 50000.0               # Oleo: each pair of friction shoes up to 50 kN
STATIC_RATIO = 1.15                # grip before it starts to slide, over the sliding friction
BUFFER_K = 1.5e6                   # N/m, both buffers together (gas spring)
BUFFER_C = 6.0e4                   # N s/m, both buffers together (oil through the orifice)
BUFFER_CAP = 5.6e5                 # N, both together: the oil's relief pressure caps the force (a hydraulic buffer's flat top)
BUFFER_STROKE = 0.6                # m
END_K = 1.0e8                      # N/m if a buffer ever bottomed out
TARGET_FT = 59.0                   # Oleo: about 18 m at 25 km/h
WALL_CRUSH = 0.3                   # m of crushed front in the what-if
CAR_HARD_BRAKING_G = 0.7           # a hard stop in a car on dry pavement is about 0.7 g or more
CAR_V0 = 30 * MPH                  # the car in the comparison
CAR_DECEL_G = 0.8                  # slamming on the brakes, ABS working, dry road
DT = 0.0005


def _simulate(pair_n: float) -> tuple:
    """Rows (t, y_train, v_train, a_train, y_stop, v_stop, compression, buffer_force, friction_work, damper_work) from first contact
    (t = 0) until both come to rest. a_train is the deceleration (positive = slowing)."""
    f_k = SHOE_PAIRS * pair_n
    f_s = STATIC_RATIO * f_k
    t, yt, vt, ys, vs = 0.0, 0.0, V0, 0.0, 0.0
    w_f = w_d = 0.0
    rows = []
    while True:
        comp = yt - ys
        if comp > 0:
            fb = max(0.0, min(BUFFER_CAP, BUFFER_K * comp + BUFFER_C * (vt - vs)))
            if comp > BUFFER_STROKE:
                fb += END_K * (comp - BUFFER_STROKE)
        else:
            fb = 0.0
        if vs > 1e-6:
            fr = f_k
        elif fb > f_s:
            fr = f_k
        else:
            fr = fb                                     # held by static grip
        at = fb / TRAIN_KG                              # train slowing
        a_s = (fb - fr) / STOP_KG                       # stop speeding up
        rows.append((t, yt, vt, at, ys, vs, comp, fb, w_f, w_d))
        if vt <= 1e-4 and vs <= 1e-4 and t > 0.5:
            break
        vt = max(0.0, vt - at * DT)
        vs_new = max(0.0, vs + a_s * DT)
        dys = 0.5 * (vs + vs_new) * DT
        w_f += f_k * dys if (vs_new > 0 or vs > 0) else 0.0
        if comp > 0:
            spring = BUFFER_K * comp + (END_K * (comp - BUFFER_STROKE) if comp > BUFFER_STROKE else 0.0)
            w_d += max(0.0, fb - spring) * (vt - vs) * DT      # what the oil takes: the force beyond the gas spring's
        vs = vs_new
        yt += vt * DT
        ys += dys
        t += DT
        if t > 60:
            raise RuntimeError("the train never stops")
    return tuple(rows)


@lru_cache(maxsize=None)
def pair_force() -> float:
    """The grip of each shoe pair (N), chosen like the number of shoes on a real stop: the train stops in TARGET_FT."""
    lo, hi = 5e3, PAIR_MAX_N * 1.5
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if _simulate(mid)[-1][1] > TARGET_FT * FT:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@lru_cache(maxsize=None)
def impact() -> tuple:
    return _simulate(pair_force())


def stop_time() -> float:
    return impact()[-1][0]


def state(t: float) -> dict:
    """Everything the film shows at simulated time t (t < 0: the train still coming in at full speed, the stop at rest)."""
    rows = impact()
    if t < 0:
        r = (t, V0 * t, V0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    else:
        i = min(len(rows) - 1, int(round(t / DT)))
        r = rows[i]
    _, yt, vt, at, ys, vs, comp, fb, wf, wd = r
    return {"t": t, "train_y": yt, "train_speed": vt, "decel_g": at / G, "stop_y": ys, "stop_speed": vs,
            "compression": max(0.0, min(BUFFER_STROKE, yt - ys)), "buffer_force": fb, "slide": ys,
            "shoe_heat_kJ": wf / (2 * SHOE_PAIRS) / 1000.0, "sliding": vs > 1e-4}


def wall_state(t: float) -> dict:
    """The what-if: the same train into a solid wall at y = 0, stopped by crushing WALL_CRUSH of its front."""
    a = V0 ** 2 / (2 * WALL_CRUSH)
    t_stop = V0 / a
    if t < 0:
        return {"t": t, "train_y": V0 * t, "train_speed": V0, "decel_g": 0.0, "crush": 0.0, "hit": False}
    tt = min(t, t_stop)
    y = V0 * tt - 0.5 * a * tt * tt
    return {"t": t, "train_y": y, "train_speed": 0.0 if t >= t_stop else V0 - a * tt, "decel_g": (a / G) if t < t_stop else 0.0, "crush": y, "hit": True}


def car_state(t: float) -> dict:
    """The comparison car (t from the moment the driver stamps on the brake): CAR_DECEL_G until it stops."""
    a = CAR_DECEL_G * G
    t_stop = CAR_V0 / a
    tt = min(max(t, 0.0), t_stop)
    return {"t": t, "x": CAR_V0 * tt - 0.5 * a * tt * tt, "speed": CAR_V0 - a * tt, "decel_g": CAR_DECEL_G if 0 <= t < t_stop else 0.0}


def stop_physics() -> dict:
    """Every number the narration says, from the model."""
    problems = []
    rows = impact()
    t_stop, y_stop = rows[-1][0], rows[-1][1]
    slide = rows[-1][4]
    peak = max(r[3] for r in rows) / G
    if abs(y_stop / FT - TARGET_FT) > 3:
        problems.append(f"the train stops in {y_stop / FT:.0f} ft, not about 60")
    if abs(V0 / MPH - 15) > 1:
        problems.append("the impact speed is not about 15 mph")
    if pair_force() > PAIR_MAX_N:
        problems.append(f"each shoe pair would need {pair_force() / 1000:.0f} kN (Oleo: up to 50 kN)")
    if peak > 1.0:
        problems.append(f"peak deceleration {peak:.2f} g is over the 1 g limit (10 m/s2, Bane NOR)")
    if peak >= CAR_HARD_BRAKING_G:
        problems.append("the stop is not gentler than a hard stop in a car")
    e_in = 0.5 * TRAIN_KG * V0 ** 2
    e_spring = 0.5 * BUFFER_K * max(0.0, rows[-1][6]) ** 2
    e_out = rows[-1][8] + rows[-1][9] + e_spring
    if abs(e_out - e_in) / e_in > 0.02:
        problems.append(f"energy does not balance: in {e_in / 1e6:.2f} MJ, out {e_out / 1e6:.2f} MJ")
    comp_max = max(r[6] for r in rows)
    if comp_max > BUFFER_STROKE:
        problems.append(f"the buffers bottom out ({comp_max:.2f} m of {BUFFER_STROKE} m)")
    first_slide = next((r[0] for r in rows if r[5] > 1e-4), None)
    if first_slide is None or comp_max < 0.03:
        problems.append("the buffers do not squash before the stop slides")
    if CAR_DECEL_G < CAR_HARD_BRAKING_G:
        problems.append("the comparison car is not braking hard")
    wall_g = V0 ** 2 / (2 * WALL_CRUSH) / G
    if wall_g < 5:
        problems.append("the wall what-if is not a wreck")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "cars": CARS, "train_t": TRAIN_KG / 1000,
            "train_short_tons": round(TRAIN_KG / SHORT_TON), "speed_mph": round(V0 / MPH, 1), "speed_kmh": round(V0 * 3.6, 1),
            "stop_ft": round(y_stop / FT, 1), "stop_m": round(y_stop, 2), "slide_m": round(slide, 2), "stop_s": round(t_stop, 2),
            "peak_g": round(peak, 3), "mean_g": round(V0 ** 2 / (2 * y_stop) / G, 3), "shoe_pairs": SHOE_PAIRS,
            "pair_kN": round(pair_force() / 1000, 1), "buffer_max_m": round(comp_max, 3),
            "slides_after_s": round(first_slide, 3) if first_slide is not None else None, "energy_MJ": round(e_in / 1e6, 2),
            "heat_per_shoe_kJ": round(rows[-1][8] / (2 * SHOE_PAIRS) / 1000, 1), "car_g": CAR_DECEL_G,
            "car_vs_stop_peak": round(CAR_DECEL_G / peak, 1), "wall_g": round(wall_g, 1), "wall_vs_stop": round(wall_g / peak)}


if __name__ == "__main__":
    import json
    print(json.dumps(stop_physics(), indent=1))
