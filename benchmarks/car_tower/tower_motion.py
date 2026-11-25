"""EP.28 robotic car tower (pure Python + numpy): two glass silos next to a car factory (Wolfsburg's CarTowers: 48 m tall, 20 floors,
400 cars each), cars delivered from the factory through a tunnel, a robot on a central mast that turns, climbs at 2 m/s and slides
each car into its bay. Render-world frame: the hero tower stands at the origin, z = 0 is the ground, the tunnel and the transfer
station are under it. Each floor has 20 bays around the mast, cars lying along the radius; two lift carriages per tower, each
serving one half (180 degrees), as the sources describe.

The motion is a sequence of moves with trapezoid speed profiles (climb at up to 2 m/s with 1 m/s^2, turn at up to 30 deg/s, the
fork's stroke at 0.6 m/s) for the hero car's story: delivered through the tunnel, picked up, climbed to floor 16 while turning,
slid into its bay; later fetched for its buyer and brought down. The gate checks the claims in the film: almost seven feet a
second, 400 cars on 20 floors, the slowest fetch under two minutes (the record figure is 1 min 44 s), and the space saved without
ramps and lanes. Simplified explanation model, not the operator's control system."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

FT = 0.3048
N_FLOORS, N_BAYS = 20, 20
FLOOR_H = 2.3
Z_FLOOR0 = 1.6                          # floor 0's deck (ground level is 0)
Z_TRANSFER = -4.0                       # the transfer station under the tower, where the tunnel arrives
R_MAST = 2.0
R_HOME = 4.6                            # a car's centre on the retracted fork
R_BAY = 9.4                             # a stored car's centre
R_GLASS = 12.0
CAR_L, CAR_W = 4.6, 1.8
V_LIFT, A_LIFT = 2.0, 1.0               # m/s, m/s^2
W_TURN, A_TURN = math.radians(30.0), math.radians(30.0)
V_FORK = 0.6
LIFT_DZ = 0.12                          # the fork lifts a car this far off its bay's rails
RAIL_H = 0.12                           # the rails a stored car stands on, above its floor
T_LIFT_DZ = 1.0
V_TUNNEL = 1.5
TUNNEL_L = 700.0                        # the factory is about 700 m away through the tunnel (the film shows the last stretch)
HERO_FLOOR, HERO_BAY = 16, 6
SLOT_BAY = 9                            # one column of bays left empty in the hero silo: the cameras look in through it
T_ARRIVE = 0.0                          # the hero car arrives on the fork at the transfer station
T_FETCH = 200.0                         # its buyer has arrived: the robot goes to fetch it
RECORD_S = 104.0                        # the published worst-case fetch (1 min 44 s)
GARAGE_M2_PER_CAR = 25.0                # a ramped garage: the space plus its share of lanes and ramps (typical design figure)


def floor_z(k: int) -> float:
    return Z_FLOOR0 + k * FLOOR_H


def bay_angle(j: int) -> float:
    return math.radians((j + 0.5) * 360.0 / N_BAYS)


def trapezoid(dist: float, vmax: float, acc: float) -> tuple[float, callable]:
    """Duration and position(t) of a move of `dist` (>= 0) with a trapezoid (or triangle) speed profile."""
    if dist <= 0:
        return 0.0, lambda t: 0.0
    t_acc = vmax / acc
    d_acc = 0.5 * acc * t_acc * t_acc
    if 2 * d_acc >= dist:
        t_acc = math.sqrt(dist / acc)
        total = 2 * t_acc

        def pos(t):
            t = min(max(t, 0.0), total)
            return 0.5 * acc * t * t if t < t_acc else dist - 0.5 * acc * (total - t) ** 2
        return total, pos
    cruise = (dist - 2 * d_acc) / vmax
    total = 2 * t_acc + cruise

    def pos(t):
        t = min(max(t, 0.0), total)
        if t < t_acc:
            return 0.5 * acc * t * t
        if t < t_acc + cruise:
            return d_acc + vmax * (t - t_acc)
        return dist - 0.5 * acc * (total - t) ** 2
    return total, pos


def _moves(z0, th0, z1, th1):
    """Climb and turn at the same time; returns duration and a function t -> (z, theta)."""
    tz, pz = trapezoid(abs(z1 - z0), V_LIFT, A_LIFT)
    dth = (th1 - th0 + math.pi) % (2 * math.pi) - math.pi
    tt, pt = trapezoid(abs(dth), W_TURN, A_TURN)
    total = max(tz, tt)

    def at(t):
        return z0 + math.copysign(pz(t), z1 - z0), th0 + math.copysign(pt(t), dth)
    return total, at


def _fork_cycle(lift_first: bool):
    """Extend under the car, lift it off the bay's rails (pick) or set it down on them (place), retract: duration, t -> (r, dz)
    and the time at which the car changes hands (from bay to fork, or from fork to bay)."""
    t_ext, p_ext = trapezoid(R_BAY - R_HOME, V_FORK, 0.6)
    total = 2 * t_ext + T_LIFT_DZ

    def at(t):
        if t < t_ext:
            return R_HOME + p_ext(t), (0.0 if lift_first else LIFT_DZ)
        if t < t_ext + T_LIFT_DZ:
            u = (t - t_ext) / T_LIFT_DZ
            return R_BAY, LIFT_DZ * (u if lift_first else 1 - u)
        return R_BAY - p_ext(t - t_ext - T_LIFT_DZ), (LIFT_DZ if lift_first else 0.0)
    return total, at, t_ext + 0.5 * T_LIFT_DZ


@lru_cache(maxsize=None)
def schedule() -> list[dict]:
    """The hero carriage's moves: [{t0, t1, kind, ...}] (kinds: climb, place, pick)."""
    th_station = math.radians(270.0)                                   # the tunnel arrives from -y
    th_bay = bay_angle(HERO_BAY)
    z_bay = floor_z(HERO_FLOOR) + RAIL_H
    z_st = Z_TRANSFER + RAIL_H
    out, t = [], T_ARRIVE
    for z0, th0, z1, th1, carry, kind_after, t_next in ((z_st, th_station, z_bay, th_bay, True, "place", None),
                                                          (z_st, th_station, z_bay, th_bay, False, "pick", T_FETCH)):
        if t_next is not None:
            t = t_next
        d, f = _moves(z0, th0, z1, th1)
        out.append({"t0": t, "t1": t + d, "kind": "climb", "fn": f, "carry": carry})
        t += d
        d, f, t_hand = _fork_cycle(lift_first=(kind_after == "pick"))
        out.append({"t0": t, "t1": t + d, "kind": kind_after, "fn": f, "z": z1, "th": th1, "hand": t + t_hand})
        t += d
        d, f = _moves(z1, th1, z0, th0)
        out.append({"t0": t, "t1": t + d, "kind": "climb", "fn": f, "carry": kind_after == "pick"})
        t += d
    return out


