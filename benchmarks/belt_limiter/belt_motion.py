"""EP.05 seatbelt: how far the belted driver moves forward and how hard the belt loads the chest in the SAME crash for two belts, computed from the simulated deceleration of the
EP.04 crumple car (hits the wall at CRASH_KMH). Illustrative one-dimensional model, not a calibrated occupant model; the film description says so.

"plain": belt with a little slack and no give (spring-damper only).
"modern": a pretensioner removes the slack just after first contact (and pulls the driver back into the seat), then a load limiter caps the belt force at LIMIT_G x body weight:
above the cap the reel lets out webbing (the torsion bar twists), below it the belt is stiff again.

Room in front of the chest (ROOM_M) is a modelling choice: a limiter only helps when the chest has room to move (real cars pair it with an airbag, which this film does not show).
If the chest runs out of room it meets a much stiffer spring and the load climbs again; the gate below checks that this never happens for the modern belt.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm

CRASH_KMH = 64.0         # the same crumple car as EP.04 (stroke 0.62 m), hit harder so that a plain belt loads the chest clearly
M = 75.0                 # kg torso + head + arms that the belt has to stop
SLACK = 0.03             # m of belt slack before a plain belt takes load
K_BELT = 100_000.0       # N/m
C_BELT = 2_000.0         # N s/m
ROOM_M = 0.32            # m of forward travel before the chest meets anything (wheel or airbag zone)
K_STOP = 600_000.0       # N/m once the room is used up
C_STOP = 2_000.0
LIMIT_G = 28.0           # load limiter cap, in g of the 75 kg torso
PRETENSION_DELAY_S = 0.003     # the pretensioner fires this long after first contact
PRETENSION_PULL_M = 0.03       # how far it pulls the driver back into the seat (visual) and the slack it removes
PRETENSION_TIME_S = 0.006
CHEST_OK_G = 25.0        # same colour scale as EP.04: below this the figure reads as unharmed
CHEST_SEVERE_G = 60.0    # the 60 g chest limit used in car-safety rules: at and above this the figure reads as severely loaded
G = cm.G
VARIANTS = ("plain", "modern")


def _crash() -> dict:
    return cm.simulate("crumple", v0_kmh=CRASH_KMH)


def contact_time_s() -> float:
    """Simulated time of first contact of the car with the wall at CRASH_KMH."""
    return cm.LEAD_SIM / (CRASH_KMH / 3.6)


@lru_cache(maxsize=None)
def response(variant: str) -> dict:
    """Occupant response on the time grid of the car simulation: forward travel r (m), belt/stop load (g), webbing paid out (m), pull-back (m)."""
    if variant not in VARIANTS:
        raise KeyError(variant)
    rec = _crash()
    t, a_car = rec["t"], rec["g"] * G
    tc = contact_time_s()
    modern = variant == "modern"
    f_cap = LIMIT_G * M * G
    r = rv = pay = 0.0
    n = len(t)
    r_out, g_out, pay_out, pull_out = (np.zeros(n) for _ in range(4))
    sub = 20
    for i in range(1, n):
        dt = (t[i] - t[i - 1]) / sub
        a_i = 0.5 * (a_car[i] + a_car[i - 1])
        fired = modern and t[i] > tc + PRETENSION_DELAY_S
        slack = 0.0 if fired else SLACK
        for _ in range(sub):
            x = r - slack - pay
            f = 0.0
            if x > 0:
                f = K_BELT * x + (C_BELT * rv if rv > 0 else 0.0)
                if modern and f > f_cap:
                    x_allow = max(0.0, (f_cap - C_BELT * max(rv, 0.0)) / K_BELT)
                    pay += max(0.0, x - x_allow)        # the reel lets out webbing until the belt force equals the cap (never takes it back)
                    f = f_cap
            if r > ROOM_M:
                f += K_STOP * (r - ROOM_M) + (C_STOP * rv if rv > 0 else 0.0)
            rv += (a_i - f / M) * dt
            r += rv * dt
            if r < 0.0:
                r, rv = 0.0, max(rv, 0.0)
        r_out[i], g_out[i], pay_out[i] = r, f / (M * G), pay
        if fired:
            u = float(np.clip((t[i] - tc - PRETENSION_DELAY_S) / PRETENSION_TIME_S, 0.0, 1.0))
            pull_out[i] = PRETENSION_PULL_M * u * u * (3.0 - 2.0 * u) * max(0.0, 1.0 - r / PRETENSION_PULL_M)
    return {"t": t, "r": r_out, "chest_g": g_out, "peak_g": np.maximum.accumulate(g_out), "payout_m": pay_out, "pull_back_m": pull_out}


def at(variant: str, sim_time: float) -> dict:
    """Driver and belt state at a simulated time."""
    res = response(variant)
    def pick(key):
        return float(np.interp(sim_time, res["t"], res[key]))
    peak = pick("peak_g")
    return {"travel_m": pick("r") - pick("pull_back_m"), "chest_g": pick("chest_g"), "peak_chest_g": peak,
            "injury": float(np.clip((peak - CHEST_OK_G) / (CHEST_SEVERE_G - CHEST_OK_G), 0.0, 1.0)),
            "payout_m": pick("payout_m"), "pull_back_m": pick("pull_back_m")}


def belt_limiter_physics() -> dict:
    """Gate for EP.05: the modern belt keeps the chest load lower than the plain belt in the same crash, only pays out webbing above the force threshold, never runs out of room,
    and its pay-out never shrinks."""
    plain, modern = response("plain"), response("modern")
    problems = []
    p_plain, p_modern = float(plain["peak_g"][-1]), float(modern["peak_g"][-1])
    if not p_modern < p_plain:
        problems.append(f"the modern belt peak {p_modern:.1f} g is not below the plain belt peak {p_plain:.1f} g")
    if float(plain["payout_m"].max()) > 0.0:
        problems.append("the plain belt paid out webbing")
    if float(modern["payout_m"].max()) <= 0.0:
        problems.append("the modern belt never paid out webbing")
    if p_modern > LIMIT_G + 0.5:
        problems.append(f"the modern belt peak {p_modern:.1f} g is above the limiter cap {LIMIT_G} g (the chest ran out of room?)")
    if float(modern["r"].max()) > ROOM_M:
        problems.append("the chest of the modern belt ran out of room")
    if np.any(np.diff(modern["payout_m"]) < -1e-9):
        problems.append("webbing pay-out shrinks")
    below = modern["chest_g"][(modern["payout_m"] == 0.0) & (modern["t"] > 0)]
    if below.size and float(below.max()) > LIMIT_G + 0.5:
        problems.append("webbing was not paid out although the force passed the cap")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "peak_plain_g": round(p_plain, 1), "peak_modern_g": round(p_modern, 1),
            "max_travel_modern_m": round(float(modern["r"].max()), 3), "max_payout_m": round(float(modern["payout_m"].max()), 3)}
