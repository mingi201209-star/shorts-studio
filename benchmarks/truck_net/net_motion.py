"""EP.34 runaway-truck arrester nets (pure Python + numpy). Render-world coordinates: the escape ramp runs along +y between two
concrete walls (inner faces at x = +-WALL_X), level, pavement at z = 0. Eight net stations at y = NET_Y[i]. At each, a net of steel
cables hangs across the ramp from posts on the walls. Each side edge of the net is tied to two steel tapes (one low, one higher up),
each coiled in an energy absorber inside the wall. The absorber pulls its tape through offset pins that bend it back and forth, so
the tape pays out against a nearly constant tension T_TAPE.

A runaway semi enters the ramp at V0 and its front reaches net 1 at t = 0. A net it has picked up wraps its front. Each side of the
net runs from the truck's front corner back toward the tapes' exits at the wall (the net does not stretch). With the front d past
the net's station, each side's two tapes pull along that line, so the net holds the truck back with 4 T d / sqrt(s^2 + d^2), where s
is the net's side length from the wall to the truck's corner, and has paid out sqrt(s^2 + d^2) - s of each tape. More nets join as
the truck reaches them, and the truck slows until it stops; rolling resistance is small.

Simplified explanation model; not a product's test data."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
LB = 0.45359237
MPH = 0.44704
FT = 0.3048
TRUCK_LB = 80000.0               # the film's runaway semi, loaded
V0_MPH = 60.0
RATING_LB = 90000.0              # "built to stop a ninety-thousand-pound truck at ninety miles an hour" (TxDOT El Paso, WYDOT Teton Pass)
RATING_MPH = 90.0
WALL_X = 4.5                     # inner faces of the walls: a 30 ft wide ramp, the net width in WYDOT's examples
WALL_T = 0.9                     # wall thickness
WALL_H = 1.6
HALF_T = 1.3                     # half the truck's width (2.6 m)
S_SIDE = WALL_X - HALF_T         # the net's side, from the truck's corner to the wall
N_NETS = 8                       # TxDOT El Paso: eight net stations; WYDOT Teton Pass: eight nets
SPACING = 15.0
NET_Y = tuple(SPACING * i for i in range(N_NETS))
NET_Z = (0.30, 2.70)             # the net's bottom and top edges
TAPE_Z = (0.45, 1.35)            # the tapes' exits in the wall, low and high
T_TAPE = 18e3                    # N per tape (about 4,000 lb), nearly constant while it pays out
TAPES_PER_NET = 4
L_TAPE = 125.0                   # m of tape coiled in each absorber
RAMP_END = NET_Y[-1] + 45.0      # the paved ramp ends here (gravel run-out beyond)
ROLL = 0.012                     # rolling resistance (no brakes, no engine braking)
DT = 0.001


def net_force(d: float) -> float:
    """Backward force (N) of one net whose station the truck's front is d metres past."""
    if d <= 0.0:
        return 0.0
    return TAPES_PER_NET * T_TAPE * d / math.hypot(S_SIDE, d)


def payout(d: float) -> float:
    """Tape pulled out of each of a net's absorbers with the front d metres past the station."""
    return 0.0 if d <= 0.0 else math.hypot(S_SIDE, d) - S_SIDE


@lru_cache(maxsize=None)
def catch(mass_lb: float = TRUCK_LB, v_mph: float = V0_MPH) -> tuple:
    """Rows (t, x, v, a) from the front reaching net 1 (x = 0) until the truck stops: x is the front's position along the ramp."""
    m = mass_lb * LB
    x, v, t, rows = 0.0, v_mph * MPH, 0.0, []
    while True:
        f = sum(net_force(x - y) for y in NET_Y) + ROLL * m * G
        a = f / m
        rows.append((t, x, v, a))
        if v <= 0.0:
            break
        v = max(0.0, v - a * DT)
        x += v * DT
        t += DT
    return tuple(rows)


def stop_time(mass_lb: float = TRUCK_LB, v_mph: float = V0_MPH) -> float:
    return catch(mass_lb, v_mph)[-1][0]


