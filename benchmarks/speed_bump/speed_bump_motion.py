"""EP.03 speed bumps: motion model for the side-by-side comparison (pure Python/numpy, no Blender).

Two identical cars, same speed, same bump height; only the bump LENGTH differs. Each axle is a quarter-car (sprung mass on a spring and damper,
unsprung mass on a tyre spring); the rear axle meets the bump WHEELBASE/v after the front. Body height and pitch come from the two axle responses.
Values are assumed for a typical passenger car and are NOT calibrated ("physically_calibrated": False): the film may say "simulation, assumed car",
never "this is what your car feels".
"""
from __future__ import annotations

import math
import os

import numpy as np

G = 9.81
CAR = {"ms": 400.0, "mu": 40.0, "ks": 22000.0, "cs": 1500.0, "kt": 200000.0, "wheelbase": 2.7, "track": 1.55, "tyre_radius": 0.281}
BUMPS = {
    "short": {"label": "SHORT BUMP", "length": 0.9, "height": 0.075, "kind": "round"},
    "hump": {"label": "LONG HUMP", "length": 3.7, "height": 0.075, "kind": "round"},
}
SPEED_KMH = 20.0
DT = 1e-4
FPS = 30
RENDER_HZ = 600   # pose sampling rate for rendering (slow-motion needs far more than 30 samples/s)


def profile(x: float, bump: dict) -> float:
    if x < 0.0 or x > bump["length"]:
        return 0.0
    return bump["height"] * math.sin(math.pi * x / bump["length"])


_HUB_TABLES: dict = {}


def hub_profile(x: float, bump: dict, radius: float) -> float:
    """Height of the wheel CENTRE (above its rest height) of a rigid round tyre rolling over the bump: the envelope of the road, not the road under the axle.
    A tyre of radius R touches the bump face before its axle is above it, so the hub path is smoother and starts earlier than the road profile. The simulation
    uses this as the road input and the renderer uses it to place the wheel, so the tyre never cuts into the bump."""
    key = (bump["length"], bump["height"], radius)
    tab = _HUB_TABLES.get(key)
    if tab is None:
        dx = 0.001
        x0 = -radius - dx
        n = int((bump["length"] + 2 * radius) / dx) + 4
        xs = x0 + dx * np.arange(n)
        xr = np.arange(0.0, bump["length"] + dx, dx)
        zr = bump["height"] * np.sin(np.pi * xr / bump["length"])
        hub = np.zeros(n)
        for i, xc in enumerate(xs):
            m = np.abs(xr - xc) <= radius
            if m.any():
                hub[i] = max(0.0, float(np.max(zr[m] + np.sqrt(radius ** 2 - (xr[m] - xc) ** 2)) - radius))
        tab = (x0, dx, hub)
        _HUB_TABLES[key] = tab
    x0, dx, hub = tab
    i = int((x - x0) / dx)
    return float(hub[i]) if 0 <= i < len(hub) else 0.0


def simulate(bump: dict, speed_kmh: float = SPEED_KMH, car: dict = CAR, lead_m: float = 3.0, tail_s: float = 3.2, hz: int = FPS):
    """Return dict of arrays sampled at `hz` (real time; the film is slowed down, so the renderer asks for a much higher rate than FPS or the pose would hold for several frames and the picture would judder): t, x (front axle, m, 0 = bump start), z_body_front/rear (m), body_height, pitch (rad),
    wheel_front/rear road height (m), body acceleration (g) at the front axle."""
    v = speed_kmh / 3.6
    wb = car["wheelbase"]
    total = (lead_m + bump["length"] + wb) / v + tail_s
    n = int(total / DT)
    out_n = int(total * hz) + 1
    state = {"f": [0.0] * 4, "r": [0.0] * 4}  # zs, vs, zu, vu
    rec = {k: np.zeros(out_n) for k in ("t", "x", "zf", "zr", "wf", "wr", "gf", "uf", "ur")}
    next_i = 0
    af = 0.0
    for i in range(n):
        t = i * DT
        for key, delay in (("f", 0.0), ("r", wb / v)):
            x = v * (t - delay) - lead_m
            zr = hub_profile(x, bump, car.get("tyre_radius", CAR["tyre_radius"]))
            zs, vs, zu, vu = state[key]
            fs = car["ks"] * (zu - zs) + car["cs"] * (vu - vs)
            ft = car["kt"] * (zr - zu)
            a_s = fs / car["ms"]
            a_u = (-fs + ft) / car["mu"]
            vs += a_s * DT
            zs += vs * DT
            vu += a_u * DT
            zu += vu * DT
            state[key] = [zs, vs, zu, vu]
            if key == "f":
                af = a_s
        if i * DT * hz >= next_i and next_i < out_n:
            rec["t"][next_i] = t
            rec["x"][next_i] = v * t - lead_m
            rec["zf"][next_i] = state["f"][0]
            rec["zr"][next_i] = state["r"][0]
            rec["wf"][next_i] = hub_profile(v * t - lead_m, bump, car.get("tyre_radius", CAR["tyre_radius"]))
            rec["wr"][next_i] = hub_profile(v * (t - wb / v) - lead_m, bump, car.get("tyre_radius", CAR["tyre_radius"]))
            rec["uf"][next_i] = state["f"][2]
            rec["ur"][next_i] = state["r"][2]
            rec["gf"][next_i] = af / G
            next_i += 1
    rec["df"] = rec["zf"] - rec["uf"]      # spring deflection (sprung minus unsprung), front / rear
    rec["dr"] = rec["zr"] - rec["ur"]
    rec["body"] = 0.5 * (rec["zf"] + rec["zr"])
    rec["pitch"] = np.arctan2(rec["zf"] - rec["zr"], wb)
    rec["speed"] = v
    return rec


