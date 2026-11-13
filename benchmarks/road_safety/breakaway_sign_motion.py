"""Motion model for the breakaway sign post episode (pure Python, no Blender,
unit-tested).

TEST CONDITIONS (what every number in the film means)
  Two identical 1,500 kg cars at 25 m/s (90 km/h), no braking, no steering,
  each hit one steel sign post head-on with the centre of the bumper.
  Lane "rigid": the post is fixed in the ground and does not give.
  Lane "breakaway": the post stands on a slip base (two plates clamped by
  bolts in open notches) that releases when sheared.

What is modelled, and only this:

* Breakaway post: a rigid body (steel post plus sign panel) in the vertical
  plane of travel. The bumper strikes it BUMPER_HEIGHT above the ground.
  The impact is treated as a plastic impulse at that point: just afterwards
  the struck point moves at the car's speed. The impulse J follows from
  momentum and angular momentum:  1/m_eff = 1/m + d^2 / I  (d = height of the
  post's centre of mass above the struck point),  J = v0 * M m_eff / (M + m_eff).
  Releasing the slip base costs the car a further BASE_IMPULSE (assumption).
  The post then flies freely under gravity, spinning, until an end reaches
  the ground, where it stops (no bounce or slide is modelled).
* The car in the breakaway lane keeps the speed it has left (coasting).
* Rigid post: the car stops over RIGID_CRUSH metres at constant deceleration,
  a = v^2 / (2 d). RIGID_CRUSH is an ASSUMPTION (a narrow fixed object crushes
  deep into the front structure); it is an order-of-magnitude stand-in, not a
  measurement. The car body is not drawn deformed.
* Nose dive under braking: second-order pitch response, capped at the bump stops.

WHAT IS CHECKED, AND WHAT IS NOT
  Checked (summary and gates): the car's speed change against the limit used
  for breakaway supports (5 m/s; 3 m/s preferred) as recalled from roadside
  hardware test criteria, NOT re-read from the source in this session; the
  post clearing the car's hood and roof at every instant; the slip force lying
  between the wind load on the sign and the force of the impact; angular
  momentum bookkeeping. NOT done: comparison with a full-scale test.
  "physically_calibrated" stays False everywhere.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.81
CAR_MASS = 1500.0
SPEED = 25.0                # m/s (90 km/h)
BUMPER_HEIGHT = 0.50        # m, where the bumper meets the post
POST_LENGTH = 4.0           # m
POST_MASS = 55.0            # kg, steel post
PANEL_MASS = 14.0           # kg, sign panel
PANEL_HEIGHT = 3.45         # m, panel centre above the ground
PANEL_SIZE = 0.90           # m, side of the square panel
SLIP_PLANE = 0.08           # m above the ground
BASE_IMPULSE = 250.0        # N s the car loses shearing the slip base (ASSUMPTION)
SLIP_FORCE = 8000.0         # N, shear at which the base lets go (ASSUMPTION)
WIND_SPEED = 40.0           # m/s design gust for the wind check
FRONT_FACE = 0.15           # m behind the nose counted as the front face (bumper to hood edge)
RIGID_CRUSH = 0.80          # m, ASSUMED deceleration distance against a fixed post
DELTA_V_LIMIT = 5.0         # m/s, limit used for breakaway supports
DELTA_V_PREFERRED = 3.0
CG_HEIGHT = 0.55
PITCH_STIFFNESS = 150e3
PITCH_LIMIT = 0.06
PITCH_OMEGA = 2 * math.pi * 1.4
PITCH_ZETA = 0.45
START_NOSE = -8.0
STOPPED_SPEED = 0.5
DT = 1.0 / 2000.0
DURATION = 1.6

#: Car outline height (m) against distance behind the nose (m): hood, windscreen, roof, boot.
CAR_PROFILE = ((0.0, 0.62), (0.25, 0.78), (1.15, 0.84), (1.95, 1.26), (3.15, 1.26), (3.60, 0.98), (3.99, 0.92))


def post_inertia() -> tuple[float, float, float]:
    """Total mass, centre-of-mass height above the ground, moment of inertia about it."""
    post_cm = SLIP_PLANE + POST_LENGTH / 2.0
    m = POST_MASS + PANEL_MASS
    cm = (POST_MASS * post_cm + PANEL_MASS * PANEL_HEIGHT) / m
    inertia = (POST_MASS * POST_LENGTH ** 2 / 12.0 + POST_MASS * (cm - post_cm) ** 2
               + PANEL_MASS * PANEL_SIZE ** 2 / 12.0 + PANEL_MASS * (PANEL_HEIGHT - cm) ** 2)
    return m, cm, inertia


def impact() -> dict:
    m, cm, inertia = post_inertia()
    d = cm - BUMPER_HEIGHT
    m_eff = 1.0 / (1.0 / m + d * d / inertia)
    j = SPEED * CAR_MASS * m_eff / (CAR_MASS + m_eff)
    v_after = SPEED - (j + BASE_IMPULSE) / CAR_MASS
    return {"post_mass_kg": m, "cm_height_m": cm, "inertia_kgm2": inertia, "arm_m": d, "effective_mass_kg": m_eff,
            "impulse_Ns": j, "car_speed_after_mps": v_after, "post_cm_speed_mps": j / m, "post_spin_radps": j * d / inertia}


def car_height(behind_nose: float) -> float:
    """Height of the car outline `behind_nose` metres back from the nose; 0 outside the car."""
    if behind_nose < 0.0 or behind_nose > CAR_PROFILE[-1][0]:
        return 0.0
    for (x0, h0), (x1, h1) in zip(CAR_PROFILE, CAR_PROFILE[1:]):
        if x0 <= behind_nose <= x1:
            return h0 + (h1 - h0) * (behind_nose - x0) / (x1 - x0)
    return 0.0


@dataclass
class CarState:
    t: float
    nose: float          # along the lane, 0 = the post
    speed: float
    accel: float
    pitch: float         # rad, positive = nose down
    distance: float


@dataclass
class PostState:
    t: float
    released: bool
    y: float             # centre of mass along the lane
    z: float             # centre of mass height
    angle: float         # rad from upright; positive = the foot swings forward (and up)
    landed: bool


def simulate_car(case: str) -> list[CarState]:
    hit = impact()
    nose, v, t, pitch, rate, dist = START_NOSE, SPEED, 0.0, 0.0, 0.0, 0.0
    states = []
    rigid_decel = SPEED ** 2 / (2.0 * RIGID_CRUSH)
    struck = False
    for _ in range(int(DURATION / DT)):
        accel = 0.0
        if case == "rigid":
            if nose >= 0.0 and v > 0.0:
                accel = -rigid_decel
        elif not struck and nose >= 0.0:
            struck = True
            v = hit["car_speed_after_mps"]            # impulsive speed change at the post
        target = min(PITCH_LIMIT, CAR_MASS * (-accel) * CG_HEIGHT / PITCH_STIFFNESS)
        rate += (PITCH_OMEGA ** 2 * (target - pitch) - 2 * PITCH_ZETA * PITCH_OMEGA * rate) * DT
        pitch += rate * DT
        states.append(CarState(t, nose, v, accel, pitch, dist))
        v = max(0.0, v + accel * DT)
        nose += v * DT
        dist += v * DT
        t += DT
    return states


def contact_time(states: list[CarState]) -> float:
    return next(s.t for s in states if s.nose >= 0.0)


def post_points(p: PostState, n: int = 24) -> list[tuple[float, float]]:
    """(y, z) samples along the post from foot to top, then the panel edges."""
    _m, cm, _i = post_inertia()
    out = []
    for i in range(n + 1):
        h = SLIP_PLANE + POST_LENGTH * i / n          # height on the upright post
        r = h - cm                                    # signed distance from the centre of mass
        out.append((p.y - r * math.sin(p.angle), p.z + r * math.cos(p.angle)))
    return out


def simulate_post(car: list[CarState]) -> list[PostState]:
    hit = impact()
    _m, cm, _i = post_inertia()
    t_c = contact_time(car)
    y, z, angle = 0.0, cm, 0.0
    vy, vz, spin = 0.0, 0.0, 0.0
    released, landed = False, False
    states = []
    for s in car:
        if not released and s.t >= t_c:
            released = True
            vy, spin = hit["post_cm_speed_mps"], hit["post_spin_radps"]
        states.append(PostState(s.t, released, y, z, angle, landed))
        if released and not landed:
            vz -= G * DT
            y += vy * DT
            z += vz * DT
            angle += spin * DT
            probe = PostState(s.t, True, y, z, angle, False)
            if min(pz for _py, pz in post_points(probe, 8)) <= 0.03:
                landed = True
    return states


def sample(states: list, t: float):
    x = max(0.0, min(len(states) - 1.0, t / DT))
    i = int(x)
    j = min(len(states) - 1, i + 1)
    f = x - i
    a, b = states[i], states[j]
    values = {}
    for key, va in vars(a).items():
        vb = getattr(b, key)
        values[key] = (va if f < 0.5 else vb) if isinstance(va, bool) else va + (vb - va) * f
    return type(a)(**values)


def clearance(car: list[CarState], post: list[PostState], step: int = 10) -> dict:
    """Smallest gap between the flying post and the car outline, over the whole flight."""
    worst, when = 99.0, None
    for c, p in zip(car[::step], post[::step]):
        if not p.released or p.landed:
            continue
        for py, pz in post_points(p):
            behind = c.nose - py
            if behind < FRONT_FACE:    # the car's front face: that is the contact itself, not a fly-over
                continue
            h = car_height(behind)
            if h > 0.0 and pz - h < worst:
                worst, when = pz - h, c.t
    return {"min_clearance_m": round(worst, 3), "at_s": None if when is None else round(when, 4)}


def wind_shear() -> float:
    """Base shear from a design gust on the sign panel (drag coefficient 1.2)."""
    return 0.5 * 1.2 * WIND_SPEED ** 2 * PANEL_SIZE ** 2 * 1.2


def summary() -> dict:
    hit = impact()
    cars = {case: simulate_car(case) for case in ("rigid", "breakaway")}
    post = simulate_post(cars["breakaway"])
    t_c = contact_time(cars["breakaway"])
    land = next((p for p in post if p.landed), post[-1])
    car_at_land = sample(cars["breakaway"], land.t)
    rigid_stop = next((s for s in cars["rigid"] if s.speed <= STOPPED_SPEED), cars["rigid"][-1])
    gap = clearance(cars["breakaway"], post)
    m, cm, inertia = post_inertia()
    # angular momentum about the struck point just after impact must be zero
    # (the impulse acts through that point): L = I w - m v_cm d
    residual = inertia * hit["post_spin_radps"] - m * hit["post_cm_speed_mps"] * hit["arm_m"]
    return {
        "breakaway": {
            "contact_s": round(t_c, 4),
            "delta_v_mps": round(SPEED - hit["car_speed_after_mps"], 3),
            "speed_after_mps": round(hit["car_speed_after_mps"], 3),
            "speed_kept_fraction": round(hit["car_speed_after_mps"] / SPEED, 4),
            "post_cm_speed_mps": round(hit["post_cm_speed_mps"], 2),
            "post_spin_radps": round(hit["post_spin_radps"], 2),
            "struck_point_speed_mps": round(hit["post_cm_speed_mps"] + hit["post_spin_radps"] * hit["arm_m"], 2),
            "angular_momentum_residual": round(residual, 6),
            "post_landed_s": round(land.t, 4), "post_landed": bool(land.landed),
            "post_landing_y_m": round(land.y, 2),
            "car_tail_at_landing_m": round(car_at_land.nose - CAR_PROFILE[-1][0], 2),
            "post_turn_at_landing_deg": round(math.degrees(land.angle), 1),
            **gap,
            "slip_force_N": SLIP_FORCE, "wind_shear_N": round(wind_shear(), 1),
            "mean_impact_force_N": round(hit["impulse_Ns"] / 0.01, 1),
        },
        "rigid": {
            "stop_distance_m": round(rigid_stop.nose, 3),
            "stop_s": round(rigid_stop.t - t_c, 4),
            "avg_decel_g": round(SPEED ** 2 / (2.0 * RIGID_CRUSH) / G, 2),
            "delta_v_mps": round(SPEED - rigid_stop.speed, 2),
            "peak_pitch_deg": round(math.degrees(max(s.pitch for s in cars["rigid"])), 2),
        },
    }
