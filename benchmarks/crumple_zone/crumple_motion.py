"""EP.04 crumple zone: one-dimensional frontal-crash simulation and the geometric crush map. Pure Python/numpy (no Blender), shared by the renderer and the gates.

Simplified and NOT calibrated to any real vehicle or crash test: a car of mass M hits a rigid barrier at V0. The nose structure crushes against a force-stroke
curve (short linear ramp, then a constant plateau); the plateau is set so the car stops after a chosen stroke. The "rigid" comparison car has the same mass, speed
and barrier but a stroke of a few centimetres. Both are hypothetical counterfactuals, not measured crash tests."""
from __future__ import annotations

import os

import numpy as np

FPS = 30
RENDER_HZ = 2000            # the crash lasts <0.1 s and the film slows it down: pose sampling must be far finer than the frame rate (EP.03 stutter lesson)
G = 9.81
V0_KMH = 50.0
MASS = 1400.0
RAMP = 0.06                 # m of stroke over which the crush force builds up
PROFILES = {
    "crumple": {"stroke": 0.62, "rebound": 0.0, "label": "CRUMPLE"},
    "rigid": {"stroke": 0.05, "rebound": 0.25, "label": "RIGID"},
}
CRUSH_LENGTH = 0.95         # m of nose structure ahead of the passenger cell that may crush
COMPACTION = 0.75           # fraction of the crushed zone that is squeezed out at full crush
LEAD_SIM = 1.2              # simulate() starts the nose this far from the barrier


def simulate(profile: str, v0_kmh: float = V0_KMH, mass: float = MASS, lead: float = LEAD_SIM, hz: int = RENDER_HZ, tail_s: float = 0.25) -> dict:
    """d = distance the car has moved since the start (cabin reference), s = permanent crush stroke, a = deceleration in g."""
    p = PROFILES[profile]
    v0 = v0_kmh / 3.6
    stroke = p["stroke"]
    f0 = 0.5 * mass * v0 * v0 / (stroke - 0.5 * RAMP)      # plateau force that absorbs the kinetic energy exactly within `stroke`
    dt = 1e-5
    n_out = int((lead / v0 + 6 * stroke / v0 + tail_s) * hz)
    t_arr, d_arr, s_arr, v_arr, a_arr = (np.zeros(n_out) for _ in range(5))
    d, v, s, t, next_i, a = 0.0, v0, 0.0, 0.0, 0, 0.0
    rebounded = False
    while next_i < n_out:
        if d > lead:
            s = max(s, d - lead)
        if d > lead and v > 0 and not rebounded:
            f = f0 * min(1.0, (d - lead) / RAMP)
            a = f / mass
            v -= a * dt
            if v <= 0:
                v, rebounded, a = -p["rebound"] * v0, True, 0.0
        elif v < 0 and d > lead:
            a = 0.0
        else:
            a = 0.0 if v > 0 or rebounded else a
        d += v * dt
        t += dt
        if t * hz >= next_i:
            t_arr[next_i], d_arr[next_i], s_arr[next_i], v_arr[next_i], a_arr[next_i] = t, d, s, v, a / G
            next_i += 1
    return {"t": t_arr, "d": d_arr, "s": s_arr, "v": v_arr, "g": a_arr, "lead": lead, "v0": v0, "mass": mass, "stroke": stroke, "hz": hz}


def summary(rec: dict) -> dict:
    stop = int(np.argmax(rec["v"] <= 0)) if np.any(rec["v"] <= 0) else len(rec["t"]) - 1
    contact = int(np.argmax(rec["d"] > rec["lead"]))
    t_stop = float(rec["t"][stop] - rec["t"][contact])
    return {"peak_g": float(rec["g"].max()), "stop_time_s": t_stop, "stroke_m": float(rec["s"].max()),
            "average_decel_g": float(rec["v0"] / t_stop / G) if t_stop > 0 else float("inf"),
            "average_force_kn": float(rec["mass"] * rec["v0"] / t_stop / 1000.0) if t_stop > 0 else float("inf")}


def crush_map(p0: np.ndarray, s: float, nose: float, length: float = CRUSH_LENGTH, rho: float = COMPACTION, cabin_y: float | None = None) -> np.ndarray:
    """Car-frame crush of the nose: points within the compaction depth d_c = s / rho behind the nose are squeezed (linear map) so the nose ends s further back,
    with buckling (hood folds up, fenders bulge); everything deeper is untouched, so the passenger cell never moves. p0: (N, 3) points in the car frame, +Y forward."""
    p = p0.copy()
    if s <= 1e-9:
        return p
    d_c = min(s / rho, length)
    s = min(s, rho * d_c)
    y, z, x = p0[:, 1], p0[:, 2], p0[:, 0]
    depth = nose - y
    inside = (depth > -0.05) & (depth < d_c)      # points a hair ahead of the measured nose (float error, plate thickness) are pushed back with the nose
    u = np.clip(depth / d_c, 0.0, 1.0)
    p[:, 1] = np.where(inside, (nose - d_c) + (1.0 - u) * (d_c - s), y)
    prog = min(1.0, d_c / length)
    lobe = np.sin(np.pi * u)
    ripple = np.sin(11.0 * u + 3.0 * x)
    hood = (z > 0.62).astype(float)
    dz = prog * (0.30 * lobe * hood * (1.0 - 0.5 * u) + 0.03 * ripple * lobe) - 0.05 * prog * (1.0 - hood) * (1.0 - u)
    p[:, 2] = np.where(inside, z + dz, z)
    p[:, 0] = np.where(inside, x * (1.0 + 0.14 * prog * lobe), x)
    return p


