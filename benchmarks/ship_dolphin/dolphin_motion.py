"""EP.33 ship-impact protection for a bridge pier (pure Python + numpy). Render-world coordinates: sea level at z = 0, the shipping channel
along +y (ships travel toward +y), the bridge deck along x over y = 0. The main pier's footing stands at the origin; in front of it,
on the channel side, an arc of dolphins: round islands, each a steel sheet-pile ring driven into the sea bed, packed with crushed rock
and capped with concrete.

A design ship (87,000 t) drifts off course at 6 knots straight at the middle dolphin; its bow touches the dolphin's front at t = 0. The
contact force grows with the total give, bow crumpling plus the ring denting in, F = F_MAX (1 - exp(-d / D0)), and slows the ship until
it stops; 60 % of the give is the bow, 40 % the ring. The peak force stays under the dolphin's capacity (nearly thirty million pounds)
and the bow stops tens of metres short of the pier. Simplified explanation model; not a ship-collision analysis."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
KNOT = 0.514444
LBF = 4.448222
TONNE = 1000.0
V0 = 6.0 * KNOT
SHIP_MASS = 87000 * TONNE
SHIP_L, SHIP_B, SHIP_DRAFT, SHIP_FREEBOARD = 200.0, 32.0, 11.0, 8.0
F_MAX = 125e6                    # N: what the bow and the ring can push back with when fully engaged
D0 = 1.2                         # m of give for the force to build up
BOW_SHARE = 0.6
CAPACITY_LBF = 30e6              # "nearly thirty million pounds of force" (the dolphins' design figure)
# the dolphins: radius, cap height above the sea, sea bed depth, ring tip depth; the arc around the pier
DOL_R = 9.0
CAP_TOP = 4.0
SEA_BED = -12.0
TIP = -24.0
ROCK_TONS = 6700.0               # "up to six thousand seven hundred tons of crushed rock" (fill design figure)
ROCK_DENSITY = 1.6               # t per m3 of packed crushed rock
ARC_R = 46.0
ARC_DEG = (215.0, 242.5, 270.0, 297.5, 325.0)
HIT = 2                          # the middle one, straight upstream of the pier
PIER_HALF = (20.0, 11.0)         # the pier footing's half size (x, y)
DT = 0.001


def dolphin_centres() -> list[tuple[float, float]]:
    return [(ARC_R * math.cos(math.radians(a)), ARC_R * math.sin(math.radians(a))) for a in ARC_DEG]


def contact_y() -> float:
    return dolphin_centres()[HIT][1] - DOL_R


def force(d: float) -> float:
    return F_MAX * (1.0 - math.exp(-max(d, 0.0) / D0))


@lru_cache(maxsize=None)
def collision():
    """Rows (t, give d, speed v, force F) from first touch until the ship stops."""
    d, v, t, rows = 0.0, V0, 0.0, []
    while v > 0.0:
        f = force(d)
        rows.append((t, d, v, f))
        v = max(0.0, v - f / SHIP_MASS * DT)
        d += v * DT
        t += DT
    rows.append((t, d, 0.0, force(d)))
    return tuple(rows)


def _at(t: float):
    rows = collision()
    i = min(len(rows) - 1, max(0, int(round(t / DT))))
    return rows[i]


def ship_state(t: float) -> dict:
    """The bow's y (its tip at the waterline before any crumpling), the give split into bow and ring, speed and force."""
    y0 = contact_y()
    if t < 0:
        return {"t": t, "bow_y": y0 + V0 * t, "give": 0.0, "bow_crush": 0.0, "ring_dent": 0.0, "speed": V0, "force": 0.0}
    _, d, v, f = _at(t)
    return {"t": t, "bow_y": y0 + d, "give": d, "bow_crush": BOW_SHARE * d, "ring_dent": (1 - BOW_SHARE) * d, "speed": v,
            "force": f if v > 0 else force(d) * math.exp(-(t - collision()[-1][0]) / 0.4)}


def rock_volume_tons() -> float:
    """Crushed rock the ring holds from the sea bed to under the cap (the cap is 1.5 m of concrete)."""
    h = (CAP_TOP - 1.5) - SEA_BED
    return math.pi * DOL_R ** 2 * h * ROCK_DENSITY


