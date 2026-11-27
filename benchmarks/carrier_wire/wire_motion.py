"""EP.35 carrier arresting gear (pure Python + numpy). Render-world coordinates: the landing area's centre line along +y, the flight
deck at z = 0; the four cross-deck pendants (arresting wires) lie across the deck 50 ft apart; the jet lands toward +y.

A 50,000 lb jet engages the third wire at 130 knots (about 150 mph) with its engines at full military power (so it could fly off
again if the hook missed). The wire's two halves run from the hook to deck sheaves at x = +-SPAN, then below deck as purchase cables
to the arresting engine. The engine is hydropneumatic: the cable pulls a crosshead that drives a ram into an oil cylinder, and the
oil is forced through a valve (the constant-runout valve). The valve is set so every jet stops in the same runout, about 340 ft.
Here, the force on the jet builds up over the first metres (the wire straightening, the oil coming up to pressure) to a level that
stops this jet, under its own thrust, in exactly that runout; the energy the engine takes is the jet's motion plus the thrust's work.

Simplified explanation model; not the Navy's engine data."""
from __future__ import annotations

import math
from functools import lru_cache

G = 9.81
LB = 0.45359237
LBF = 4.448222
KNOT = 0.514444
MPH = 0.44704
FT = 0.3048
JET_LB = 50000.0                 # Mk 7 Mod 3: aircraft up to 50,000 lb at 130 knots in about 340 ft
V0 = 130 * KNOT                  # 66.9 m/s, 149.6 mph: "a hundred fifty miles an hour"
THRUST_LBF = 2 * 13000.0         # two engines at military power ("full throttle")
RUNOUT_FT = 340.0
WIRE_GAP_FT = 50.0               # "four arresting wires about 50 feet apart; pilots aim for the third"
N_WIRES = 4
CAUGHT = 2                       # the third wire
SPAN = 17.0                      # deck sheaves at x = +-SPAN (m)
D_RISE = 9.0                     # m over which the pull builds up
FOOTBALL_FIELD_FT = 360.0        # end line to end line
CDP_LIFE = 125                   # Navy: a cross-deck pendant's operational life is 125 arrestments
RAM_STROKE = 4.5                 # m of ram travel at full runout (picture only)
DT = 0.0005


def wire_y() -> tuple[float, ...]:
    return tuple(i * WIRE_GAP_FT * FT for i in range(N_WIRES))


def mass() -> float:
    return JET_LB * LB


def thrust() -> float:
    return THRUST_LBF * LBF


def _stop_distance(f_max: float) -> float:
    m, v, d = mass(), V0, 0.0
    while v > 0.0:
        f = f_max * (1.0 - math.exp(-d / D_RISE)) - thrust()
        v = v - f / m * DT if f > 0 or v > 0 else 0.0
        if f <= 0 and d > 50:
            return float("inf")
        d += max(v, 0.0) * DT
    return d


@lru_cache(maxsize=None)
def f_max() -> float:
    """The engine's full pull on the jet, set (like the runout valve) so the jet stops in RUNOUT_FT."""
    lo, hi = 2e5, 3e6
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _stop_distance(mid) > RUNOUT_FT * FT:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def pull(d: float) -> float:
    """Backward force on the jet (N) with the hook d metres past the wire's rest line."""
    return 0.0 if d <= 0 else f_max() * (1.0 - math.exp(-d / D_RISE))


def payout(d: float) -> float:
    """Cable pulled out of the deck at each sheave: the half-wire's length from the sheave to the hook, minus its rest length."""
    return 0.0 if d <= 0 else math.hypot(SPAN, d) - SPAN


def tension(d: float) -> float:
    """Tension in each half of the wire: the two halves' pull along the deck adds up to the force on the jet."""
    return 0.0 if d <= 0 else pull(d) * math.hypot(SPAN, d) / (2 * d)


@lru_cache(maxsize=None)
def arrest() -> tuple:
    """Rows (t, d, v, a) from the hook catching the wire (t = 0) until the jet stops; a is the deceleration (positive = slowing)."""
    m = mass()
    t, d, v, rows = 0.0, 0.0, V0, []
    while True:
        a = (pull(d) - thrust()) / m
        rows.append((t, d, v, a))
        if v <= 0.0:
            break
        v = max(0.0, v - a * DT)
        d += v * DT
        t += DT
    return tuple(rows)


def jet_state(t: float) -> dict:
    """The hook's distance past the caught wire, speed, deceleration, cable payout and ram travel at time t (t < 0: still rolling in
    at full speed, hook dragging on the deck)."""
    rows = arrest()
    if t < 0:
        d, v, a = V0 * t, V0, 0.0
    else:
        i = min(len(rows) - 1, int(round(t / DT)))
        _, d, v, a = rows[i]
    p = payout(d)
    return {"t": t, "d": d, "speed": v, "decel_g": a / G, "payout": p, "ram": RAM_STROKE * p / payout(RUNOUT_FT * FT),
            "pull": pull(d), "tension": tension(d)}


def stop_time() -> float:
    return arrest()[-1][0]


def wire_physics() -> dict:
    """Every number the narration says, from the model."""
    problems = []
    rows = arrest()
    t_stop, d_stop = rows[-1][0], rows[-1][1]
    if abs(d_stop / FT - RUNOUT_FT) > 5:
        problems.append(f"the jet stops in {d_stop / FT:.0f} ft, not about {RUNOUT_FT:.0f}")
    if not 0.8 * FOOTBALL_FIELD_FT <= d_stop / FT <= 1.1 * FOOTBALL_FIELD_FT:
        problems.append("the runout is not about the length of a football field")
    if abs(V0 / MPH - 150) > 1.0:
        problems.append("the engaging speed is not about 150 mph")
    e_in = 0.5 * mass() * V0 ** 2 + thrust() * d_stop
    e_abs = sum(pull(r[1]) * (rows[i + 1][1] - r[1]) for i, r in enumerate(rows[:-1]))
    if abs(e_abs - e_in) / e_in > 0.01:
        problems.append("the energy the engine takes does not match the jet's motion plus the thrust's work")
    peak = max(r[3] for r in rows) / G
    if not 1.5 <= peak <= 4.0:
        problems.append(f"peak deceleration {peak:.1f} g is not a plausible trap")
    if any(r[3] < -1e-9 for r in rows[200:]):
        problems.append("the thrust wins somewhere after the wire is taut")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "jet_lb": JET_LB, "speed_mph": round(V0 / MPH, 1),
            "speed_knots": round(V0 / KNOT), "stop_ft": round(d_stop / FT), "stop_s": round(t_stop, 2), "peak_g": round(peak, 2),
            "energy_MJ": round(e_in / 1e6, 1), "max_tension_lbf": round(max(tension(r[1]) for r in rows) / LBF),
            "max_payout_ft": round(payout(d_stop) / FT), "pull_max_lbf": round(f_max() / LBF), "wires": N_WIRES, "caught": CAUGHT + 1,
            "cable_life": CDP_LIFE}


if __name__ == "__main__":
    import json
    print(json.dumps(wire_physics(), indent=1))