def carriage(t: float) -> dict:
    """The hero carriage at story time t: the fork's height (top of its tines), heading, reach and lift, and where the hero car is
    ('tunnel', 'fork', 'bay' or 'station')."""
    sch = schedule()
    state = {"z": Z_TRANSFER + RAIL_H, "th": math.radians(270.0), "r": R_HOME, "dz": LIFT_DZ, "car": "tunnel" if t < T_ARRIVE else "fork"}
    for mv in sch:
        if t < mv["t0"]:
            break
        u = min(t, mv["t1"]) - mv["t0"]
        if mv["kind"] == "climb":
            z, th = mv["fn"](u)
            state.update(z=z, th=th, r=R_HOME, dz=LIFT_DZ if mv["carry"] else 0.0)
            state["car"] = "fork" if mv["carry"] else ("bay" if state["car"] in ("fork", "bay") else state["car"])
        else:
            r, dz = mv["fn"](u)
            state.update(z=mv["z"], th=mv["th"], r=r, dz=dz)
            handed = t >= mv["hand"]
            state["car"] = ("bay" if handed else "fork") if mv["kind"] == "place" else ("fork" if handed else "bay")
    if t >= sch[-1]["t1"]:
        state["car"] = "station"
    return state


def hero_car(t: float) -> dict:
    """World pose of the hero car: x, y, z (the bottom of its tyres), heading (where its nose points: inward, toward the mast)."""
    if t < T_ARRIVE:
        y = -R_HOME - V_TUNNEL * (T_ARRIVE - t)
        return {"x": 0.0, "y": y, "z": Z_TRANSFER + RAIL_H + LIFT_DZ, "heading": math.pi / 2, "where": "tunnel"}
    c = carriage(t)
    if c["car"] == "bay":
        th = bay_angle(HERO_BAY)
        return {"x": R_BAY * math.cos(th), "y": R_BAY * math.sin(th), "z": floor_z(HERO_FLOOR) + RAIL_H, "heading": th + math.pi, "where": "bay"}
    return {"x": c["r"] * math.cos(c["th"]), "y": c["r"] * math.sin(c["th"]), "z": c["z"] + c["dz"], "heading": c["th"] + math.pi, "where": c["car"]}


