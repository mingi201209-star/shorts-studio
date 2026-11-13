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
