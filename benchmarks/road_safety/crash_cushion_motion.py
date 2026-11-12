"""Motion model for the sand-barrel crash cushion episode (pure Python, no
Blender, unit-tested).

What is modelled, and only this:

* A car of mass CAR_MASS drives along the axis of a single file of
  sand-filled barrels. Each barrel i holds sand of mass SAND_KG[i].
* While the car's nose is inside barrel i's footprint, the sand there has to
  be accelerated up to the car's speed (it is thrown forward and sideways).
  Momentum accounting gives a force  F = (m_i / D) * v^2  on the car: the
  sand mass swept per metre times speed squared. A constant SHELL_FORCE
  stands for the plastic shells breaking and the car's own rolling losses.
* The car is not drawn deformed and its own crush is not simulated; in the
  model the sand takes the momentum. This is a teaching model, not a crash
  simulation. "physically_calibrated" stays False everywhere.
* For the comparison shot, a rigid wall stops the same car over WALL_CRUSH
  metres at constant deceleration (energy balance, v^2 / (2 d)).
* Nose dive under braking: a second-order pitch response toward
  M * a * h_cg / K_pitch, capped where the bump stops would take over.

Particles (sand grains and shell chips) are launched when the nose reaches a
barrel and then fly ballistically; their forward speed is the car's speed at
that instant, which is the momentum transfer the narration describes.
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
WALL_CRUSH = 0.90          # m, assumed crush distance against a rigid wall
CG_HEIGHT = 0.55           # m
PITCH_STIFFNESS = 150e3    # N m/rad (wheel rate 28 kN/m, geometry of the sedan)
PITCH_LIMIT = 0.06         # rad, bump stops
PITCH_OMEGA = 2 * math.pi * 1.4
PITCH_ZETA = 0.45
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
    """Time the nose first reaches each barrel's face (shell contact)."""
    times: list[float | None] = []
    for i in range(len(ROWS)):
        hit = next((s.t for s in states if s.nose >= barrel_front(i)), None)
        times.append(hit)
    return times


#: Speed below which the car counts as stopped (m/s). Sand drag falls with
#: speed squared, so the last metre is a slow crawl; counting that crawl as
#: "still stopping" would overstate the stopping time.
STOPPED_SPEED = 0.5


def stop_state(states: list[State]) -> State:
    return next((s for s in states if s.speed <= STOPPED_SPEED), states[-1])


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
    return out


def sample_at_nose(states: list[State], nose: float) -> State:
    return next((s for s in states if s.nose >= nose), states[-1])


# ---------------------------------------------------------------- particles


@dataclass
class Particle:
    kind: str              # "sand" | "chip"
    barrel: int
    t0: float              # launch time
    p0: tuple[float, float, float]   # (x lateral, y along axis, z)
    v0: tuple[float, float, float]
    spin: float = 0.0
    axis: tuple[float, float, float] = (0.0, 0.0, 1.0)
    rest_after: float = field(default=0.0)


PARTICLE_RADIUS = 0.035


def barrels() -> list[dict]:
    """Every barrel: row, lateral x, centre y along the axis, sand kg."""
    out = []
    for i, (count, kg) in enumerate(ROWS):
        for j in range(count):
            x = (j - (count - 1) / 2.0) * LATERAL_PITCH
            out.append({"row": i, "x": x, "y": barrel_front(i) + BARREL_D / 2, "kg": kg})
    return out


def build_particles(states: list[State], seed: int = 7) -> list[Particle]:
    """Launch sand grains and shell chips from every barrel at the moment the
    nose reaches it. Forward speed = the car's speed then (the sand is being
    brought up to the car's speed); sideways and upward speeds are random."""
    rng = random.Random(seed)
    times = burst_times(states)
    particles: list[Particle] = []
    for b in barrels():
        i = b["row"]
        t_hit = times[i]
        if t_hit is None:
            continue
        v_car = sample(states, t_hit).speed
        count = int(10 + b["kg"] / 16)
        for _ in range(count):
            r = BARREL_D / 2 * math.sqrt(rng.random()) * 0.92
            a = rng.random() * math.tau
            y = b["y"] + r * math.sin(a)
            p0 = (b["x"] + r * math.cos(a), y, rng.uniform(0.05, fill_height_kg(b["kg"])))
            vx = rng.gauss(0.0, 2.4) + 1.6 * math.cos(a) + 0.9 * b["x"]
            vy = v_car * rng.uniform(0.92, 1.12)
            vz = rng.uniform(0.6, 3.6)
            particles.append(Particle("sand", i, t_hit, p0, (vx, vy, vz)))
        for _ in range(4):
            a = rng.random() * math.tau
            r = BARREL_D / 2
            p0 = (b["x"] + r * math.cos(a), b["y"] + r * math.sin(a), rng.uniform(0.2, 0.9))
            v = (math.cos(a) * rng.uniform(1.5, 4.5) + 0.9 * b["x"], v_car * rng.uniform(0.8, 1.05),
                 rng.uniform(0.5, 3.0))
            axis = (rng.random(), rng.random(), rng.random())
            norm = math.sqrt(sum(c * c for c in axis)) or 1.0
            particles.append(Particle("chip", i, t_hit, p0, v, spin=rng.uniform(-12, 12),
                                      axis=tuple(c / norm for c in axis)))
    return particles


def particle_state(p: Particle, t: float) -> tuple[tuple[float, float, float], float, bool] | None:
    """Position, rotation angle and airborne flag at time t; None before launch."""
    if t < p.t0:
        return None
    tau = t - p.t0
    x0, y0, z0 = p.p0
    vx, vy, vz = p.v0
    floor = PARTICLE_RADIUS if p.kind == "sand" else 0.012
    # time to first ground contact: z0 + vz t - g t^2 / 2 = floor
    disc = vz * vz + 2 * G * (z0 - floor)
    t_ground = (vz + math.sqrt(max(0.0, disc))) / G
    if tau <= t_ground:
        pos = (x0 + vx * tau, y0 + vy * tau, z0 + vz * tau - 0.5 * G * tau * tau)
        return pos, p.spin * tau, pos[2] > floor + 0.01
    # after landing: horizontal speed decays quickly, rests on the ground
    gx, gy = x0 + vx * t_ground, y0 + vy * t_ground
    k = 7.0
    decay = (1.0 - math.exp(-k * (tau - t_ground))) / k
    return (gx + 0.35 * vx * decay, gy + 0.35 * vy * decay, floor), p.spin * t_ground, False


def fill_height_kg(kg: float) -> float:
    """Visible sand height inside a barrel (m): proportional to its sand mass,
    the heaviest barrel filled to about 90% of the shell."""
    return 0.10 + 0.75 * BARREL_HEIGHT * kg / max(k for _, k in ROWS)


def pile_radius(kg: float) -> float:
    return 0.30 + 0.20 * kg / max(k for _, k in ROWS)