def summary(rec) -> dict:
    dt = float(rec["t"][1] - rec["t"][0])
    spring_rate = float(np.max(np.abs(np.gradient(rec["df"], dt))))     # how fast the spring is squeezed (m/s)
    hub_rate = float(np.max(np.abs(np.gradient(rec["wf"], dt))))        # how fast the road lifts the wheel (m/s)
    return {"peak_spring_rate_ms": spring_rate, "peak_hub_rate_ms": hub_rate, "peak_spring_deflection_m": float(np.max(np.abs(rec["df"]))), "peak_body_g": float(np.max(np.abs(rec["gf"]))), "peak_body_rise_m": float(np.max(np.abs(rec["body"]))),
            "peak_pitch_deg": float(np.degrees(np.max(np.abs(rec["pitch"]))))}


CLAIMS = {"physically_calibrated": False, "assumed": "typical passenger car, 7.5 cm bump height, 20 km/h"}


# ----------------------------------------------------------------------------- film timeline (960 frames at 30 fps = 32 s)
TOTAL_FRAMES = 960
#: five slow-motion passes of the SAME car over the SAME two bumps; only the approach speed changes. `lead_m`: how far before the bump the front axle starts;
#: `slow`: playback rate (the film shows the simulation `slow` times as fast as real time). A property of the shot, not of the physics.
SEGMENTS = [
    {"id": "A", "kmh": 20.0, "slow": 0.25, "frames": 296, "lead_m": 1.4},
    {"id": "B", "kmh": 30.0, "slow": 0.50, "frames": 160, "lead_m": 1.4},
    {"id": "C", "kmh": 10.0, "slow": 0.60, "frames": 160, "lead_m": 1.4},
    {"id": "D", "kmh": 20.0, "slow": 0.50, "frames": 160, "lead_m": 1.4},
    {"id": "E", "kmh": 30.0, "slow": 0.50, "frames": 184, "lead_m": 1.4},
]
PASS_FRAMES = sum(s["frames"] for s in SEGMENTS)   # every frame is a rendered pass: no charts, no text, only the 3D scene
SIM_LEAD_M = 3.0   # simulate() starts the front axle 3 m before the bump

#: camera work. layout "stack": long hump on top, short bump below (1080x700 each); "side": long hump left, short bump right (540x1400 each).
#: (first frame, last frame, camera kind, layout)
SHOTS = [
    (1, 105, "rear3q", "side"), (106, 210, "side", "stack"), (211, 296, "wheel", "side"),
    (297, 376, "front3q", "side"), (377, 456, "side", "stack"),
    (457, 536, "rear3q", "side"), (537, 616, "wheel", "side"),
    (617, 696, "top", "side"), (697, 776, "front3q", "side"),
    (777, 856, "rear3q", "side"), (857, 960, "side", "stack"),
]


def shot_at(frame: int) -> tuple[str, str]:
    for a, b, kind, layout in SHOTS:
        if a <= frame <= b:
            return kind, layout
    raise ValueError(frame)


