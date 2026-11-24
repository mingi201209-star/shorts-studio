"""EP.25 drawbridge (Chicago-type double-leaf trunnion bascule), pure Python + numpy. Render-world coordinates: a river runs along +y
between embankment walls at x = +-WALL_X; the street crosses it along x at road level z = 0. Each leaf turns about a trunnion (a
steel shaft along y) at x = +-TRUNNION_X, z = TRUNNION_Z: over the river the leaf reaches LEAF_L to the middle of the river, where it
meets the other leaf; behind the trunnion a short tail carries the counterweight, which hangs in a pit under the street.

The leaf and the counterweight are one rigid seesaw. Their masses are set so that the combined centre of mass sits almost exactly on
the trunnion's axis, a little toward the river (the leaf closes by itself): gravity then makes almost no torque at any angle, and
the motors only have to overcome the small imbalance, the trunnion friction and the inertia of the start and stop. The opening is
the operator's smooth profile: a slow start, an even swing, a slow stop at OPEN_DEG after about a minute.

Gate figures: the peak power that profile needs from the motors of one leaf (with the counterweight), the same opening without the
counterweight, the balance, and the time. Simplified explanation model with generic masses of a big Chicago bascule, not the data of
any one bridge."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
HP = 745.7
WALL_X = 34.0                            # river walls
TRUNNION_X = 35.0                        # pivot axis, just behind the wall
TRUNNION_Z = -3.0                        # below the road surface
LEAF_L = 35.0                            # trunnion to the tip (the tips meet at x = 0)
TAIL_L = 8.5                             # trunnion to the back of the tail
M_LEAF = 3.6e6                           # leaf: deck, trusses, railings (kg) - "thousands of tons"
D_LEAF = 15.5                            # its centre of mass from the axis, toward the river (m)
Z_LEAF = 1.8                             # ... and above the axis (m): the deck is on top
K_LEAF = 9.6                             # radius of gyration about its own centre (m)
M_CW = 9.0e6                             # counterweight (kg): heavier than the leaf
K_CW = 2.6
IMBALANCE = 0.003                        # the leaf is 0.3 % heavier in moment than the counterweight: it closes by itself
D_CW = M_LEAF * D_LEAF * (1 - IMBALANCE) / M_CW      # counterweight arm behind the axis
Z_CW = -M_LEAF * Z_LEAF / M_CW                       # counterweight below the axis so the combined centre sits on it
MU = 0.004                               # trunnion bearing friction
R_TRUNNION = 0.45
OPEN_DEG = 78.0
T_OPEN = 60.0                            # "in about a minute"
T_RAMP = 14.0                            # slow start and slow stop
MOTORS_HP = 2 * 108.0                    # two 108 hp motors per leaf
I_SYS = M_LEAF * (D_LEAF ** 2 + Z_LEAF ** 2 + K_LEAF ** 2) + M_CW * (D_CW ** 2 + Z_CW ** 2 + K_CW ** 2)

# the story's clock (s): gates down, the leaves rise, a sailboat passes, the leaves come down, the gates go up
T_GATES = -18.0
T_UP = 0.0
T_SHIP = (62.0, 152.0)
T_DOWN = 160.0
T_GATES_UP = T_DOWN + T_OPEN + 8.0
SHIP_Y = (-160.0, 160.0)
SHIP_X = -6.0


def _profile(tau: float) -> tuple[float, float, float]:
    """Angle (rad), speed (rad/s), acceleration (rad/s^2) tau seconds into an opening (trapezoidal speed with eased ramps)."""
    th_max = math.radians(OPEN_DEG)
    w = th_max / (T_OPEN - T_RAMP)
    if tau <= 0:
        return 0.0, 0.0, 0.0
    if tau >= T_OPEN:
        return th_max, 0.0, 0.0

    def ramp_pos(u):                                 # integral of the eased speed share over a ramp (u in 0..1)
        return u ** 3 - 0.5 * u ** 4                 # speed share 3u^2 - 2u^3, its integral u^3 - u^4/2

    if tau < T_RAMP:
        u = tau / T_RAMP
        return w * T_RAMP * ramp_pos(u), w * (3 * u * u - 2 * u ** 3), w * (6 * u - 6 * u * u) / T_RAMP
    if tau <= T_OPEN - T_RAMP:
        return w * T_RAMP * 0.5 + w * (tau - T_RAMP), w, 0.0
    u = (T_OPEN - tau) / T_RAMP
    return th_max - w * T_RAMP * ramp_pos(u), w * (3 * u * u - 2 * u ** 3), -w * (6 * u - 6 * u * u) / T_RAMP


def angle(t: float) -> float:
    """Leaf angle (rad) at story time t: up from T_UP, down from T_DOWN."""
    if t < T_DOWN:
        return _profile(t - T_UP)[0]
    return math.radians(OPEN_DEG) - _profile(t - T_DOWN)[0]


def angular_speed(t: float) -> float:
    if t < T_DOWN:
        return _profile(t - T_UP)[1]
    return -_profile(t - T_DOWN)[1]


RACK_R, PINION_R = 6.5, 0.6              # the curved rack on the tail and the pinion that drives it (m)
CW_BOX = ((-11.2, -2.2), (-3.2, 2.3))     # the counterweight block drawn in the film: (u from, to), (v from, to) in the leaf's frame


def pinion_angle(theta: float) -> float:
    """Turn of the pinion (rad) for a leaf angle theta: the rack's pitch circle rolls on the pinion's."""
    return -theta * (RACK_R + 0.11) / (PINION_R + 0.1)


def cw_lowest_z(theta: float) -> float:
    """Lowest point of the counterweight block (m, world z) at leaf angle theta: it swings down into the pit as the road goes up."""
    return TRUNNION_Z + min(u * math.sin(theta) + v * math.cos(theta) for u in CW_BOX[0] for v in CW_BOX[1])


def gate_down(t: float) -> float:
    """How far the traffic gates are down (0 up, 1 down): 4 s to lower at T_GATES, 4 s to raise at T_GATES_UP."""
    if T_GATES <= t < T_GATES_UP:
        return min(1.0, (t - T_GATES) / 4.0)
    if t >= T_GATES_UP:
        return max(0.0, 1.0 - (t - T_GATES_UP) / 4.0)
    return 0.0


def gravity_torque(theta: float, with_cw: bool = True) -> float:
    """Torque of gravity trying to lower the leaf (N m) at angle theta (leaf and counterweight as one rigid seesaw)."""
    m_d = M_LEAF * (D_LEAF * math.cos(theta) - Z_LEAF * math.sin(theta))
    if with_cw:
        m_d += M_CW * (-D_CW * math.cos(theta) - Z_CW * math.sin(theta))
    return G * m_d


@lru_cache(maxsize=None)
def opening(with_cw: bool = True) -> dict:
    """Motor torque and power through one opening."""
    i_sys = I_SYS if with_cw else M_LEAF * (D_LEAF ** 2 + Z_LEAF ** 2 + K_LEAF ** 2)
    weight = G * (M_LEAF + (M_CW if with_cw else 0.0))
    ts = np.linspace(0.0, T_OPEN, 2401)
    th, w, a = (np.array(v) for v in zip(*[_profile(float(x)) for x in ts]))
    tg = np.array([gravity_torque(float(x), with_cw) for x in th])
    tf = MU * weight * R_TRUNNION * np.sign(w)
    tau = i_sys * a + tg + tf
    p = tau * w
    return {"t": ts, "theta": th, "w": w, "torque": tau, "power": p, "peak_kw": float(p.max()) / 1e3, "peak_hp": float(p.max()) / HP,
            "energy_kj": float(np.trapezoid(np.clip(p, 0, None), ts)) / 1e3}


def ship_y(t: float) -> float:
    a, b = T_SHIP
    u = min(1.0, max(0.0, (t - a) / (b - a)))
    return SHIP_Y[0] + (SHIP_Y[1] - SHIP_Y[0]) * u


def gates_down(t: float) -> bool:
    return T_GATES <= t < T_GATES_UP


def state(t: float) -> dict:
    th = angle(t)
    return {"t": t, "theta": th, "theta_deg": math.degrees(th), "omega": angular_speed(t), "gates_down": gates_down(t), "ship_y": ship_y(t),
            "ship_moving": T_SHIP[0] < t < T_SHIP[1]}


def bascule_physics() -> dict:
    """Gate: balanced like a seesaw, the counterweight heavier than the leaf, open in about a minute on two 108 hp motors; the same
    opening without the counterweight would need about a hundred times the power."""
    problems = []
    w = opening(True)
    wo = opening(False)
    balance = abs(M_LEAF * D_LEAF - M_CW * D_CW) / (M_LEAF * D_LEAF)
    if not M_CW > M_LEAF:
        problems.append("the counterweight is not heavier than the leaf")
    if not 0 < balance < 0.01:
        problems.append(f"the seesaw is not balanced within 1 % ({balance:.4f})")
    if gravity_torque(0.0) <= 0 or gravity_torque(math.radians(OPEN_DEG)) <= 0:
        problems.append("the leaf would not come down by itself")
    if w["peak_hp"] > MOTORS_HP:
        problems.append(f"one opening needs {w['peak_hp']:.0f} hp, more than two 108 hp motors")
    if not 45 <= T_OPEN <= 75:
        problems.append("the opening does not take about a minute")
    ratio = wo["peak_hp"] / w["peak_hp"]
    if ratio < 50:
        problems.append(f"without the counterweight it needs only {ratio:.0f} times the power")
    if not 75 <= OPEN_DEG <= 85:
        problems.append("the leaves do not stand nearly upright")
    if not T_SHIP[0] > T_OPEN or not T_SHIP[1] < T_DOWN:
        problems.append("the ship passes before the leaves are up or after they start down")
    return {
        "status": "FAIL" if problems else "PASS", "problems": problems,
        "leaf_tons": round(M_LEAF / 1000), "counterweight_tons": round(M_CW / 1000), "counterweight_arm_m": round(D_CW, 2),
        "leaf_arm_m": D_LEAF, "imbalance_share": round(balance, 4), "open_deg": OPEN_DEG, "open_s": T_OPEN,
        "peak_power_hp": round(w["peak_hp"], 1), "motors_hp": MOTORS_HP, "energy_per_opening_kj": round(w["energy_kj"]),
        "peak_power_without_counterweight_hp": round(wo["peak_hp"]), "times_more_without": round(ratio),
        "closing_torque_knm": round(gravity_torque(0.0) / 1e3),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(bascule_physics(), indent=1))
