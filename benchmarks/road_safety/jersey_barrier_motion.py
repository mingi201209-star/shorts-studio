"""Vehicle motion for the Jersey barrier episode, computed instead of
hand-keyed.

The previous cut animated the car with interpolated positions and a
whole-body roll. Viewer feedback: the contact was not shown clearly, tyre,
suspension and body did not move as one mechanism, and nothing on screen
explained what the sloped face does. This module replaces the hand keys with
a small deterministic simulation, so every pose the renderer draws comes
from the same equations and the QA gates can read the same numbers the
picture was drawn from.

Model (pure Python, no Blender, unit-testable):

* Planar single-track ("bicycle") model with a linear tyre: states are world
  position, heading, forward speed u, lateral speed v and yaw rate r.
* Four independent quarter-car suspensions: each sprung corner follows its
  wheel through a spring and damper.
* Jersey barrier: a barrier-side tyre whose outer edge passes the toe is
  lifted by the profile (75 mm reveal, then the 55 degree lower slope). The
  slope pushes back along its normal, so the sideways force on the tyre is
  the tyre's vertical load times tan(55 deg): the higher the wheel is pushed
  into its suspension, the harder the slope steers it away. That is the
  mechanism the film explains.
* Flat wall: nothing lifts. The first thing to arrive is the body corner; a
  stiff contact pushes it back and concrete-on-steel friction drags along the
  side.
* After a short reaction time a simple driver model steers back to the lane.

What this is NOT: a validated crash simulation. No tyre deflection, no body
deformation, no load transfer, linear tyres. It is a first-principles
kinematic/dynamic sketch that keeps the motion mutually consistent (no
sideways sliding, lift proportional to incursion, force proportional to
load). Parameters are ordinary passenger-car textbook values, not measured
from any specific vehicle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- New Jersey safety-shape profile, traffic side, metres ---------------
# Offsets are measured from the toe (the bottom edge facing traffic) toward
# the barrier's centreline; heights from the road.
REVEAL_HEIGHT = 0.075          # 3 in vertical reveal at the toe
SLOPE_TOP_HEIGHT = 0.33        # 13 in break point
SLOPE_ANGLE = math.radians(55.0)
SLOPE_RUN = (SLOPE_TOP_HEIGHT - REVEAL_HEIGHT) / math.tan(SLOPE_ANGLE)  # ~0.179
BARRIER_HEIGHT = 0.81          # 32 in
BASE_HALF_WIDTH = 0.305        # 24 in base
TOP_HALF_WIDTH = 0.075         # 6 in top
UPPER_RUN = BASE_HALF_WIDTH - TOP_HALF_WIDTH - SLOPE_RUN


def jersey_profile() -> list[tuple[float, float]]:
    """Closed (x, z) outline centred on the barrier axis, traffic side -x."""
    half = [(-BASE_HALF_WIDTH, 0.0), (-BASE_HALF_WIDTH, REVEAL_HEIGHT),
            (-BASE_HALF_WIDTH + SLOPE_RUN, SLOPE_TOP_HEIGHT),
            (-TOP_HALF_WIDTH, BARRIER_HEIGHT)]
    return half + [(-x, z) for x, z in reversed(half)]


def flat_profile() -> list[tuple[float, float]]:
    return [(-BASE_HALF_WIDTH, 0.0), (-BASE_HALF_WIDTH, BARRIER_HEIGHT),
            (BASE_HALF_WIDTH, BARRIER_HEIGHT), (BASE_HALF_WIDTH, 0.0)]


def jersey_face_offset(z: float) -> float:
    """How far behind the toe the traffic face is at height z."""
    if z <= REVEAL_HEIGHT:
        return 0.0
    if z <= SLOPE_TOP_HEIGHT:
        return (z - REVEAL_HEIGHT) / math.tan(SLOPE_ANGLE)
    return SLOPE_RUN + UPPER_RUN * min(1.0, (z - SLOPE_TOP_HEIGHT) / (BARRIER_HEIGHT - SLOPE_TOP_HEIGHT))


#: Lateral distance over which the tyre mounts the 75 mm reveal. A round
#: tyre meeting a low step at a shallow angle rolls up it over a short
#: distance instead of jumping; 4 cm keeps the lift continuous.
REVEAL_BLEND = 0.04


def wheel_lift(incursion: float) -> float:
    """Height the tyre's outer edge is carried to once it is `incursion`
    metres past the toe."""
    if incursion <= 0.0:
        return 0.0
    if incursion < REVEAL_BLEND:
        s = incursion / REVEAL_BLEND
        return REVEAL_HEIGHT * s * s * (3.0 - 2.0 * s)
    return min(SLOPE_TOP_HEIGHT, REVEAL_HEIGHT + (incursion - REVEAL_BLEND) * math.tan(SLOPE_ANGLE))


@dataclass(frozen=True)
class Car:
    """Geometry comes from the rendered model (the renderer measures it and
    passes it in); the dynamic constants are generic passenger-car values."""
    front_axle: float = 1.15       # centre of mass to front axle, m
    rear_axle: float = 1.25        # centre of mass to rear axle, m
    tyre_outer: float = 0.80       # centreline to tyre outer sidewall, m
    body_half_width: float = 0.83  # centreline to body side, m
    nose: float = 1.95             # centre to front bumper, m
    tail: float = 1.95             # centre to rear bumper, m
    body_contact_height: float = 0.40  # bumper / sill height that would meet a wall
    mass: float = 1400.0
    yaw_inertia: float = 2200.0
    cornering_front: float = 70000.0   # N/rad per axle
    cornering_rear: float = 80000.0
    corner_sprung_mass: float = 320.0  # kg carried by one corner
    spring: float = 24000.0            # N/m at the wheel
    damper: float = 2400.0             # N s/m
    bump_travel: float = 0.09          # suspension travel before the bump stop


@dataclass
class Scenario:
    wall: str                      # "jersey" or "flat"
    speed: float = 12.0            # m/s (about 27 mph)
    approach_deg: float = 5.0      # shallow drift toward the barrier
    initial_gap: float = 0.30      # tyre outer edge to toe at t=0, m
    lane_offset: float = 0.95      # where the driver steers back to (tyre edge to toe)
    reaction_time: float = 0.45    # s after first contact before steering input
    duration: float = 4.0
    dt: float = 1.0 / 1200.0
    wall_stiffness: float = 350000.0   # flat wall body contact, N/m
    wall_damping: float = 9000.0
    wall_friction: float = 0.35        # painted steel on concrete


WHEELS = ("front_right", "rear_right", "front_left", "rear_left")


@dataclass
class State:
    t: float
    x: float            # car centre, lateral; 0 is the barrier toe, negative is the road
    y: float            # along the barrier
    heading: float      # rad, positive = nose toward the barrier
    speed: float
    yaw_rate: float
    steer: float
    wheel_z: dict = field(default_factory=dict)       # wheel centre rise above rolling height
    corner_z: dict = field(default_factory=dict)      # sprung corner rise
    compression: dict = field(default_factory=dict)   # wheel_z - corner_z
    incursion: dict = field(default_factory=dict)     # tyre edge past the toe (jersey)
    tyre_force: dict = field(default_factory=dict)    # sideways push from the slope, N
    body_gap: float = 0.0     # smallest clearance between body side and the wall face
    body_force: float = 0.0   # flat-wall contact force on the body, N
    scrape_from_y: float | None = None  # where body contact started, for the scrape mark
    distance: float = 0.0     # distance rolled, for wheel spin

    @property
    def roll(self) -> float:
        """Positive = barrier side up."""
        right = (self.corner_z["front_right"] + self.corner_z["rear_right"]) / 2
        left = (self.corner_z["front_left"] + self.corner_z["rear_left"]) / 2
        return right - left  # caller divides by track width

    def event(self, name: str) -> bool:
        return EVENTS[name](self)


#: Named physical conditions the narration can be checked against. Each is a
#: predicate over the simulated state the frame was drawn from.
EVENTS = {
    "tyre_on_slope": lambda s: max(s.incursion.values(), default=0.0) > 0.005,
    "front_tyre_climbing": lambda s: s.wheel_z["front_right"] > 0.03,
    "suspension_compressed": lambda s: max(s.compression.values()) > 0.02,
    "body_clear_of_wall": lambda s: s.body_gap > 0.02,
    "body_on_wall": lambda s: s.body_force > 500.0,
    "steered_away": lambda s: s.heading < math.radians(-0.4),
}


def simulate(scenario: Scenario, car: Car = Car()) -> list[State]:
    """Explicit fixed-step integration. Returns one State per step."""
    c, sc = car, scenario
    heading = math.radians(sc.approach_deg)
    # Place the car so the front barrier-side tyre edge starts initial_gap
    # short of the toe.
    x = -sc.initial_gap - c.tyre_outer * math.cos(heading) - c.front_axle * math.sin(heading)
    y = 0.0
    u, v, r = sc.speed, 0.0, 0.0
    wheel_z = {w: 0.0 for w in WHEELS}
    corner_z = {w: 0.0 for w in WHEELS}
    corner_vz = {w: 0.0 for w in WHEELS}
    static_load = c.mass * 9.81 / 4.0
    first_contact = None
    scrape_from = None
    distance = 0.0
    steer = 0.0
    lane_x = -sc.lane_offset - c.tyre_outer
    states: list[State] = []
    steps = int(sc.duration / sc.dt)
    arm = {"front_right": c.front_axle, "rear_right": -c.rear_axle,
           "front_left": c.front_axle, "rear_left": -c.rear_axle}
    side = {"front_right": 1.0, "rear_right": 1.0, "front_left": -1.0, "rear_left": -1.0}

    for step in range(steps):
        t = step * sc.dt
        sin_h, cos_h = math.sin(heading), math.cos(heading)

        # --- contact with the barrier -----------------------------------
        force_x = 0.0        # world, +x is into the barrier
        force_y = 0.0
        moment = 0.0         # about the vertical axis, + = nose toward barrier
        incursion, tyre_force = {}, {}
        new_wheel_z = {}
        for w in WHEELS:
            # World position of this tyre's outer edge.
            px = x + arm[w] * sin_h + side[w] * c.tyre_outer * cos_h
            py = y + arm[w] * cos_h - side[w] * c.tyre_outer * sin_h
            d = px if (sc.wall == "jersey" and side[w] > 0) else -1.0
            incursion[w] = max(0.0, d)
            new_wheel_z[w] = wheel_lift(d)
            comp = new_wheel_z[w] - corner_z[w]
            comp_rate = (new_wheel_z[w] - wheel_z[w]) / sc.dt - corner_vz[w]
            spring_force = c.spring * comp + c.damper * comp_rate
            if comp > c.bump_travel:
                spring_force += 400000.0 * (comp - c.bump_travel)  # bump stop
            # Quarter-car: the sprung corner follows its wheel.
            corner_vz[w] += spring_force / c.corner_sprung_mass * sc.dt
            corner_z[w] += corner_vz[w] * sc.dt
            push = 0.0
            if d > 0.0:
                load = max(0.0, static_load + spring_force)
                # On the reveal the tyre is still mounting; the sideways
                # component grows to tan(55 deg) of the load as it reaches
                # the slope proper.
                ramp = min(1.0, d / REVEAL_BLEND)
                push = load * math.tan(SLOPE_ANGLE) * ramp
                force_x -= push
                moment += (py - y) * (-push)
            tyre_force[w] = push
        wheel_z = new_wheel_z

        body_force = 0.0
        body_gap = 1e9
        # Body side sample points: front corner, mid, rear corner.
        for along in (c.nose, 0.0, -c.tail):
            px = x + along * sin_h + c.body_half_width * cos_h
            py = y + along * cos_h - c.body_half_width * sin_h
            pvx = u * sin_h + v * cos_h + r * (py - y)
            if sc.wall == "jersey":
                # Rolling away from the barrier pulls the body side back a
                # little at bumper height; ignoring that is conservative.
                gap = jersey_face_offset(c.body_contact_height) - px
            else:
                gap = -px
            body_gap = min(body_gap, gap)
            if sc.wall == "flat" and gap < 0.0:
                normal = sc.wall_stiffness * (-gap) + sc.wall_damping * max(0.0, pvx)
                body_force += normal
                friction = sc.wall_friction * normal
                force_x -= normal
                force_y -= friction
                moment += (py - y) * (-normal) - (px - x) * (-friction)
        if first_contact is None and (body_force > 0.0 or any(i > 0.0 for i in incursion.values())):
            first_contact = t
        if scrape_from is None and body_force > 0.0:
            scrape_from = y + c.nose

        # --- driver ------------------------------------------------------
        if first_contact is not None and t > first_contact + sc.reaction_time:
            target = -0.9 * heading - 0.10 * (x - lane_x) - 0.25 * r  # steer right is +
            target = max(-0.12, min(0.12, target))
        else:
            target = 0.0
        steer += (target - steer) * min(1.0, sc.dt / 0.12)

        # --- single-track dynamics --------------------------------------
        # Body axes: forward f = (sin h, cos h), right g = (cos h, -sin h).
        # v is lateral speed to the right, r is yaw rate toward the right
        # (toward the barrier), steer is positive to the right. This is the
        # textbook model mirrored, so the equations keep their usual form.
        # `moment` is clockwise-positive (toward the barrier) to match r.
        f_forward = force_x * sin_h + force_y * cos_h
        f_right = force_x * cos_h - force_y * sin_h
        safe_u = max(1.0, u)
        alpha_f = (v + c.front_axle * r) / safe_u - steer
        alpha_r = (v - c.rear_axle * r) / safe_u
        fy_f = -c.cornering_front * alpha_f
        fy_r = -c.cornering_rear * alpha_r
        dv = (fy_f + fy_r + f_right) / c.mass - u * r
        dr = (c.front_axle * fy_f - c.rear_axle * fy_r + moment) / c.yaw_inertia
        du = f_forward / c.mass + v * r
        v += dv * sc.dt
        r += dr * sc.dt
        u = max(0.0, u + du * sc.dt)
        heading += r * sc.dt
        x += (u * sin_h + v * cos_h) * sc.dt
        y += (u * cos_h - v * sin_h) * sc.dt
        distance += u * sc.dt

        states.append(State(
            t=t, x=x, y=y, heading=heading, speed=u, yaw_rate=r, steer=steer,
            wheel_z=dict(wheel_z), corner_z=dict(corner_z),
            compression={w: wheel_z[w] - corner_z[w] for w in WHEELS},
            incursion=incursion, tyre_force=tyre_force,
            body_gap=body_gap, body_force=body_force,
            scrape_from_y=scrape_from, distance=distance,
        ))
    return states


def sample(states: list[State], t: float, dt: float) -> State:
    return states[max(0, min(len(states) - 1, int(round(t / dt))))]


def summary(states: list[State]) -> dict:
    def first(pred):
        return next((round(s.t, 3) for s in states if pred(s)), None)
    return {
        "first_tyre_contact_s": first(lambda s: max(s.incursion.values()) > 0),
        "first_body_contact_s": first(lambda s: s.body_force > 0),
        "peak_incursion_m": round(max(max(s.incursion.values()) for s in states), 3),
        "peak_wheel_lift_m": round(max(max(s.wheel_z.values()) for s in states), 3),
        "peak_compression_m": round(max(max(s.compression.values()) for s in states), 3),
        "peak_corner_rise_m": round(max(max(s.corner_z.values()) for s in states), 3),
        "min_body_gap_m": round(min(s.body_gap for s in states), 3),
        "peak_tyre_push_kN": round(max(max(s.tyre_force.values()) for s in states) / 1000, 2),
        "peak_body_force_kN": round(max(s.body_force for s in states) / 1000, 2),
        "min_heading_deg": round(math.degrees(min(s.heading for s in states)), 2),
        "end_heading_deg": round(math.degrees(states[-1].heading), 2),
        "end_x_m": round(states[-1].x, 3),
        "end_speed_mps": round(states[-1].speed, 2),
        "max_abs_yaw_rate_dps": round(math.degrees(max(abs(s.yaw_rate) for s in states)), 1),
    }
