"""Motion model for the runaway-truck-ramp (gravel arrester bed) episode.

Pure Python, no Blender, unit-tested.

TEST CONDITIONS (what every number in the film means)
  A 20,000 kg truck with failed brakes enters a level gravel arrester bed at
  25 m/s (90 km/h) and is not steered. "Stopping distance" is the distance
  from the first tyre contact with the gravel until speed is below
  STOPPED_SPEED. The paved comparison is the same truck coasting on pavement.

What is modelled, and only this:
  * Deceleration from rolling resistance: a = C * g, with C the rolling
    resistance coefficient. Loose pea gravel is taken as C = 0.25 and paved
    road as C = 0.01. BOTH ARE ASSUMPTIONS (the 0.25 is an illustrative value
    from a published worked example, not a design standard; Arizona DOT's
    review says field tests are still needed to predict minimum values).
  * Tyre sink: the bed resists more the deeper the tyres sink, modelled as
    resistance ramping from PAVED_C to GRAVEL_C over RAMP_IN metres.
  * Gravel thrown aside is drawn as particles; it is not simulated as a
    granular flow.
  NOT done: no comparison with a full-scale arrester-bed test trace, no
  braking, no grade. "physically_calibrated" is False everywhere.
"""
from __future__ import annotations

G = 9.81
MASS = 20000.0
SPEED0 = 25.0
GRAVEL_C = 0.25
PAVED_C = 0.01
RAMP_IN = 12.0          # metres over which the tyres sink to full depth
STOPPED_SPEED = 0.5
FPS = 30
SUBSTEPS = 20


def resistance(distance: float, c_full: float) -> float:
    """Rolling-resistance coefficient after `distance` metres in the bed."""
    f = min(max(distance / RAMP_IN, 0.0), 1.0)
    return PAVED_C + (c_full - PAVED_C) * f


def simulate(c_full: float = GRAVEL_C, seconds: float = 32.0, speed0: float = SPEED0) -> list[dict]:
    """One state per video frame: distance (m) travelled in the bed, speed (m/s),
    deceleration (m/s^2). Distance is clamped once the truck has stopped."""
    dt = 1.0 / (FPS * SUBSTEPS)
    x, v = 0.0, speed0
    states = []
    for _ in range(int(seconds * FPS)):
        a = 0.0
        for _ in range(SUBSTEPS):
            if v <= STOPPED_SPEED:
                v = 0.0
                a = 0.0
                break
            a = resistance(x, c_full) * G
            v = max(v - a * dt, 0.0)
            x += v * dt
        states.append({"x": x, "v": v, "a": a})
    return states


def stop_distance(c_full: float = GRAVEL_C, speed0: float = SPEED0) -> float:
    states = simulate(c_full, seconds=600.0, speed0=speed0) if c_full < 0.05 else simulate(c_full, speed0=speed0)
    return states[-1]["x"]


def stop_time(states: list[dict]) -> float:
    for i, s in enumerate(states):
        if s["v"] == 0.0:
            return i / FPS
    return float("inf")


def summary(states: list[dict]) -> dict:
    t = stop_time(states)
    peak_a = max(s["a"] for s in states)
    return {
        "stop_distance_m": round(states[-1]["x"], 1),
        "stop_time_s": round(t, 2),
        "peak_decel_g": round(peak_a / G, 3),
        "physically_calibrated": False,
    }


def audit_energy(states: list[dict]) -> dict:
    """Work done by resistance must equal the kinetic energy lost."""
    ke0 = 0.5 * MASS * SPEED0 ** 2
    ke1 = 0.5 * MASS * states[-1]["v"] ** 2
    work = 0.0
    prev_x = 0.0
    for s in states:
        work += resistance(prev_x, GRAVEL_C) * G * MASS * (s["x"] - prev_x)
        prev_x = s["x"]
    return {"ke_lost_J": ke0 - ke1, "work_J": work, "ratio": work / (ke0 - ke1)}


# --------------------------------------------------------------- gravel spray
import random  # noqa: E402

WHEEL_R = 0.5
AXLES_Y = (-1.4, -6.2, -7.5, -12.0, -13.3)    # axle positions behind the nose (m), from the truck model in the renderer
WHEEL_X = (-1.05, 1.05)
SINK_MAX = 0.16                                # tyre sink at full depth (m); drawn, not measured
GRAINS_PER_WHEEL_PER_S = 36.0


def sink(distance: float) -> float:
    """Tyre sink (m): zero on pavement, SINK_MAX once resistance is at full depth."""
    return SINK_MAX * min(max(distance / RAMP_IN, 0.0), 1.0)


