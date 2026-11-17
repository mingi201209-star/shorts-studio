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
#: Full film = 26.0 s = 780 frames at 30 fps, planned against the REAL spoken cues (audio-cues run): every replay segment starts on a spoken cue.
#: Segments 1-3 are the already validated opening (4.5 s -> cut at the cue "slow the car down" = frame 126); the later ones are replays of the SAME crash
#: (same physics, same sim) from the other cameras; each replay uses its own playback speed so that the crush fills the beat (no frozen frame, nothing invented).
T_MOTION_END_S = 0.09      # simulated time AFTER CONTACT at which the crumple car has stopped (stop time 87 ms; asserted against simulate() in the tests)
CONTACT_FILM_S = 0.30      # a replay shows the car touching the barrier 0.3 s after the cue (real onset inside the sync tolerance)
_REPLAYS = [               # id, first frame, last frame, panels, layout, camera (first frame = round(cue * 30) + 1)
    ("C2", 126, 223, ("crumple", "rigid"), "sequential", "compare"),   # "slow the car down"      4.17 s
    ("X2", 224, 365, ("crumple",), "full", "xray"),               # "For the same change"    7.42 s
    ("C3", 366, 502, ("crumple", "rigid"), "sequential", "compare"),   # "The rigid front stops" 12.15 s
    ("X3", 503, 586, ("crumple",), "full", "xray"),               # "The passenger"         16.72 s
    ("X4", 587, 690, ("crumple",), "full", "xray"),               # "while seat belts and"  19.53 s
    ("H2", 691, 744, ("crumple",), "full", "hero"),               # "The front is meant"    22.99 s
    ("X5", 745, 780, ("crumple",), "full", "xray"),               # "The cabin isn't."      24.80 s
]


def _replay(seg_id, first, last, panels, layout, camera):
    film_s = (last - first + 1) / FPS
    slow = T_MOTION_END_S / (1.03 * film_s - CONTACT_FILM_S)      # the motion lasts to the last frame of the segment: no frozen frame
    return {"id": seg_id, "first": first, "last": last, "lead_m": round(CONTACT_FILM_S * slow * V0_KMH / 3.6, 4), "slow": round(slow, 5), "panels": panels, "layout": layout, "camera": camera}


SEGMENTS = [
    {"id": "H", "first": 1, "last": 18, "lead_m": 0.30, "panels": ("crumple",), "layout": "full", "camera": "hero"},
    {"id": "C", "first": 19, "last": 60, "lead_m": 0.30, "panels": ("crumple", "rigid"), "layout": "sequential", "camera": "compare"},
    {"id": "X", "first": 61, "last": 125, "lead_m": 1.00, "panels": ("crumple",), "layout": "full", "camera": "xray"},      # contact 1.0 s into the segment (= 3.0 s, the cue "structures fold and"), crush finished before the cut at 4.17 s
] + [_replay(*r) for r in _REPLAYS]
TOTAL_FRAMES = SEGMENTS[-1]["last"]
XRAY_RAMP = (61, 91)       # frames over which the body turns into a ghost (scan line from the nose to the tail) - first X-ray segment only
#: (spoken cue text, picture event, first film frame): each event must start within SYNC_TOLERANCE_S of the cue (gate, measured speech timing)
SYNC_EVENTS = [("Inside, hidden", "scan-line X-ray reveal starts", 61), ("slow the car down", "comparison replay starts", 126), ("For the same change", "X-ray replay starts", 224),
               ("The rigid front stops", "rigid comparison replay starts", 366), ("The passenger", "X-ray view of the protected cabin starts", 503),
               ("while seat belts and", "second X-ray replay starts", 587), ("The front is meant", "hero replay of the front deforming starts", 691),
               ("The cabin isn't.", "closing X-ray view of the intact cabin starts", 745)]
SYNC_TOLERANCE_S = 0.4


def visible_panel(frame: int) -> str:
    """Exactly one full-screen car per comparison frame: crumple first, rigid second."""
    seg = segment_at(frame)
    if seg["layout"] != "sequential":
        return seg["panels"][0]
    midpoint = (seg["first"] + seg["last"] + 1) // 2
    return "crumple" if frame < midpoint else "rigid"


def visible_panels(frame: int) -> tuple[str, ...]:
    return (visible_panel(frame),)


def segment_at(frame: int) -> dict:
    for seg in SEGMENTS:
        if seg["first"] <= frame <= seg["last"]:
            return seg
    raise ValueError(frame)


def frame_time(frame: int) -> float:
    """Film frame (1-based) -> simulated time (s) since simulate()'s start."""
    seg = segment_at(frame)
    v0 = V0_KMH / 3.6
    if seg["layout"] == "sequential":
        # Each car gets its own approach, contact and stopping action.
        midpoint = (seg["first"] + seg["last"] + 1) // 2
        start = seg["first"] if frame < midpoint else midpoint
        beat_s = (midpoint - seg["first"] if frame < midpoint else seg["last"] - midpoint + 1) / FPS
        slow = T_MOTION_END_S / max(0.1, 1.03 * beat_s - CONTACT_FILM_S)
        lead_m = CONTACT_FILM_S * slow * v0
        return (LEAD_SIM - lead_m) / v0 + (frame - start) / FPS * slow
    return (LEAD_SIM - seg["lead_m"]) / v0 + (frame - seg["first"]) / FPS * seg.get("slow", SLOW)


def first_contact_film_s(seg_id: str = "H") -> float:
    seg = next(s for s in SEGMENTS if s["id"] == seg_id)
    return seg["lead_m"] / (V0_KMH / 3.6) / seg.get("slow", SLOW)


def xray_factor(frame: int) -> float:
    """0 outside the X-ray segments; the first X-ray segment ramps the scan line in, the later ones are X-ray from their first frame."""
    seg = segment_at(frame)
    if seg["camera"] != "xray":
        return 0.0
    if seg["id"] != "X":
        return 1.0
    a, b = XRAY_RAMP
    if frame <= a:
        return 0.0
    return 1.0 if frame >= b else (frame - a) / (b - a)