def fetch_time() -> float:
    sch = schedule()
    fetch = [m for m in sch if m["t0"] >= T_FETCH]
    return fetch[-1]["t1"] - T_FETCH


def worst_fetch() -> float:
    """From the transfer station to the farthest bay (top floor, half a turn away), pick, and back."""
    z_top = floor_z(N_FLOORS - 1) + RAIL_H
    d1, _ = _moves(Z_TRANSFER + RAIL_H, 0.0, z_top, math.pi - 1e-6)
    d2, _, _ = _fork_cycle(lift_first=True)
    return 2 * d1 + d2


def tower_physics() -> dict:
    problems = []
    ft_s = V_LIFT / FT
    if not 6.0 <= ft_s < 7.0:
        problems.append(f"the robot climbs {ft_s:.1f} ft a second (narration: almost seven)")
    cars = N_FLOORS * N_BAYS
    if cars != 400 or N_FLOORS != 20:
        problems.append(f"{cars} cars on {N_FLOORS} floors (narration: four hundred on twenty)")
    top = floor_z(N_FLOORS - 1) + FLOOR_H
    if not 44.0 <= top + 1.5 <= 50.0:
        problems.append(f"the tower is {top + 1.5:.0f} m tall (the towers are 48 m)")
    worst = worst_fetch()
    if not worst < 120.0 or not worst <= RECORD_S:
        problems.append(f"the slowest fetch takes {worst:.0f} s (narration: under two minutes; the record is 104 s)")
    gap = R_BAY - CAR_L / 2 - (math.hypot(R_HOME + CAR_L / 2, CAR_W / 2))
    if gap < 0.1:
        problems.append(f"a car turning on the fork comes within {gap:.2f} m of the stored cars")
    arc = 2 * math.pi * (R_BAY - CAR_L / 2) / N_BAYS
    if arc < CAR_W + 0.2:
        problems.append(f"the bays are only {arc:.2f} m wide at their inner end")
    if HERO_BAY == SLOT_BAY:
        problems.append("the hero car's bay is in the empty column")
    footprint = math.pi * R_GLASS ** 2
    per_car = footprint / cars
    if not per_car * 10 < GARAGE_M2_PER_CAR:
        problems.append("the tower does not pack cars much tighter than a ramped garage")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lift_m_s": V_LIFT, "lift_ft_s": round(ft_s, 2), "cars": cars,
            "floors": N_FLOORS, "height_m": round(top + 1.5, 1), "worst_fetch_s": round(worst, 1), "hero_fetch_s": round(fetch_time(), 1),
            "land_m2_per_car": round(per_car, 2), "garage_m2_per_car": GARAGE_M2_PER_CAR, "turn_clearance_m": round(gap, 2),
            "bay_width_inner_m": round(arc, 2)}


if __name__ == "__main__":
    import json
    print(json.dumps(tower_physics(), indent=1))
