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
CAR = {"ms": 400.0, "mu": 40.0, "ks": 22000.0, "cs": 1500.0, "kt": 200000.0, "wheelbase": 2.7, "track": 1.55}
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


def simulate(bump: dict, speed_kmh: float = SPEED_KMH, car: dict = CAR, lead_m: float = 3.0, tail_s: float = 3.2, hz: int = FPS):
    """Return dict of arrays sampled at `hz` (real time; the film is slowed down, so the renderer asks for a much higher rate than FPS or the pose would hold for several frames and the picture would judder): t, x (front axle, m, 0 = bump start), z_body_front/rear (m), body_height, pitch (rad),
    wheel_front/rear road height (m), body acceleration (g) at the front axle."""
    v = speed_kmh / 3.6
    wb = car["wheelbase"]
    total = (lead_m + bump["length"] + wb) / v + tail_s
    n = int(total / DT)
    out_n = int(total * hz) + 1
    state = {"f": [0.0] * 4, "r": [0.0] * 4}  # zs, vs, zu, vu
    rec = {k: np.zeros(out_n) for k in ("t", "x", "zf", "zr", "wf", "wr", "gf")}
    next_i = 0
    af = 0.0
    for i in range(n):
        t = i * DT
        for key, delay in (("f", 0.0), ("r", wb / v)):
            x = v * (t - delay) - lead_m
            zr = profile(x, bump)
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
            rec["wf"][next_i] = profile(v * t - lead_m, bump)
            rec["wr"][next_i] = profile(v * (t - wb / v) - lead_m, bump)
            rec["gf"][next_i] = af / G
            next_i += 1
    rec["body"] = 0.5 * (rec["zf"] + rec["zr"])
    rec["pitch"] = np.arctan2(rec["zf"] - rec["zr"], wb)
    rec["speed"] = v
    return rec


def summary(rec) -> dict:
    return {"peak_body_g": float(np.max(np.abs(rec["gf"]))), "peak_body_rise_m": float(np.max(np.abs(rec["body"]))),
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
        out[seg["id"]] = {k: summary(simulate(b, speed_kmh=seg["kmh"], car=car)) for k, b in BUMPS.items()}
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
    # "explain" = the X-ray film plus two new principle scenes (the wheel's own path over each bump, the roof's path afterwards) and no repeated passes.
    SEGMENTS = [
        {"id": "A", "kmh": 20.0, "slow": 0.17, "frames": 300, "lead_m": 1.4},    # intro, dive to the wheel, body turns translucent
        {"id": "P", "kmh": 20.0, "slow": 0.22, "frames": 200, "lead_m": 1.4},    # NEW: the wheel's path (hub trail), X-ray still on
        {"id": "B", "kmh": 30.0, "slow": 0.50, "frames": 170, "lead_m": 1.4},    # thirty km/h, roof trail, body opaque again
        {"id": "C", "kmh": 10.0, "slow": 0.60, "frames": 160, "lead_m": 1.4},    # ten km/h
        {"id": "E", "kmh": 20.0, "slow": 0.25, "frames": 250, "lead_m": 1.4},    # closing: same height, how quickly it lifts
    ]
    PASS_FRAMES = sum(x["frames"] for x in SEGMENTS)
    SHOTS = [
        (1, 105, "rear3q", "side"), (106, 300, "wheel", "side"),
        (301, 410, "profile", "stack"), (411, 500, "front3q", "side"),
        (501, 590, "side", "stack"), (591, 670, "tyre", "side"),
        (671, 750, "top", "side"), (751, 830, "high3q", "side"),
        (831, 930, "tyre", "stack"), (931, 1010, "front3q", "side"), (1011, 1080, "side", "stack"),
    ]
    XRAY_RAMPS = (139, 171, 480, 505)
    TRAILS = [(301, 500, "hub"), (501, 830, "roof")]
    BEAT_PICTURE_START = {3: 301, 4: 501, 5: 671, 6: 831}
    BEAT2_BEFORE_FRAME = 300
    FILM_FILES = {"video": "speed-bump-explain.mp4", "review": "speed-bump-explain-540x960-review.mp4", "validation": "speed-bump-explain-validation.json"}


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