def wheel_y(y_wheel: float, s: float, nose: float, radius: float = 0.281, clearance: float = 0.02) -> float:
    """Front wheel position after a crush of stroke s: the tyre is rigid, so once the crushed nose line (nose - s) reaches the front of the tyre the wheel is pushed back with it
    (it never ends up in front of the crushed nose, i.e. never through the barrier)."""
    return min(y_wheel, nose - s - radius - clearance)


# ----------------------------------------------------------------------------- film timeline (preview of the first 4.5 s = 135 frames at 30 fps)
SLOW = 0.09
FILM = os.environ.get("EP04_FILM", "preview")
#: (id, first frame, last frame, lead_m (nose distance to the barrier at the segment's first frame), profiles drawn, layout)
SEGMENTS = [
    {"id": "H", "first": 1, "last": 18, "lead_m": 0.30, "panels": ("crumple",), "layout": "full", "camera": "hero"},
    {"id": "C", "first": 19, "last": 60, "lead_m": 0.30, "panels": ("crumple", "rigid"), "layout": "stack", "camera": "compare"},
    {"id": "X", "first": 61, "last": 135, "lead_m": 1.00, "panels": ("crumple",), "layout": "full", "camera": "xray"},
]
TOTAL_FRAMES = SEGMENTS[-1]["last"]
XRAY_RAMP = (61, 91)       # frames over which the body turns into a ghost (scan line from the nose to the tail)
#: (spoken cue text, picture event, first film frame): each event must start within SYNC_TOLERANCE_S of the cue (gate, measured speech timing)
SYNC_EVENTS = [("Inside, hidden", "scan-line X-ray reveal starts", 61)]
SYNC_TOLERANCE_S = 0.4


def segment_at(frame: int) -> dict:
    for seg in SEGMENTS:
        if seg["first"] <= frame <= seg["last"]:
            return seg
    raise ValueError(frame)


def frame_time(frame: int) -> float:
    """Film frame (1-based) -> simulated time (s) since simulate()'s start."""
    seg = segment_at(frame)
    v0 = V0_KMH / 3.6
    return (LEAD_SIM - seg["lead_m"]) / v0 + (frame - seg["first"]) / FPS * SLOW


def first_contact_film_s(seg_id: str = "H") -> float:
    seg = next(s for s in SEGMENTS if s["id"] == seg_id)
    return seg["lead_m"] / (V0_KMH / 3.6) / SLOW


def xray_factor(frame: int) -> float:
    a, b = XRAY_RAMP
    if frame <= a:
        return 0.0
    return 1.0 if frame >= b else (frame - a) / (b - a)


# ----------------------------------------------------------------------------- explanatory models (NOT crash-test results)
TIME_BAR_SCALE = 7.0          # m of road drawn per second of (real) stopping time, the same for both cars: bar length is proportional to the stopping time
ARROW_PER_KN = 1.9 / 3535.0    # m of arrow per kN of AVERAGE stopping force (linear): the rigid car's ~3500 kN is a 1.9 m arrow, the crumple car's ~220 kN about 0.12 m


def stop_phase(rec: dict) -> tuple[int, int]:
    """(index of first contact, index at which the car has stopped) in a simulation record."""
    contact = int(np.argmax(rec["d"] > rec["lead"]))
    stop = int(np.argmax(rec["v"] <= 0)) if np.any(rec["v"] <= 0) else len(rec["t"]) - 1
    return contact, stop


def stopping_distance_time(rec: dict, i: int) -> tuple[float, float]:
    """Stopping distance (m) and stopping time (s) the car has used up at sample i (both grow from first contact until the car has stopped, then hold)."""
    contact, stop = stop_phase(rec)
    j = min(i, stop)
    if j <= contact:
        return 0.0, 0.0
    return float(rec["s"][j]), float(rec["t"][j] - rec["t"][contact])


def average_force_kn(profile: str) -> float:
    return summary(simulate(profile))["average_force_kn"]


# simplified occupant held by a belt and an airbag in the CRUMPLE car: relative motion in the car frame, m x'' = m a_decel - belt - airbag
OCC = {"mass": 75.0, "belt_k": 55e3, "belt_c": 1.8e3, "bag_gap": 0.22, "bag_k": 120e3, "bag_c": 2.5e3, "bag_fire_s": 0.012}


def occupant_sim(rec: dict) -> dict:
    """Forward travel x (m) of the occupant relative to the car, sampled like the record. Belt: spring + damper from the start of the crash; airbag: fires bag_fire_s after first
    contact and pushes back once the occupant has travelled bag_gap."""
    dt = 1.0 / rec["hz"]
    contact, _ = stop_phase(rec)
    x = v = 0.0
    out = np.zeros(len(rec["t"]))
    for i in range(len(rec["t"])):
        t_since = rec["t"][i] - rec["t"][contact]
        a_car = rec["g"][i] * G                               # deceleration of the car (the occupant is pushed forward relative to it)
        f = OCC["belt_k"] * x + OCC["belt_c"] * v
        if t_since > OCC["bag_fire_s"] and x > OCC["bag_gap"]:
            f += OCC["bag_k"] * (x - OCC["bag_gap"]) + OCC["bag_c"] * v
        sub = 20
        for _ in range(sub):
            a = a_car - f / OCC["mass"] if rec["t"][i] >= rec["t"][contact] else 0.0
            v += a * dt / sub
            x = max(0.0, x + v * dt / sub)
            if x == 0.0 and v < 0:
                v = 0.0
        out[i] = x
    return {"x": out, "bag_open": np.array([1.0 if rec["t"][i] - rec["t"][contact] > OCC["bag_fire_s"] and rec["t"][i] >= rec["t"][contact] else 0.0 for i in range(len(rec["t"]))])}
