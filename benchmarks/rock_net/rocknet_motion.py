"""EP.21 rockfall ring-net barrier (pure Python + numpy). Render-world coordinates: a mountain road runs along +y at the foot of a
slope that rises toward +x at SLOPE degrees. Halfway up the slope a flexible barrier stands across it: posts every SPAN metres along
y, a net of interlocked steel rings between them, support ropes along the top and bottom, and retaining ropes from each post top to
anchors further up the slope. Every rope runs through a ring brake (a loop of steel tube held by a press sleeve): above a set pull the
loop shrinks as the tube slides through its sleeve, and the bending and friction turn the rock's energy into heat.

A 20 t boulder comes down the slope at 60 mph (26.8 m/s, 7.2 MJ: the top class of these barriers is rated 8,000 kJ) and hits the
middle span. Simulated time t = 0 at first contact. The rock's centre moves along the slope (d_hat) while the net in front of it
deflects: first the ring net and ropes take up the load (force rising with the square of the deflection), then the brakes slip at a
near-constant force; gravity along the slope keeps pushing. The rock stops after about 8 m (27 ft), springs back a little and comes to
rest in the net. The posts lean with the load. Simplified explanation model, not the data sheet of any product."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

MPH = 0.44704
FT = 0.3048
G = 9.81
SLOPE = math.radians(38.0)
X_TOE = 5.2                              # foot of the slope (the road edge is at 3.6)
UP = 22.0                                # barrier base, metres up the slope from the toe
X_B = X_TOE + UP * math.cos(SLOPE)
Z_B = UP * math.sin(SLOPE)
H_NET = 5.0                              # post / net height
SPAN = 10.0
POST_YS = (-15.0, -5.0, 5.0, 15.0)
ANCHOR_UP = 9.0                          # retaining-rope anchors, metres further up the slope
M = 20000.0                              # 20 t
DENSITY = 2700.0
R_ROCK = (3 * M / DENSITY / (4 * math.pi)) ** (1 / 3)
V0 = 60 * MPH
RATED_KJ = 8000.0                        # the top class of flexible rockfall barriers
HIT_Y, HIT_H = 0.0, 2.5                  # impact point: middle of the middle span, 2.5 m up the net
W_B = 3.0                                # deflection where the brakes start to slip (m)
F_B = 1.2e6                              # brake slip force on the rock (N)
K2 = 40e3                                # slight hardening while the brakes run (N/m)
BRAKE_SHARE = 0.25                       # brake slip per metre of deflection beyond W_B
LOOP_R0 = 0.35                           # brake loop radius when new (m)
REBOUND = 0.08                           # the net springs back by this share of the peak deflection
REBOUND_TAU = 0.25
ROLL_T = 1.0                             # the rock leaves a bump this long before the hit and flies into the net


def d_hat() -> np.ndarray:
    """Unit direction down the slope (the rock's path and the net's deflection)."""
    return np.array([-math.cos(SLOPE), 0.0, -math.sin(SLOPE)])


def slope_z(x: float) -> float:
    return max(0.0, (x - X_TOE) * math.tan(SLOPE))


def net_force(w: float) -> float:
    if w <= 0:
        return 0.0
    if w < W_B:
        return F_B * (w / W_B) ** 2
    return F_B + K2 * (w - W_B)


def net_energy(w: float) -> float:
    if w <= 0:
        return 0.0
    if w < W_B:
        return F_B * w ** 3 / (3 * W_B ** 2)
    u = w - W_B
    return F_B * W_B / 3 + F_B * u + K2 * u * u / 2


@lru_cache(maxsize=None)
def _catch() -> dict:
    dt = 2e-5
    t, w, v = 0.0, 0.0, V0
    ts, ws, vs = [0.0], [0.0], [V0]
    g_along = G * math.sin(SLOPE)
    while v > 0 and t < 5:
        a = g_along - net_force(w) / M
        v_new = v + a * dt
        if v_new <= 0:
            t += v / -a
            w += v * v / (2 * -a)
            v = 0.0
        else:
            w += (v + v_new) / 2 * dt
            v = v_new
            t += dt
        ts.append(t)
        ws.append(w)
        vs.append(v)
    return {"t": np.array(ts), "w": np.array(ws), "v": np.array(vs), "stop_t": t, "w_max": w}


def stop_time() -> float:
    return _catch()["stop_t"]


def w_max() -> float:
    return _catch()["w_max"]


def deflection(t: float) -> float:
    """Net deflection at the impact point along d_hat (m)."""
    if t <= 0:
        return 0.0
    c = _catch()
    if t <= c["stop_t"]:
        return float(np.interp(t, c["t"], c["w"]))
    tau = t - c["stop_t"]
    return c["w_max"] * (1.0 - REBOUND * (1.0 - math.exp(-tau / REBOUND_TAU)))


def rock_speed(t: float) -> float:
    if t <= 0:
        return V0
    c = _catch()
    return float(np.interp(t, c["t"], c["v"])) if t <= c["stop_t"] else 0.0


def brake_slip(t: float) -> float:
    """How far each brake has run (m of tube through its sleeve); brakes never run back."""
    w = deflection(min(t, stop_time()))
    return BRAKE_SHARE * max(0.0, w - W_B)


def loop_radius(t: float) -> float:
    return LOOP_R0 - brake_slip(t) / (2 * math.pi)


def brake_power(t: float) -> float:
    """Power the brakes are turning into heat (W): slip force x slip speed (for the glow)."""
    if t <= 0 or t >= stop_time():
        return 0.0
    w = deflection(t)
    if w < W_B:
        return 0.0
    return net_force(w) * rock_speed(t)


def contact_point() -> np.ndarray:
    """Where the rock's front first touches the net (on the net plane x = X_B)."""
    return np.array([X_B, HIT_Y, Z_B + HIT_H])