def frame_to_pass(frame: int) -> tuple[dict, float]:
    """Film frame (1-based) -> (segment, simulated time in s measured from simulate()'s start)."""
    n = frame - 1
    for seg in SEGMENTS:
        if n < seg["frames"]:
            v = seg["kmh"] / 3.6
            t0 = (SIM_LEAD_M - seg["lead_m"]) / v
            return seg, t0 + n / FPS * seg["slow"]
        n -= seg["frames"]
    raise ValueError(frame)


def pass_summaries(car: dict = CAR) -> dict:
    """Peak numbers per pass and bump, from the same simulation that poses the cars (used by narration and gates)."""
    out = {}
    for seg in SEGMENTS:
        out[seg["id"]] = {k: summary(simulate(b, speed_kmh=seg["kmh"], car=car, hz=RENDER_HZ)) for k, b in BUMPS.items()}
    return out


# ----------------------------------------------------------------------------- film profiles
#: "v1" = the finished film (exterior only). "xray" (env EP03_FILM=xray) = the X-ray explainer: the body turns translucent while the narration says
#: "look inside" and a spring + damper per wheel shows how the simulated suspension moves. The profile only changes the timeline; physics is identical.
FILM = os.environ.get("EP03_FILM", "v1")
#: (first frame, last frame) of the frames over which the body fades to translucent and back (0 = never)
XRAY_RAMPS = (0, 0, 0, 0)
#: spoken beat -> the first frame of the picture it talks about, and the frame before which beat 2 must start
BEAT_PICTURE_START = {3: 297, 4: 457, 5: 617, 6: 777}
BEAT2_BEFORE_FRAME = 296
SYNC_EVENTS: list = []      # film profiles with cue-synced picture events fill this in (see "final")
SYNC_TOLERANCE_S = 0.4
FILM_FILES = {"video": "speed-bump-shapes.mp4", "review": "speed-bump-540x960-review.mp4", "validation": "speed-bump-validation.json"}

if FILM == "xray":
    SEGMENTS = [
        {"id": "A", "kmh": 20.0, "slow": 0.17, "frames": 300, "lead_m": 1.4},    # 0-10.0 s: intro, dive to the wheel, body turns translucent
        {"id": "A2", "kmh": 20.0, "slow": 0.25, "frames": 188, "lead_m": 1.4},   # 10.0-16.3 s: "squeezes the spring in a flash / slowly"
        {"id": "B", "kmh": 30.0, "slow": 0.50, "frames": 157, "lead_m": 1.4},    # 16.3-21.5 s: thirty kilometres per hour
        {"id": "C", "kmh": 10.0, "slow": 0.60, "frames": 155, "lead_m": 1.4},    # 21.5-26.7 s: at ten
        {"id": "D", "kmh": 30.0, "slow": 0.50, "frames": 160, "lead_m": 1.4},    # 26.7-32.0 s: back to the exterior
    ]
    PASS_FRAMES = sum(x["frames"] for x in SEGMENTS)
    SHOTS = [
        (1, 105, "rear3q", "side"), (106, 190, "wheel", "side"), (191, 300, "side", "stack"),
        (301, 380, "wheel", "side"), (381, 488, "side", "stack"),
        (489, 566, "wheel", "side"), (567, 645, "side", "stack"),
        (646, 705, "wheel", "side"), (706, 800, "rear3q", "side"),
        (801, 880, "front3q", "side"), (881, 960, "side", "stack"),
    ]
    XRAY_RAMPS = (139, 171, 690, 720)
    BEAT_PICTURE_START = {3: 301, 4: 489, 5: 646, 6: 801}
    BEAT2_BEFORE_FRAME = 300
    FILM_FILES = {"video": "speed-bump-xray.mp4", "review": "speed-bump-xray-540x960-review.mp4", "validation": "speed-bump-xray-validation.json"}


#: frames over which a 3D trail (a glowing tube) is drawn behind a moving point: (first, last, "hub" = front wheel hub, "roof" = roof of the car)
TRAILS: list = []

