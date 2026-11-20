"""EP.10 following distance (pure Python, no Blender): the car ahead brakes hard; two followers at the same speed with the same driver and
the same brakes, one a 3-second gap behind, one a 1-second gap behind.

Each follower keeps going at full speed for the driver's reaction time (REACTION_S: see the brake lights, move the foot, press), then
brakes at the same deceleration as the car ahead. Braking distance is v^2 / (2 a), so it grows with the square of the speed.
If the gap (bumper to bumper) reaches zero the two cars collide: a perfectly plastic impact (equal masses, they move on together at the
common speed and keep braking). Qualitative explanation model; numbers in the film use these same textbook formulas."""
from __future__ import annotations

from functools import lru_cache

G = 9.81
MPH = 0.44704
V0 = 60 * MPH                   # 26.8 m/s, 96.6 km/h
DECEL = 0.8 * G                 # dry road, hard braking
REACTION_S = 1.5
GAP_S = {"three": 3.0, "one": 1.0}
CAR_LEN = 4.0                   # nose to tail of the CC0 sedan (geometry 1.93 + 2.07)
DT = 0.001
T_END = 6.0


def reaction_distance(v: float = V0) -> float:
    return v * REACTION_S


def braking_distance(v: float = V0) -> float:
    return v * v / (2 * DECEL)


@lru_cache(maxsize=None)
def _run(gap: str) -> tuple:
    lead_x, lead_v = V0 * GAP_S[gap] + CAR_LEN, V0       # positions of the cars' tails/noses: follower nose at 0, lead tail at the gap
    fol_x, fol_v = 0.0, V0
    hit = None
    rows = []
    for i in range(int(round(T_END / DT)) + 1):
        t = i * DT
        a_lead = DECEL if lead_v > 0 else 0.0
        a_fol = DECEL if (t >= REACTION_S and fol_v > 0) else 0.0
        lead_v = max(0.0, lead_v - a_lead * DT)
        fol_v = max(0.0, fol_v - a_fol * DT)
        lead_x += lead_v * DT
        fol_x += fol_v * DT
        gap_m = lead_x - CAR_LEN - fol_x
        if gap_m <= 0.0 and fol_v > lead_v:
            if hit is None:
                hit = {"t": t, "closing_ms": fol_v - lead_v, "fol_v": fol_v, "lead_v": lead_v}
            v = 0.5 * (fol_v + lead_v)
            fol_v = lead_v = v
            fol_x = lead_x - CAR_LEN
            gap_m = 0.0
        rows.append((t, lead_x, lead_v, fol_x, fol_v, max(0.0, gap_m), a_lead > 0, a_fol > 0))
    return tuple(rows), hit


def at(gap: str, t: float) -> dict:
    rows, hit = _run(gap)
    if t < 0:
        x0 = rows[0]
        return {"t": t, "lead_x": x0[1] + V0 * t, "lead_v": V0, "fol_x": V0 * t, "fol_v": V0, "gap_m": V0 * GAP_S[gap], "lead_braking": False,
                "fol_braking": False, "hit": False, "since_hit": None}
    i = min(len(rows) - 1, max(0, int(round(t / DT))))
    t_, lx, lv, fx, fv, g, lb, fb = rows[i]
    return {"t": t_, "lead_x": lx, "lead_v": lv, "fol_x": fx, "fol_v": fv, "gap_m": g, "lead_braking": lb or (lv == 0 and t_ > 0), "fol_braking": fb,
            "hit": bool(hit and t_ >= hit["t"]), "since_hit": (t_ - hit["t"]) if hit and t_ >= hit["t"] else None}


def follow_physics() -> dict:
    """Gate: what the narration says is what the model does."""
    problems = []
    rows3, hit3 = _run("three")
    rows1, hit1 = _run("one")
    if hit3 is not None:
        problems.append("the 3-second car hits the car ahead")
    if hit1 is None:
        problems.append("the 1-second car stops in time")
    end_gap3 = rows3[-1][5]
    if end_gap3 < 5.0:
        problems.append(f"the 3-second car stops only {end_gap3:.1f} m behind")
    if abs(reaction_distance() - 40.2) > 0.3:
        problems.append("reaction distance at 60 mph is not about 40 m")
    if abs(braking_distance(2 * 13.4) / braking_distance(13.4) - 4.0) > 1e-6:
        problems.append("doubling the speed does not quadruple the braking distance")
    first_brake = next(r[0] for r in rows1 if r[7])
    if abs(first_brake - REACTION_S) > 0.002:
        problems.append("the follower brakes before the reaction time is over")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "reaction_m": round(reaction_distance(), 1),
            "braking_m": round(braking_distance(), 1), "stop_total_m": round(reaction_distance() + braking_distance(), 1),
            "one_s_hit_at_s": round(hit1["t"], 3) if hit1 else None, "one_s_impact_kmh": round(hit1["closing_ms"] * 3.6, 1) if hit1 else None,
            "three_s_stops_behind_m": round(end_gap3, 1)}