def build_gravel(states: list[dict], seed: int = 7) -> list[dict]:
    """Stones kicked up by the tyres. A stone is launched from the leading edge
    of a tyre that is in the bed, at a fraction of the truck's speed forward
    (the tyre pushes the stones it digs into), a few m/s sideways and up, then
    flies ballistically and lies where it lands. Emission is proportional to
    speed times sink, so it fades as the truck stops. Pure bookkeeping for the
    picture; not a granular-flow simulation."""
    rng = random.Random(seed)
    grains = []
    carry = {(a, s): 0.0 for a in range(len(AXLES_Y)) for s in range(2)}
    for i, st in enumerate(states):
        t = i / FPS
        s = sink(st["x"])
        if s <= 0.0 or st["v"] <= 0.0:
            continue
        for a, ay in enumerate(AXLES_Y):
            for side, wx in enumerate(WHEEL_X):
                carry[(a, side)] += GRAINS_PER_WHEEL_PER_S / FPS * (st["v"] / SPEED0) * (s / SINK_MAX)
                while carry[(a, side)] >= 1.0:
                    carry[(a, side)] -= 1.0
                    sx = 1 if wx > 0 else -1
                    grains.append({
                        "t0": t + rng.random() / FPS,
                        "p0": (wx + sx * rng.uniform(0.0, 0.25), st["x"] + ay + WHEEL_R * 0.6, 0.05),
                        "v0": (sx * rng.uniform(0.8, 3.4), st["v"] * rng.uniform(0.25, 0.7) + rng.uniform(-0.5, 0.5),
                               rng.uniform(1.5, 4.8) * (0.5 + st["v"] / SPEED0)),
                        "r": rng.uniform(0.012, 0.03)})
    return grains


def grain_position(g: dict, t: float) -> tuple[float, float, float] | None:
    """Position at film-sim time t, None before launch (or after a dust mote's
    life is over). Lands and stays at rest."""
    tau = t - g["t0"]
    if tau < 0.0 or tau > g.get("life", 1e9):
        return None
    gg = G * g.get("gscale", 1.0)
    x = g["p0"][0] + g["v0"][0] * tau
    y = g["p0"][1] + g["v0"][1] * tau
    z = g["p0"][2] + g["v0"][2] * tau - 0.5 * gg * tau * tau
    if z <= g["r"]:
        a, b, c = -0.5 * gg, g["v0"][2], g["p0"][2] - g["r"]
        tl = (-b - (b * b - 4 * a * c) ** 0.5) / (2 * a)
        x = g["p0"][0] + g["v0"][0] * tl
        y = g["p0"][1] + g["v0"][1] * tl
        z = g["r"]
    return (x, y, z)


DUST_PER_WHEEL_PER_S = 160.0


def build_dust(states: list[dict], seed: int = 21) -> list[dict]:
    """Fine dust lifted by the tyres: many tiny motes that sink slowly (reduced
    gravity stands in for air drag) and disappear after a couple of seconds.
    Picture only."""
    rng = random.Random(seed)
    motes = []
    carry = {(a, s): 0.0 for a in range(len(AXLES_Y)) for s in range(2)}
    for i, st in enumerate(states):
        t = i / FPS
        s = sink(st["x"])
        if s <= 0.0 or st["v"] <= 0.0:
            continue
        for a, ay in enumerate(AXLES_Y):
            for side, wx in enumerate(WHEEL_X):
                carry[(a, side)] += DUST_PER_WHEEL_PER_S / FPS * (st["v"] / SPEED0) ** 0.5 * (s / SINK_MAX)
                while carry[(a, side)] >= 1.0:
                    carry[(a, side)] -= 1.0
                    sx = 1 if wx > 0 else -1
                    motes.append({
                        "t0": t + rng.random() / FPS, "life": rng.uniform(1.2, 3.0), "gscale": 0.10,
                        "p0": (wx + sx * rng.uniform(-0.1, 0.35), st["x"] + ay + rng.uniform(-0.4, 0.4), 0.08),
                        "v0": (sx * rng.uniform(0.1, 2.2), st["v"] * rng.uniform(0.05, 0.35),
                               rng.uniform(0.5, 2.4)),
                        "r": rng.uniform(0.012, 0.03)})
    return motes


def airborne(grains: list[dict], t: float) -> int:
    n = 0
    for g in grains:
        tau = t - g["t0"]
        if 0.0 <= tau and g["p0"][2] + g["v0"][2] * tau - 0.5 * G * tau * tau > g["r"] + 0.02:
            n += 1
    return n