if FILM == "explain":
    # "explain" = the X-ray film plus a new principle scene (the wheel's own path over each bump, drawn as a glowing 3D tube) and no repeated passes.
    # Frame boundaries follow the measured spoken beat starts [0, 4.59, 10.62, 16.8, 24.13, 29.27] s of a 36.5 s film (audio check 2).
    SEGMENTS = [
        {"id": "A", "kmh": 20.0, "slow": 0.17, "frames": 317, "lead_m": 1.4},    # intro, dive to the wheel, body turns translucent
        {"id": "P", "kmh": 20.0, "slow": 0.22, "frames": 188, "lead_m": 1.4},    # NEW: the wheel's path (hub trail), X-ray still on
        {"id": "B", "kmh": 30.0, "slow": 0.40, "frames": 220, "lead_m": 1.4},    # thirty km/h, body opaque again
        {"id": "C", "kmh": 10.0, "slow": 0.60, "frames": 156, "lead_m": 1.4},    # ten km/h
        {"id": "E", "kmh": 20.0, "slow": 0.25, "frames": 214, "lead_m": 1.4},    # closing: same height, how quickly it lifts
    ]
    PASS_FRAMES = sum(x["frames"] for x in SEGMENTS)
    SHOTS = [
        (1, 105, "rear3q", "side"), (106, 205, "wheel", "side"), (206, 317, "front3q", "side"),
        (318, 420, "profile", "stack"), (421, 505, "rear3q", "side"),
        (506, 590, "side", "stack"), (591, 660, "tyre", "side"), (661, 725, "top", "side"),
        (726, 800, "high3q", "side"), (801, 881, "profile", "stack"),
        (882, 970, "tyre", "stack"), (971, 1040, "high3q", "side"), (1041, 1095, "side", "stack"),
    ]
    XRAY_RAMPS = (139, 171, 480, 505)
    TRAILS = [(318, 1095, "hub")]
    BEAT_PICTURE_START = {3: 318, 4: 506, 5: 726, 6: 882}
    BEAT2_BEFORE_FRAME = 317
    FILM_FILES = {"video": "speed-bump-explain.mp4", "review": "speed-bump-explain-540x960-review.mp4", "validation": "speed-bump-explain-validation.json"}


if FILM == "reveal":
    # "reveal" = the explain film re-cut after the owner's review: full-height 1080x1920 picture (captions sit on the picture, no black band), a first three seconds
    # with both cars big over their bumps followed at once by the scan-line X-ray reveal, springs that glow with their compression, a tight spring close-up.
    # 35.0 s / 1050 frames; frame boundaries follow the measured spoken beat starts (a longer film adds slack = silence and breaks the total-silence gate).
    BEAT_STARTS_S = [0.0, 4.47, 10.51, 16.71, 24.06, 29.23]
    SEGMENTS = [
        {"id": "A", "kmh": 20.0, "slow": 0.17, "frames": 315, "lead_m": 1.4},
        {"id": "P", "kmh": 20.0, "slow": 0.22, "frames": 186, "lead_m": 1.4},
        {"id": "B", "kmh": 30.0, "slow": 0.40, "frames": 221, "lead_m": 1.4},
        {"id": "C", "kmh": 10.0, "slow": 0.60, "frames": 155, "lead_m": 1.4},
        {"id": "E", "kmh": 20.0, "slow": 0.25, "frames": 173, "lead_m": 1.4},
    ]
    PASS_FRAMES = sum(x["frames"] for x in SEGMENTS)
    SHOTS = [
        (1, 120, "low3q", "stack"), (121, 215, "spring", "stack"), (216, 315, "front3q", "stack"),
        (316, 410, "profile", "stack"), (411, 501, "wheel", "stack"),
        (502, 585, "side", "stack"), (586, 655, "tyre", "side"), (656, 722, "top", "side"),
        (723, 795, "high3q", "stack"), (796, 877, "profile", "stack"),
        (878, 960, "tyre", "stack"), (961, 1010, "low3q", "stack"), (1011, 1050, "side", "stack"),
    ]
    XRAY_RAMPS = (88, 118, 700, 722)
    TRAILS = [(316, 1050, "hub")]
    BEAT_PICTURE_START = {3: 316, 4: 502, 5: 723, 6: 878}
    BEAT2_BEFORE_FRAME = 315
    FILM_FILES = {"video": "speed-bump-reveal.mp4", "review": "speed-bump-reveal-540x960-review.mp4", "validation": "speed-bump-reveal-validation.json"}


