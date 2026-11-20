"""EP.11 one difference: speed. The same car (same mass, same front structure) hits the same rigid wall at 30 mph and at 40 mph.
Pure Python (no Blender), shared by the renderer, the overlays and the gates.

Front structure: a linear crush stiffness K (force grows with crush depth, the usual first-order model of a car front in crash
reconstruction). The kinetic energy 1/2 m v^2 is absorbed as 1/2 K s^2, so the crush depth s grows in proportion to the speed and the
energy with its square. K is chosen so the 40 mph car uses about 70 cm of crush (the most the EP.04 crush map allows before the cabin).
Plastic: no rebound. Simplified explanation model, not calibrated to any real vehicle or crash test.
Also: the stopping comparison (same 1.5 s reaction, same 0.8 g braking) and the equivalent fall height h = v^2 / 2g."""
from __future__ import annotations

import math
from functools import lru_cache

G = 9.81
MPH = 0.44704
MASS = 1400.0
SPEEDS = {"slow": 30.0, "fast": 40.0}            # mph
S_FAST = 0.70                                     # m of crush at 40 mph
K = MASS * (SPEEDS["fast"] * MPH) ** 2 / S_FAST ** 2     # N/m
STOREY_M = 3.0
REACTION_S = 1.5
DECEL = 0.8 * G
DT = 1e-5


def v0(kind: str) -> float:
    return SPEEDS[kind] * MPH


def energy_kj(kind: str) -> float:
    return 0.5 * MASS * v0(kind) ** 2 / 1000.0


def crush_m(kind: str) -> float:
    return v0(kind) * math.sqrt(MASS / K)


def fall_height_m(kind: str) -> float:
    return v0(kind) ** 2 / (2 * G)


def storeys(kind: str) -> int:
    return round(fall_height_m(kind) / STOREY_M)


def stop_distance(kind: str) -> float:
    v = v0(kind)
    return v * REACTION_S + v * v / (2 * DECEL)


def braking_speed_at(kind: str, x: float) -> float:
    """Speed (m/s) after travelling x metres from the moment the hazard appears (reaction, then braking)."""
    v = v0(kind)
    xr = v * REACTION_S
    if x <= xr:
        return v
    return math.sqrt(max(0.0, v * v - 2 * DECEL * (x - xr)))


def fast_speed_where_slow_stops_mph() -> float:
    return braking_speed_at("fast", stop_distance("slow")) / MPH


def brake_state(kind: str, t: float) -> dict:
    """Stopping run: t seconds after the hazard appears (negative = cruising). x = distance travelled since t = 0."""
    v = v0(kind)
    if t <= REACTION_S:
        return {"x": v * t, "v": v, "braking": False}
    tb = min(t - REACTION_S, v / DECEL)
    return {"x": v * REACTION_S + v * tb - 0.5 * DECEL * tb * tb, "v": max(0.0, v - DECEL * tb), "braking": True}


@lru_cache(maxsize=None)
def _crash(kind: str) -> tuple:
    """Integrates the crash from contact (t = 0): rows of (t, x since contact = crush, v, decel_g)."""
    v, x, t, rows = v0(kind), 0.0, 0.0, [(0.0, 0.0, v0(kind), 0.0)]
    while v > 0:
        a = K * x / MASS
        v -= a * DT
        x += max(v, 0.0) * DT
        t += DT
        rows.append((t, x, max(v, 0.0), a / G))
    return tuple(rows)


def crash_duration(kind: str) -> float:
    return _crash(kind)[-1][0]


def crash_state(kind: str, t: float) -> dict:
    """t = seconds after the nose touches the wall (negative = still approaching at full speed). y = how far the cabin has moved past the
    contact position (= crush depth s once in contact)."""
    if t < 0:
        return {"t": t, "y": v0(kind) * t, "s": 0.0, "v": v0(kind), "g": 0.0, "stopped": False}
    rows = _crash(kind)
    i = min(len(rows) - 1, int(round(t / DT)))
    tt, x, v, g = rows[i]
    return {"t": t, "y": x, "s": x, "v": v, "g": g, "stopped": i == len(rows) - 1}


def speed_physics() -> dict:
    """Gate: what the narration says is what the model does."""
    problems = []
    e = energy_kj("fast") / energy_kj("slow") - 1
    if abs(e - 0.778) > 0.002:
        problems.append(f"energy increase is {e:.3f}, the narration says 78 %")
    s_slow, s_fast = _crash("slow")[-1][1], _crash("fast")[-1][1]
    if abs(s_fast - S_FAST) > 0.01 or abs(s_slow - crush_m("slow")) > 0.01:
        problems.append("integrated crush differs from the closed form")
    if not (0.48 <= s_slow <= 0.56):
        problems.append(f"30 mph crush {s_slow:.2f} m is not about half a metre")
    if s_fast > 0.71:
        problems.append("40 mph crush runs past the crush zone (EP.04 map limit 0.71 m)")
    if (storeys("slow"), storeys("fast")) != (3, 5):
        problems.append(f"fall heights {fall_height_m('slow'):.1f} / {fall_height_m('fast'):.1f} m are not 3 / 5 storeys")
    vf = fast_speed_where_slow_stops_mph()
    if round(vf) != 35:
        problems.append(f"where the slow car stops, the fast one is at {vf:.1f} mph (narration: 35)")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "energy_kj": {k: round(energy_kj(k), 1) for k in SPEEDS},
            "energy_increase_pct": round(100 * e, 1), "crush_cm": {"slow": round(100 * s_slow, 1), "fast": round(100 * s_fast, 1)},
            "crash_ms": {k: round(1000 * crash_duration(k), 1) for k in SPEEDS}, "peak_g": {k: round(max(r[3] for r in _crash(k)), 1) for k in SPEEDS},
            "fall_m": {k: round(fall_height_m(k), 1) for k in SPEEDS}, "stop_m": {k: round(stop_distance(k), 1) for k in SPEEDS},
            "fast_mph_where_slow_stops": round(vf, 1)}


if __name__ == "__main__":
    import json
    print(json.dumps(speed_physics(), indent=1))