N_SPRAY = 150
SPARK_LIFE = 0.3


@lru_cache(maxsize=None)
def spray() -> tuple:
    """Water thrown up where the bow meets the dolphin and chips of concrete from the cap: (spawn time, position, velocity, size, kind)."""
    rng = np.random.default_rng(3333)
    cx, cy = dolphin_centres()[HIT]
    out = []
    for k in range(N_SPRAY):
        kind = "chip" if k < 30 else "water"
        tb = float(rng.uniform(0.0, 1.4 if kind == "water" else 0.4))
        a = rng.uniform(-1.2, 1.2)
        pos = np.array([cx + DOL_R * math.sin(a) * 0.9, cy - DOL_R * math.cos(a) * 0.9, rng.uniform(0.5, 3.8) if kind == "chip" else 0.3])
        vel = np.array([math.sin(a) * rng.uniform(2.0, 8.0), -rng.uniform(1.5, 7.0), rng.uniform(5.0, 15.0)])
        size = rng.uniform(0.4, 1.0) if kind == "chip" else rng.uniform(0.8, 2.2)
        out.append((tb, pos, vel, size, kind))
    return tuple(out)


def spray_pose(k: int, t: float):
    tb, p0, v0, size, kind = spray()[k]
    tau = t - tb
    if tau < 0:
        return None
    p = p0 + v0 * tau + np.array([0.0, 0.0, -0.5 * G * tau * tau])
    floor = CAP_TOP + size / 2 if kind == "chip" and np.hypot(p[0] - dolphin_centres()[HIT][0], p[1] - dolphin_centres()[HIT][1]) < DOL_R else size / 2
    if p[2] < floor:
        return None if kind == "water" else (np.array([p[0], p[1], floor]), False)
    return p, True


def airborne_count(t: float) -> int:
    return sum(1 for k in range(N_SPRAY) if (p := spray_pose(k, t)) is not None and p[1])


def dolphin_physics() -> dict:
    """Every number the narration says, from the model."""
    problems = []
    rows = collision()
    t_stop, d_stop = rows[-1][0], rows[-1][1]
    peak = max(r[3] for r in rows)
    if peak / LBF > CAPACITY_LBF:
        problems.append(f"the peak force {peak / LBF / 1e6:.1f} million lb is over the dolphin's capacity")
    if peak / LBF < 0.8 * CAPACITY_LBF:
        problems.append(f"the peak force {peak / LBF / 1e6:.1f} million lb is not near thirty million")
    bow_stop = contact_y() + d_stop
    gap = -PIER_HALF[1] - bow_stop
    if gap < 20.0:
        problems.append(f"the ship stops only {gap:.1f} m from the pier (narration: before it ever touches the pier)")
    e_in = 0.5 * SHIP_MASS * V0 ** 2
    e_abs = sum(r[3] * (rows[i + 1][1] - r[1]) for i, r in enumerate(rows[:-1]))
    if abs(e_abs - e_in) / e_in > 0.02:
        problems.append("the energy soaked up by the bow and the ring does not match the ship's")
    tons = rock_volume_tons()
    if not 0.85 * ROCK_TONS <= tons <= 1.05 * ROCK_TONS:
        problems.append(f"the ring holds {tons:.0f} t of rock (narration: up to 6,700)")
    if not 0 < BOW_SHARE < 1:
        problems.append("the bow and the ring do not both give")
    for k in range(N_SPRAY):
        for t in np.arange(0.0, 4.0, 0.02):
            p = spray_pose(k, float(t))
            if p is not None and p[0][2] < spray()[k][3] / 2 - 1e-6:
                problems.append(f"spray piece {k} goes below the surface")
                break
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "ship_t": round(SHIP_MASS / TONNE), "speed_knots": 6.0,
            "energy_MJ": round(e_in / 1e6), "give_m": round(d_stop, 2), "bow_crush_m": round(BOW_SHARE * d_stop, 2),
            "ring_dent_m": round((1 - BOW_SHARE) * d_stop, 2), "stop_s": round(t_stop, 2), "peak_million_lb": round(peak / LBF / 1e6, 1),
            "gap_to_pier_m": round(gap, 1), "rock_t": round(tons)}


if __name__ == "__main__":
    import json
    print(json.dumps(dolphin_physics(), indent=1))