def rock_center(t: float) -> np.ndarray:
    """Centre of the rock. Its path runs parallel to the slope; before the hit it rolls (resting on the slope), hops off a bump
    ROLL_T s before the hit and flies into the net 2.5 m up."""
    d = d_hat()
    c0 = contact_point() - R_ROCK * d
    if t >= 0:
        return c0 + deflection(t) * d
    p = c0 + (V0 * t) * d
    h_roll = R_ROCK / math.cos(SLOPE)
    h_hit = c0[2] - slope_z(c0[0])
    if t <= -ROLL_T:
        h = h_roll
    else:
        tau = (t + ROLL_T) / ROLL_T
        h = h_roll + (h_hit - h_roll) * tau + 1.6 * tau * (1 - tau)
    p[2] = slope_z(p[0]) + h
    return p


def rock_spin(t: float) -> float:
    """Rolling angle about the y axis (rad): rolls while on the slope, keeps spinning in the air, stops in the net."""
    if t <= -ROLL_T:
        return V0 * t / R_ROCK
    if t <= 0:
        return V0 * t / R_ROCK
    return 0.6 * (1 - math.exp(-t / 0.15))


def post_lean(t: float) -> float:
    """Downslope lean of the posts (rad), following the rope load."""
    w = deflection(t)
    f = net_force(min(w, w_max())) if t <= stop_time() else net_force(w)
    return math.radians(12.0) * min(1.0, f / net_force(w_max()))


def state(t: float, variant: str = "catch") -> dict:
    c = rock_center(t)
    return {"t": t, "variant": variant, "w": deflection(t), "rock_x": float(c[0]), "rock_y": float(c[1]), "rock_z": float(c[2]),
            "speed": rock_speed(t), "slip": brake_slip(t), "loop_r": loop_radius(t), "lean": post_lean(t), "power": brake_power(t)}


def rocknet_physics() -> dict:
    problems = []
    ke = 0.5 * M * V0 * V0
    if not abs(M - 20000) < 1 or round(V0 / MPH) != 60:
        problems.append("the rock is not 20 t at 60 mph (narration)")
    if ke / 1e3 > RATED_KJ:
        problems.append(f"{ke / 1e3:.0f} kJ is more than the top rating {RATED_KJ:.0f} kJ")
    wm = w_max()
    if not 20 * FT < wm < 15.0:
        problems.append(f"braking distance {wm:.1f} m (narration: more than twenty feet; tests allow up to about 15 m)")
    work = net_energy(wm)
    gravity = M * G * math.sin(SLOPE) * wm
    if abs(work - (ke + gravity)) / ke > 0.01:
        problems.append(f"energy does not balance: net {work / 1e3:.0f} kJ vs {(ke + gravity) / 1e3:.0f} kJ")
    brakes = work - net_energy(W_B)
    if brakes / work < 0.6:
        problems.append(f"the brakes take only {brakes / work:.0%} of the energy")
    if loop_radius(10.0) < 0.08:
        problems.append("a brake loop closes up completely")
    fpk = net_force(wm)
    peak_g = fpk / M / G
    gentle = M * V0 * V0 / (2 * 0.3) / 1e6                         # the force if the same rock stopped in 0.3 m (a rigid wall)
    if fpk / 1e6 > gentle / 5:
        problems.append("the slow stop does not keep the force far below a rigid stop")
    lowest = rock_center(10.0)
    if lowest[0] - R_ROCK < X_TOE + 2.0:
        problems.append("the caught rock reaches the road")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "kinetic_kj": round(ke / 1e3), "rated_kj": RATED_KJ,
            "braking_m": round(wm, 2), "braking_ft": round(wm / FT, 1), "stop_s": round(stop_time(), 3), "peak_force_kN": round(fpk / 1e3),
            "peak_g": round(peak_g, 1), "rigid_stop_force_MN": round(gentle, 1), "brakes_share": round(brakes / work, 3),
            "brake_slip_m": round(brake_slip(10.0), 2), "rock_radius_m": round(R_ROCK, 2)}


if __name__ == "__main__":
    import json
    print(json.dumps(rocknet_physics(), indent=1))
