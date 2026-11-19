"""EP.04 driver (crash-test-dummy style figure): how far the belted driver moves forward inside the cabin and how hard the belt and the steering wheel load the chest, computed from the
simulated deceleration of each car. Illustrative one-dimensional model, not a calibrated occupant model (no airbag, no pretensioner, no neck model); the film description says so.

Model: the torso (mass M) is held by a belt that acts like a spring-damper after a little slack; the cabin decelerates with the simulated pulse a(t). Relative to the cabin the torso moves
forward by r(t). If it travels further than REACH it meets the steering wheel (a much stiffer spring). The force on the chest divided by M*g is the chest load in g.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm

M = 75.0                 # kg torso + head + arms that the belt and the wheel have to stop
SLACK = 0.03             # m of belt slack before the belt takes load
K_BELT = 100_000.0       # N/m
C_BELT = 2_000.0         # N s/m
REACH = 0.21             # m of forward travel before the chest meets the steering wheel
K_WHEEL = 600_000.0      # N/m
C_WHEEL = 2_000.0
CHEST_OK_G = 25.0        # chest load below this reads as unharmed (green)
CHEST_SEVERE_G = 60.0    # the 60 g chest limit used in car-safety rules: at and above this the figure reads as severely loaded (red)
G = cm.G


@lru_cache(maxsize=None)
def response(profile: str) -> dict:
    """Occupant response on the time grid of the car simulation: forward travel r (m), chest load (g) and its running peak."""
    rec = cm.recs()[profile]
    t, a_car = rec["t"], rec["g"] * G
    r = rv = 0.0
    n = len(t)
    r_out, g_out = np.zeros(n), np.zeros(n)
    sub = 20
    for i in range(1, n):
        dt = (t[i] - t[i - 1]) / sub
        a_i = 0.5 * (a_car[i] + a_car[i - 1])
        for _ in range(sub):
            f = 0.0
            if r > SLACK:
                f += K_BELT * (r - SLACK) + (C_BELT * rv if rv > 0 else 0.0)
            if r > REACH:
                f += K_WHEEL * (r - REACH) + (C_WHEEL * rv if rv > 0 else 0.0)
            acc = a_i - f / M            # forward acceleration of the torso relative to the cabin
            rv += acc * dt
            r += rv * dt
            if r < 0.0:                  # pushed back into the seat
                r, rv = 0.0, max(rv, 0.0)
        r_out[i] = r
        g_out[i] = f / (M * G)
    return {"t": t, "r": r_out, "chest_g": g_out, "peak_g": np.maximum.accumulate(g_out)}


def at(profile: str, sim_time: float) -> dict:
    """Driver state at a simulated time: forward travel (m), chest load (g), running peak chest load (g) and the injury level 0..1 (0 = unharmed, 1 = severely loaded)."""
    res = response(profile)
    r = float(np.interp(sim_time, res["t"], res["r"]))
    g = float(np.interp(sim_time, res["t"], res["chest_g"]))
    peak = float(np.interp(sim_time, res["t"], res["peak_g"]))
    injury = float(np.clip((peak - CHEST_OK_G) / (CHEST_SEVERE_G - CHEST_OK_G), 0.0, 1.0))
    return {"travel_m": r, "chest_g": g, "peak_chest_g": peak, "injury": injury, "hits_wheel": r > REACH}


def pitch_rad(travel_m: float) -> float:
    """Forward lean of the torso for a forward travel of the chest (hip stays on the seat, the upper body hinges forward)."""
    return float(np.clip(travel_m / 0.55, 0.0, 1.1))


def head_extra_rad(chest_g: float) -> float:
    """Extra forward snap of the head on top of the torso lean (the neck lets the head swing further when the chest is stopped hard)."""
    return float(np.clip(chest_g / 120.0, 0.0, 0.7))
