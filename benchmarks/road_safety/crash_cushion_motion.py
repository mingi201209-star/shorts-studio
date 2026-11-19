"""Motion model for the sand-barrel crash cushion episode (pure Python, no
Blender, unit-tested).

TEST CONDITIONS (what every number in the film means)
  A 1,500 kg car at 25 m/s (90 km/h) drives straight at the centre of the
  array with no braking and no steering. "Stopping distance" is the distance
  the nose travels from first contact with the array (or the wall) until the
  car's speed is below STOPPED_SPEED (0.5 m/s).

What is modelled, and only this:

* While the car's nose is inside a row of barrels, the sand there has to be
  accelerated up to the car's speed. Momentum accounting gives a force
  F = (row sand mass / D) * v^2 on the car: sand mass swept per metre times
  speed squared. A constant SHELL_FORCE stands for the plastic shells breaking
  and rolling losses. Rows are heavier toward the back.
* The car is not drawn deformed and its own crush is not simulated; in the
  model the sand takes the momentum.
* Rigid-wall comparison: the same car stops over WALL_CRUSH metres at constant
  deceleration, a = v^2 / (2 d). WALL_CRUSH is an ASSUMPTION. NHTSA NCAP
  frontal tests at 56 km/h report maximum crush of roughly 0.44-0.62 m for
  current cars (figures seen in the NCAP report listings); at 90 km/h the same
  structures would be asked for more than they have, so "about one metre" is
  an order-of-magnitude stand-in, not a measurement.
* Nose dive under braking: second-order pitch response, capped at the bump stops.

WHAT IS CHECKED, AND WHAT IS NOT
  Checked (audit_* and summary): momentum the launched sand carries versus
  momentum the car lost; average deceleration, exit speed and a flail-space
  occupant impact velocity against the acceptance limits that sand-barrel
  arrays are evaluated against (exit speed under 10 mph, occupant impact
  velocity under 40 ft/s, average deceleration under 12 g, as summarised in a
  state-DOT research Q&A). NOT done: comparison with a full-scale crash test
  trace. "physically_calibrated" stays False everywhere.

Particles (sand grains, fine dust, shell chips) are launched when a barrel's
shell gives way, over a short window, and fly under gravity (dust also under
air drag); their forward speed is the car's mean speed while it pushes
through that row, which is the momentum transfer the narration describes.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

G = 9.81
CAR_MASS = 1500.0          # kg
SPEED = 25.0               # m/s  (90 km/h)
BARREL_D = 0.90            # m, diameter = footprint along the axis
BARREL_PITCH = 0.95        # m, centre-to-centre
BARREL_HEIGHT = 0.95       # m
#: Rows front to back: (barrels in the row, sand per barrel in kg). The array
#: widens toward the back and each barrel holds more sand, so the car meets
#: little mass first and much more later. A head-on car (1.8 m wide) engages a
#: whole row at once, so a row's mass is count * kg.
ROWS = ((1, 90.0), (1, 120.0), (2, 120.0), (2, 190.0), (3, 190.0), (3, 500.0), (3, 640.0))
LATERAL_PITCH = 0.95       # m between barrels across the array
SHELL_FORCE = 4000.0       # N while the nose is inside the array
WALL_CRUSH = 1.00          # m, ASSUMED deceleration distance against a rigid wall (see docstring)
CG_HEIGHT = 0.55           # m
PITCH_STIFFNESS = 150e3    # N m/rad (wheel rate 28 kN/m, geometry of the sedan)
PITCH_LIMIT = 0.06         # rad, bump stops
PITCH_OMEGA = 2 * math.pi * 1.4
PITCH_ZETA = 0.45
BURST_DEPTH = 0.45         # m the nose has to push into a barrel before its shell gives way
CRUSH_RATIO = 0.55         # fraction of the barrel's length it is squashed by at that moment
FLAIL_DISTANCE = 0.6       # m, occupant free-flight distance used by barrier evaluation (flail-space model)
OIV_LIMIT = 12.2           # m/s (40 ft/s)
AVG_DECEL_LIMIT_G = 12.0   # average deceleration limit used for sand-barrel arrays
EXIT_SPEED_LIMIT = 4.47    # m/s (10 mph) at the end of the array
START_NOSE = -8.0          # m before the first barrel face
DT = 1.0 / 2000.0


@dataclass(frozen=True)
class Scenario:
    case: str = "array"            # "array" | "wall"
    speed: float = SPEED
    start_nose: float = START_NOSE
    duration: float = 1.4
    dt: float = DT


@dataclass
class State:
    t: float
    nose: float            # nose position along the axis, 0 = first barrel face
    speed: float
    accel: float           # m/s^2, negative while slowing
    pitch: float           # rad, positive = nose down
    barrel: int            # index of barrel the nose is inside, -1 if none
    distance: float        # rolled distance, for wheel spin


def barrel_front(i: int) -> float:
    return i * BARREL_PITCH


def barrel_back(i: int) -> float:
    return i * BARREL_PITCH + BARREL_D


def sand_force(nose: float, speed: float) -> tuple[float, int]:
    """Force on the car and the barrel it is inside (-1 if none)."""
    for i, (count, kg) in enumerate(ROWS):
        if barrel_front(i) <= nose < barrel_back(i):
            return count * kg / BARREL_D * speed * speed + SHELL_FORCE, i
    return 0.0, -1


def simulate(scenario: Scenario | None = None) -> list[State]:
    sc = scenario or Scenario()
    dt = sc.dt
    nose, v, t, pitch, pitch_rate, dist = sc.start_nose, sc.speed, 0.0, 0.0, 0.0, 0.0
    states: list[State] = []
    steps = int(sc.duration / dt)
    wall_decel = sc.speed ** 2 / (2.0 * WALL_CRUSH)
    for _ in range(steps):
        if sc.case == "wall":
            force = (CAR_MASS * wall_decel) if (nose >= 0.0 and v > 0.0) else 0.0
            barrel = -1
        else:
            force, barrel = sand_force(nose, v) if v > 0.0 else (0.0, -1)
            if nose >= barrel_back(len(ROWS) - 1) and v > 0.0:
                force = SHELL_FORCE
        accel = -force / CAR_MASS
        # Pitch: nose dives in proportion to deceleration, with lag.
        target = min(PITCH_LIMIT, CAR_MASS * (-accel) * CG_HEIGHT / PITCH_STIFFNESS)
        pitch_acc = PITCH_OMEGA ** 2 * (target - pitch) - 2 * PITCH_ZETA * PITCH_OMEGA * pitch_rate
        pitch_rate += pitch_acc * dt
        pitch += pitch_rate * dt
        states.append(State(t=t, nose=nose, speed=v, accel=accel, pitch=pitch, barrel=barrel, distance=dist))
        v = max(0.0, v + accel * dt)
        step = v * dt
        nose += step
        dist += step
        t += dt
    return states


def sample(states: list[State], t: float, dt: float = DT) -> State:
    """Linear interpolation, clamped at both ends."""
    x = max(0.0, min(len(states) - 1.0, t / dt))
    i = int(x)
    j = min(len(states) - 1, i + 1)
    f = x - i
    a, b = states[i], states[j]
    mix = lambda p, q: p + (q - p) * f  # noqa: E731
    return State(t=mix(a.t, b.t), nose=mix(a.nose, b.nose), speed=mix(a.speed, b.speed),
                 accel=mix(a.accel, b.accel), pitch=mix(a.pitch, b.pitch),
                 barrel=a.barrel if f < 0.5 else b.barrel, distance=mix(a.distance, b.distance))


def burst_times(states: list[State]) -> list[float | None]:
    """Time each barrel's shell gives way: the nose has pushed BURST_DEPTH
    into it. Until then the barrel is being squashed (see crush_fraction)."""
    times: list[float | None] = []
    for i in range(len(ROWS)):
        hit = next((s.t for s in states if s.nose >= barrel_front(i) + BURST_DEPTH), None)
        times.append(hit)
    return times


#: Speed below which the car counts as stopped (m/s). Sand drag falls with
#: speed squared, so the last metre is a slow crawl; counting that crawl as
#: "still stopping" would overstate the stopping time.
STOPPED_SPEED = 0.5


def stop_state(states: list[State]) -> State:
    return next((s for s in states if s.speed <= STOPPED_SPEED), states[-1])


def crush_fraction(nose: float, row: int) -> float:
    """0 = untouched, 1 = at the moment the shell gives way."""
    return max(0.0, min(1.0, (nose - barrel_front(row)) / BURST_DEPTH))


#: Speed below which the car counts as stopped (m/s). Sand drag falls with
#: speed squared, so the last metre is a slow crawl; counting that crawl as
#: "still stopping" would overstate the stopping time.
STOPPED_SPEED = 0.5


def stop_state(states: list[State]) -> State:
    return next((s for s in states if s.speed <= STOPPED_SPEED), states[-1])


def crush_fraction(nose: float, row: int) -> float:
    """0 = untouched, 1 = at the moment the shell gives way."""
    return max(0.0, min(1.0, (nose - barrel_front(row)) / BURST_DEPTH))


def ghost_times(states: list[State]) -> list[float]:
    """Times of the stroboscopic car positions: every GHOST_INTERVAL from first contact."""
    contact = next(s.t for s in states if s.nose >= 0.0)
    return [round(contact + k * GHOST_INTERVAL, 6) for k in range(1, 13)]


def occupant_metrics(states: list[State], dt: float = DT) -> dict:
    """Flail-space occupant impact velocity and ridedown deceleration from the
    car's deceleration trace. The occupant is a free body travelling at the
    impact speed until it has moved FLAIL_DISTANCE relative to the car, then
    rides down with the car."""
    i0 = next(i for i, s in enumerate(states) if s.nose >= 0.0)
    v_occ = states[i0].speed
    rel = 0.0
    hit = None
    for i in range(i0, len(states)):
        rel += (v_occ - states[i].speed) * dt
        if rel >= FLAIL_DISTANCE:
            hit = i
            break
    if hit is None:   # car stopped first: the occupant keeps going at the speed difference
        left = FLAIL_DISTANCE - rel
        oiv = v_occ - states[-1].speed
        hit = len(states) - 1
        rel_t = left / max(oiv, 1e-9)
        del rel_t
    else:
        oiv = v_occ - states[hit].speed
    window = max(1, int(round(0.010 / dt)))
    decel = [max(0.0, -s.accel) for s in states[hit:]]
    ride = 0.0
    if len(decel) >= window:
        run = sum(decel[:window])
        ride = run / window
        for j in range(window, len(decel)):
            run += decel[j] - decel[j - window]
            ride = max(ride, run / window)
    else:
        ride = max(decel, default=0.0)
    return {"oiv_mps": round(oiv, 2), "ridedown_g": round(ride / G, 2)}


def momentum_audit(states: list[State], particles: list["Particle"], dt: float = DT) -> dict:
    """Does the sand that is drawn carry the momentum the car lost to it?
    car momentum lost to sand = M (v0 - v_end) - shell impulse;
    drawn sand momentum = sum of (sand mass x forward launch speed)."""
    v0 = next(s.speed for s in states if s.nose >= 0.0)
    v_end = states[-1].speed
    in_array = [s for s in states if s.nose >= 0.0 and s.speed > 0.0
                and (s.barrel >= 0 or s.nose >= barrel_back(len(ROWS) - 1))]
    shell_impulse = SHELL_FORCE * dt * len(in_array)
    lost = CAR_MASS * (v0 - v_end) - shell_impulse
    shown = 0.0
    for unit, b in enumerate(barrels()):
        mine = [p for p in particles if p.kind == "sand" and p.unit == unit]
        if mine:
            shown += b["kg"] * sum(p.v0[1] for p in mine) / len(mine)
    return {"car_momentum_lost_to_sand": round(lost, 1), "sand_momentum_drawn": round(shown, 1),
            "ratio": round(shown / lost, 3) if lost else None}


def summary(states: list[State], case: str) -> dict:
    stop = stop_state(states)
    moving = [s for s in states if s.nose >= 0.0 and s.speed > STOPPED_SPEED]
    peak = max((-s.accel for s in moving), default=0.0)
    contact_t = next((s.t for s in states if s.nose >= 0.0), None)
    out = {
        "case": case,
        "contact_s": None if contact_t is None else round(contact_t, 4),
        "stop_s": round(stop.t, 4),
        "stop_distance_m": round(stop.nose, 3),
        "peak_decel_g": round(peak / G, 2),
        "peak_pitch_deg": round(math.degrees(max(s.pitch for s in states)), 2),
        "avg_decel_g": round(states[0].speed ** 2 / (2.0 * stop.nose) / G, 2) if stop.nose > 0 else None,
        **occupant_metrics(states),
    }
    if case == "array":
        def mean_decel(lo: float, hi: float) -> float:
            part = [s for s in moving if lo <= s.nose < hi]
            return round(sum(-s.accel for s in part) / max(1, len(part)) / G, 2)
        third = stop.nose / 3.0
        out["mean_decel_first_third_g"] = mean_decel(0.0, third)
        out["mean_decel_middle_third_g"] = mean_decel(third, 2 * third)
        out["peak_decel_at_m"] = round(max(moving, key=lambda s: -s.accel).nose, 2)
        out["speed_at_wall_line_mps"] = round(sample_at_nose(states, WALL_CRUSH).speed, 2)
        out["total_sand_kg"] = sum(c * k for c, k in ROWS)
        out["speed_at_array_end_mps"] = round(sample_at_nose(states, barrel_back(len(ROWS) - 1)).speed, 2)
    return out


def sample_at_nose(states: list[State], nose: float) -> State:
    return next((s for s in states if s.nose >= nose), states[-1])


# ---------------------------------------------------------------- particles


@dataclass
class Particle:
    kind: str              # "sand" (grain) | "dust" (fine, drag) | "chip" (shell piece)
    barrel: int            # row index
    unit: int              # barrel index in barrels()
    t0: float              # launch time
    p0: tuple[float, float, float]   # (x lateral, y along axis, z)
    v0: tuple[float, float, float]
    radius: float = 0.015
    drag: float = 0.0      # 1/s, linear air drag (fine dust only)
    spin: float = 0.0
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    t_ground: float = 0.0  # time after launch of first ground contact (filled by build_particles)
    land_v: tuple[float, float, float] = (0.0, 0.0, 0.0)
    hop: float = 0.0       # duration of the single bounce


#: Grains per kilogram of sand in a barrel, and fine dust per kilogram. A grain
#: here stands for a small clump of real sand (a real grain is far below a pixel).
GRAINS_PER_KG = 1.6
DUST_PER_KG = 0.9
CHIPS_PER_BARREL = 4
BOUNCE = 0.22


def barrels() -> list[dict]:
    """Every barrel: row, lateral x, centre y along the axis, sand kg."""
    out = []
    for i, (count, kg) in enumerate(ROWS):
        for j in range(count):
            x = (j - (count - 1) / 2.0) * LATERAL_PITCH
            out.append({"row": i, "x": x, "y": barrel_front(i) + BARREL_D / 2, "kg": kg})
    return out


def mean_speed_in_row(states: list[State], row: int) -> float:
    inside = [s.speed for s in states if s.barrel == row]
    return sum(inside) / len(inside) if inside else 0.0


def _floor(p: Particle) -> float:
    return p.radius if p.kind != "chip" else 0.012


def _fall(p: Particle, tau: float) -> tuple[float, float, float]:
    """Position tau seconds after launch, before the first ground contact."""
    x0, y0, z0 = p.p0
    vx, vy, vz = p.v0
    k = p.drag
    if k <= 0.0:
        return x0 + vx * tau, y0 + vy * tau, z0 + vz * tau - 0.5 * G * tau * tau
    f = (1.0 - math.exp(-k * tau)) / k
    return x0 + vx * f, y0 + vy * f, z0 + (vz + G / k) * f - G * tau / k


def _velocity(p: Particle, tau: float) -> tuple[float, float, float]:
    vx, vy, vz = p.v0
    k = p.drag
    if k <= 0.0:
        return vx, vy, vz - G * tau
    e = math.exp(-k * tau)
    return vx * e, vy * e, (vz + G / k) * e - G / k


def _prepare(p: Particle) -> None:
    floor = _floor(p)
    lo, hi = 0.0, 8.0
    for _ in range(40):          # z(t) is concave after launch: bisect for the ground time
        mid = (lo + hi) / 2.0
        if _fall(p, mid)[2] > floor:
            lo = mid
        else:
            hi = mid
    p.t_ground = hi
    p.land_v = _velocity(p, hi)
    p.hop = 2.0 * BOUNCE * max(0.0, -p.land_v[2]) / G


def build_particles(states: list[State], seed: int = 7) -> list[Particle]:
    """Sand grains, fine dust and shell chips for every barrel. They are
    released over a short window after the shell gives way (a pour, not a
    single puff). Forward speed = the car's mean speed while it pushes
    through that row (the sand is being brought up to the car's speed)."""
    rng = random.Random(seed)
    times = burst_times(states)
    particles: list[Particle] = []
    for unit, b in enumerate(barrels()):
        i = b["row"]
        t_hit = times[i]
        if t_hit is None:
            continue
        v_row = mean_speed_in_row(states, i)
        fill = fill_height_kg(b["kg"])
        for kind, per_kg in (("sand", GRAINS_PER_KG), ("dust", DUST_PER_KG)):
            for _ in range(int(b["kg"] * per_kg)):
                r = BARREL_D / 2 * math.sqrt(rng.random()) * 0.94
                a = rng.random() * math.tau
                z = rng.uniform(0.04, fill if kind == "sand" else BARREL_HEIGHT)
                p0 = (b["x"] + r * math.cos(a), b["y"] + r * math.sin(a), z)
                lateral = rng.gauss(0.0, 2.0 if kind == "sand" else 2.8) + 1.4 * math.cos(a) + 0.9 * b["x"]
                forward = v_row * (rng.uniform(0.9, 1.12) if kind == "sand" else rng.uniform(0.55, 0.95))
                up = max(0.0, rng.gauss(1.1, 1.2)) if kind == "sand" else max(0.0, rng.gauss(2.0, 1.6))
                radius = math.exp(rng.uniform(math.log(0.010), math.log(0.024))) if kind == "sand" \
                    else rng.uniform(0.005, 0.009)
                t0 = t_hit + min(0.12, rng.expovariate(1.0 / 0.03))
                p = Particle(kind, i, unit, t0, p0, (lateral, forward, up), radius=radius,
                             drag=0.0 if kind == "sand" else 2.6)
                _prepare(p)
                particles.append(p)
        for _ in range(CHIPS_PER_BARREL):
            a = rng.random() * math.tau
            r = BARREL_D / 2
            p0 = (b["x"] + r * math.cos(a), b["y"] + r * math.sin(a), rng.uniform(0.2, 0.9))
            v = (math.cos(a) * rng.uniform(1.5, 4.5) + 0.9 * b["x"], v_row * rng.uniform(0.8, 1.05),
                 rng.uniform(0.5, 3.0))
            axis = (rng.random(), rng.random(), rng.random())
            norm = math.sqrt(sum(c * c for c in axis)) or 1.0
            p = Particle("chip", i, unit, t_hit, p0, v, radius=0.05, spin=rng.uniform(-12, 12),
                         axis=tuple(c / norm for c in axis))
            _prepare(p)
            particles.append(p)
    return particles


def particle_state(p: Particle, t: float) -> tuple[tuple[float, float, float], float, bool] | None:
    """Position, rotation angle and airborne flag at time t; None before launch."""
    if t < p.t0:
        return None
    tau = t - p.t0
    floor = _floor(p)
    if tau <= p.t_ground:
        pos = _fall(p, tau)
        return pos, p.spin * tau, pos[2] > floor + 0.01
    gx, gy, _gz = _fall(p, p.t_ground)
    vx, vy, vz = p.land_v
    s = tau - p.t_ground
    hvx, hvy = 0.5 * vx, 0.5 * vy              # friction on the first impact
    if s <= p.hop:                               # one small bounce
        z = floor + 0.5 * BOUNCE * (-vz) * s * (1.0 - s / p.hop) * 2.0 if p.hop > 0 else floor
        return (gx + hvx * s, gy + hvy * s, z), p.spin * p.t_ground, z > floor + 0.01
    s2 = s - p.hop
    slide = (1.0 - math.exp(-7.0 * s2)) / 7.0    # then it slides to rest
    return (gx + hvx * p.hop + 0.35 * hvx * slide, gy + hvy * p.hop + 0.35 * hvy * slide, floor), \
        p.spin * p.t_ground, False


def fill_height_kg(kg: float) -> float:
    """Visible sand height inside a barrel (m): proportional to its sand mass,
    the heaviest barrel filled to about 90% of the shell."""
    return 0.10 + 0.75 * BARREL_HEIGHT * kg / max(k for _, k in ROWS)


def pile_radius(kg: float) -> float:
    return 0.30 + 0.20 * kg / max(k for _, k in ROWS)
