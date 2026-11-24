"""EP.27 submersible bridge (pure Python + numpy): a road bridge at the mouth of the Corinth Canal that sinks instead of lifting.
Render-world frame: the canal runs along +y (from the sea at -y into the cut), the water surface is z = 0 and the road crosses along
x at y = 0. The steel deck (33 m by 7 m, two lanes, as the canal operator gives it) normally carries the road 1.2 m above the water;
for a ship it is lowered to 8 m below the surface (about 26 ft), into a pit in the canal bed (the canal is 8 m deep), at about 4 m a
minute with soft starts and stops, and raised again after the ship has passed. A tall ship (46 m, 3.8 m draft, masts 38 m above
the water) sails over it. The gate checks the claims in the film: the depth, the speed, that the road ends up almost on the bottom,
the room under the ship's keel, that nothing is above the water when the ship passes, and how tall a lift bridge's towers would have
to be for the same masts. Simplified explanation model, not the operator's figures for any one bridge."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

FT = 0.3048
Z_UP = 1.2                              # road surface when the bridge is up (m above the water)
Z_DOWN = -8.0                           # road surface when it is down
V_SINK = 4.0 / 60.0                     # m/s (about 13 ft a minute)
RAMP = 4.0                              # s to reach full speed (and to stop)
DECK_L, DECK_W = 33.0, 7.0              # along the road (across the canal), across the road (along the canal)
DECK_DEPTH = 1.6                        # steel box girders under the road surface
CANAL_W = 24.6                          # at the waterline
CANAL_BED = -8.5
PIT = -10.0                             # the pit the deck's girders sit in when down
T_DOWN0 = 0.0                           # the deck starts down
T_UP0 = 232.0                           # and starts back up
T_GATES_CLOSE = -40.0
SHIP_L, SHIP_BEAM, SHIP_DRAFT, MAST_H = 46.0, 8.2, 3.8, 38.0
SHIP_V = 2.0                            # m/s through the canal mouth
T_SHIP = 168.0                          # the ship's bow reaches the deck's near edge (y = -DECK_W / 2)
LIFT_CLEAR = 2.0                        # a lift bridge would have to hold its deck this far above the highest mast
LIFT_MACHINERY = 5.0                    # and its towers stand this far above the raised deck (sheaves, machinery)


@lru_cache(maxsize=None)
def _travel_profile():
    """Time from the start of a move to its end, and the distance done as a function of time (soft starts and stops)."""
    travel = Z_UP - Z_DOWN
    dt = 0.01

    def v_of(tau, total):
        def s(a):
            a = min(1.0, max(0.0, a))
            return a * a * (3 - 2 * a)
        return V_SINK * s(tau / RAMP) * s((total - tau) / RAMP)

    lo, hi = travel / V_SINK, travel / V_SINK + 3 * RAMP
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        d = sum(v_of(k * dt, mid) * dt for k in range(int(mid / dt) + 1))
        lo, hi = (mid, hi) if d < travel else (lo, mid)
    total = 0.5 * (lo + hi)
    ts = np.arange(0.0, total + dt, dt)
    vs = np.array([v_of(x, total) for x in ts])
    dist = np.concatenate([[0.0], np.cumsum(0.5 * (vs[1:] + vs[:-1]) * dt)])
    dist *= travel / dist[-1]
    return total, ts, dist, vs


def move_time() -> float:
    return _travel_profile()[0]


def deck_z(t: float) -> float:
    """Road surface height at story time t (s)."""
    total, ts, dist, _ = _travel_profile()
    if t <= T_DOWN0:
        return Z_UP
    if t <= T_DOWN0 + total:
        return Z_UP - float(np.interp(t - T_DOWN0, ts, dist))
    if t <= T_UP0:
        return Z_DOWN
    if t <= T_UP0 + total:
        return Z_DOWN + float(np.interp(t - T_UP0, ts, dist))
    return Z_UP


def deck_speed(t: float) -> float:
    """Signed vertical speed of the deck (m/s, + up)."""
    total, ts, _, vs = _travel_profile()
    if T_DOWN0 < t < T_DOWN0 + total:
        return -float(np.interp(t - T_DOWN0, ts, vs))
    if T_UP0 < t < T_UP0 + total:
        return float(np.interp(t - T_UP0, ts, vs))
    return 0.0


def t_gates_open() -> float:
    return T_UP0 + move_time() + 12.0


def gates_down(t: float) -> float:
    """0 = up (open), 1 = down (closed); the arms take 6 s to swing."""
    if t < T_GATES_CLOSE or t > t_gates_open() + 6.0:
        return 0.0
    if t < T_GATES_CLOSE + 6.0:
        u = (t - T_GATES_CLOSE) / 6.0
    elif t > t_gates_open():
        u = 1.0 - (t - t_gates_open()) / 6.0
    else:
        return 1.0
    return u * u * (3 - 2 * u)


def lights_on(t: float) -> bool:
    return T_GATES_CLOSE - 8.0 <= t <= t_gates_open() + 6.0


def ship_bow_y(t: float) -> float:
    return -DECK_W / 2 + SHIP_V * (t - T_SHIP)


def ship_over_deck(t: float) -> bool:
    bow = ship_bow_y(t)
    return bow > -DECK_W / 2 and bow - SHIP_L < DECK_W / 2


@lru_cache(maxsize=None)
def t_out() -> float:
    """When the rising road surface comes out of the water."""
    ts = np.linspace(T_UP0, T_UP0 + move_time(), 2000)
    zs = np.array([deck_z(x) for x in ts])
    return float(ts[int(np.searchsorted(zs, 0.0))])


def wet(t: float) -> float:
    """How wet the road surface looks: 1 under water and just out of it, drying over a few minutes."""
    if deck_z(t) < 0.0 and t > T_DOWN0:
        return 1.0
    if t > T_UP0 and t >= t_out():
        return math.exp(-(t - t_out()) / 150.0)
    return 0.0


def sinking_physics() -> dict:
    """Gate: the film's claims against the model."""
    total = move_time()
    problems = []
    depth_ft = -Z_DOWN / FT
    speed_ft_min = V_SINK * 60.0 / FT
    if not 24.0 <= depth_ft <= 28.0:
        problems.append(f"the road goes {depth_ft:.1f} ft under (narration: about twenty-six feet)")
    if not 12.0 <= speed_ft_min <= 14.0:
        problems.append(f"it sinks at {speed_ft_min:.1f} ft a minute (narration: about thirteen)")
    if not 0.0 < Z_DOWN - CANAL_BED <= 1.0:
        problems.append(f"the road stops {Z_DOWN - CANAL_BED:.1f} m above the canal bed (narration: almost on the bottom)")
    if Z_DOWN - DECK_DEPTH < PIT:
        problems.append("the deck's girders do not fit in the pit")
    ts = np.arange(T_SHIP - 30.0, T_SHIP + 60.0, 0.25)
    over = [t for t in ts if ship_over_deck(t)]
    if not over:
        problems.append("the ship never passes over the bridge")
    clear = min((-SHIP_DRAFT) - deck_z(t) for t in over) if over else -1.0
    if clear < 1.0:
        problems.append(f"only {clear:.1f} m under the ship's keel")
    if over and (max(deck_z(t) for t in over) > -SHIP_DRAFT - 1.0 or over[0] < T_DOWN0 + total or over[-1] > T_UP0):
        problems.append("the road is not all the way down while the ship is over it")
    if any(gates_down(t) < 1.0 for t in np.arange(T_DOWN0 - 1.0, T_UP0 + total + 1.0, 1.0)):
        problems.append("the gates are not down while the road is moving or under")
    tower = MAST_H + LIFT_CLEAR + LIFT_MACHINERY
    if not tower > MAST_H:
        problems.append("a lift bridge's towers would not have to be taller than the masts")
    if wet(t_out() + 5.0) < 0.9 or wet(T_UP0 + total) < 0.8:
        problems.append("the road does not come up dripping wet")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "depth_ft": round(depth_ft, 1), "depth_m": -Z_DOWN,
            "speed_ft_per_min": round(speed_ft_min, 1), "speed_m_per_min": round(V_SINK * 60, 2), "move_s": round(total, 1),
            "road_above_bed_m": round(Z_DOWN - CANAL_BED, 2), "keel_clearance_m": round(clear, 2), "ship_over_deck_s": round(len(over) * 0.25, 1),
            "mast_m": MAST_H, "lift_tower_m": tower, "gates_open_s": round(t_gates_open(), 1)}


if __name__ == "__main__":
    import json
    print(json.dumps(sinking_physics(), indent=1))