if FILM == "final":
    # "final" = the quality-improvement cut: ONE condition for the whole film (same car, 20 km/h, same suspension, same 7.5 cm height; only the bump LENGTH differs),
    # one playback rate (slow = 0.2) for every pass, wheel placed on the tyre-envelope path (no tyre cutting into the bump), spring colour = squeeze RATE.
    # 31.0 s / 930 frames. Boundaries and events follow the measured spoken cues (audio check 2: beat starts 0, 4.603, 10.717, 16.208, 22.155, 26.085 s).
    SEGMENTS = [
        {"id": "A", "kmh": 20.0, "slow": 0.20, "frames": 141, "lead_m": 0.7},    # beat 1: the first wheel/bump contact is at 0.6 s (impact and body reaction from the start)
        {"id": "A2", "kmh": 20.0, "slow": 0.20, "frames": 181, "lead_m": 2.2},   # beat 2: scan-line reveal while the car approaches; the front wheel meets the bump at frame ~201, as the spring close-up starts
        {"id": "P", "kmh": 20.0, "slow": 0.20, "frames": 164, "lead_m": 1.0},    # beat 3: the wheel path, four times faster
        {"id": "B", "kmh": 20.0, "slow": 0.20, "frames": 178, "lead_m": 1.0},    # beat 4: spring squeezed twice as fast, body jolt
        {"id": "C", "kmh": 20.0, "slow": 0.20, "frames": 118, "lead_m": 1.0},    # beat 5: exterior, smooth lift vs kick
        {"id": "E", "kmh": 20.0, "slow": 0.20, "frames": 148, "lead_m": 1.0},    # beat 6: replay of both bumps side by side, same conditions
    ]
    PASS_FRAMES = sum(x["frames"] for x in SEGMENTS)
    #: every shot is a different camera from its neighbours; shots that show the ghost body look DOWN onto asphalt (not at sky); wide shots carry the LONG / SHORT signs
    SHOTS = [
        (1, 60, "low3q", "stack"), (61, 141, "rear3q", "stack"),
        (142, 202, "high3q", "stack"), (203, 262, "spring", "stack"), (263, 322, "front3q_hi", "stack"),
        (323, 407, "profile", "stack"), (408, 486, "left", "stack"), (487, 576, "side_xray", "stack"),
        (577, 664, "front3q", "stack"), (665, 732, "rear3q", "stack"), (733, 782, "high3q", "stack"),
        (783, 860, "side", "stack"), (861, 930, "side_far", "stack"),
    ]
    XRAY_RAMPS = (142, 172, 650, 675)
    TRAILS = [(323, 782, "hub"), (783, 930, "both")]
    BEAT_PICTURE_START = {3: 323, 4: 487, 5: 665, 6: 783}
    BEAT2_BEFORE_FRAME = 322
    #: (spoken cue text, picture event, film frame where the event starts): each event must start within SYNC_TOLERANCE_S of the cue's start (gate)
    SYNC_EVENTS = [
        ("Now look inside where", "scan-line reveal starts", 142),
        ("a spring and a damper", "spring and damper close-up", 203),
        ("The wheel has to", "wheel path trail starts", 323),
        ("The spring is squeezed", "side view of the spring with rest-length marks", 487),
        ("The long hump lifts", "body opaque again, exterior view", 665),
        ("What matters is how", "side-by-side replay with hub and body trails", 783),
    ]
    SYNC_TOLERANCE_S = 0.4
    FILM_FILES = {"video": "speed-bump-final.mp4", "review": "speed-bump-final-540x960-review.mp4", "validation": "speed-bump-final-validation.json"}


TOTAL_FRAMES = PASS_FRAMES   # every film frame is a rendered pass, whichever profile is active


#: the rendered wheel follows the rigid tyre envelope: it never cuts into the bump and never floats by more than this (m). The simulated tyre compliance
#: (up to about 2 cm) is not drawn, so a frame can never show a tyre inside the bump or above it.
VISUAL_CONTACT_TOL_M = 0.004


def visual_wheel_z(u: float, envelope: float) -> float:
    return min(max(float(u), float(envelope) - VISUAL_CONTACT_TOL_M), float(envelope) + VISUAL_CONTACT_TOL_M)


def trail_mode(frame: int):
    for a, b, kind in TRAILS:
        if a <= frame <= b:
            return kind
    return None


def xray_factor(frame: int) -> float:
    """0 = opaque exterior, 1 = fully translucent with the suspension showing."""
    a, b, c, d = XRAY_RAMPS
    if a == 0 and b == 0:
        return 0.0
    if frame <= a:
        return 0.0
    if frame < b:
        return (frame - a) / (b - a)
    if frame <= c:
        return 1.0
    if frame < d:
        return 1.0 - (frame - c) / (d - c)
    return 0.0