def truck_state(t: float, rating: bool = False) -> dict:
    """The truck's front y, speed, deceleration, each net's d (front past its station) and tape payout at simulated time t (t < 0:
    still rolling in at full speed)."""
    mass, vmph = (RATING_LB, RATING_MPH) if rating else (TRUCK_LB, V0_MPH)
    if t < 0.0:
        v = vmph * MPH
        y, a = v * t, ROLL * G
    else:
        rows = catch(mass, vmph)
        i = min(len(rows) - 1, int(round(t / DT)))
        _, y, v, a = rows[i]
    d = [y - ny for ny in NET_Y]
    return {"t": t, "front_y": y, "speed": v, "decel_g": a / G, "d": d, "payout": [payout(x) for x in d],
            "engaged": sum(1 for x in d if x > 0.0), "force": sum(net_force(x) for x in d)}


def side_edge(d: float, y_net: float, side: int) -> tuple[float, float]:
    """Plan position (x, y) of a net's side edge (where its tapes are tied) with the front d past the station; side = +1 right, -1 left.
    Before the truck reaches it the edge sits at the wall; after, it lies on the line from the truck's corner to the tape exit, a side's
    length from the corner."""
    if d <= 0.0:
        return side * WALL_X, y_net
    L = math.hypot(S_SIDE, d)
    cx, cy = side * HALF_T, y_net + d
    return cx + side * S_SIDE * S_SIDE / L, cy - S_SIDE * d / L


def path_x(y: float) -> float:
    """The truck's lateral position: down the highway's right lane (x = ROAD_LANE), then a smooth move into the ramp (x = 0)."""
    a, b = -150.0, -60.0
    if y <= a:
        return ROAD_LANE
    if y >= b:
        return 0.0
    u = (y - a) / (b - a)
    return ROAD_LANE * (1.0 - u * u * (3 - 2 * u))


def heading(y: float) -> float:
    """Yaw of the truck (radians, positive = turning toward +x) from the slope of its path."""
    h = 0.5
    return math.atan2(path_x(y + h) - path_x(y - h), 2 * h)


ROAD_LANE = -12.0                # the highway's right lane, left of the ramp


def net_physics() -> dict:
    """Every claim of the narration, from the model."""
    problems = []
    rows = catch()
    t_stop, x_stop = rows[-1][0], rows[-1][1]
    st = truck_state(t_stop)
    if st["engaged"] < 3:
        problems.append(f"only {st['engaged']} nets catch the truck (narration: net after net)")
    peak = max(r[3] for r in rows) / G
    if peak > 1.5:
        problems.append(f"peak deceleration {peak:.2f} g (narration: gentle enough to protect the driver)")
    if x_stop > RAMP_END:
        problems.append("the truck runs off the end of the ramp")
    m = TRUCK_LB * LB
    e_in = 0.5 * m * (V0_MPH * MPH) ** 2
    e_tape = TAPES_PER_NET * T_TAPE * sum(st["payout"])
    e_roll = ROLL * m * G * x_stop
    if abs(e_tape + e_roll - e_in) / e_in > 0.02:
        problems.append("the energy bent out of the tapes does not match the truck's")
    rr = catch(RATING_LB, RATING_MPH)
    rs = truck_state(rr[-1][0], rating=True)
    if rr[-1][1] > RAMP_END:
        problems.append("the 90,000 lb truck at 90 mph runs off the end of the ramp")
    if max(rs["payout"]) > L_TAPE:
        problems.append(f"a tape runs out ({max(rs['payout']):.0f} m of {L_TAPE:.0f} m) in the rating case")
    r_peak = max(r[3] for r in rr) / G
    if r_peak > 2.0:
        problems.append(f"the rating case peaks at {r_peak:.2f} g")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "truck_lb": TRUCK_LB, "speed_mph": V0_MPH,
            "stop_s": round(t_stop, 2), "stop_ft": round(x_stop / FT), "nets_used": st["engaged"], "peak_g": round(peak, 2),
            "tape_out_max_ft": round(max(st["payout"]) / FT), "rating_lb": RATING_LB, "rating_mph": RATING_MPH,
            "rating_stop_ft": round(rr[-1][1] / FT), "rating_nets_used": rs["engaged"], "rating_peak_g": round(r_peak, 2),
            "rating_tape_out_max_ft": round(max(rs["payout"]) / FT), "tape_tension_lb": round(T_TAPE / G / LB)}


if __name__ == "__main__":
    import json
    print(json.dumps(net_physics(), indent=1))
