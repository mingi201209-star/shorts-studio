"""EP.03 speed bumps: motion model for the side-by-side comparison (pure Python/numpy, no Blender).

Two identical cars, same speed, same bump height; only the bump LENGTH differs. Each axle is a quarter-car (sprung mass on a spring and damper,
unsprung mass on a tyre spring); the rear axle meets the bump WHEELBASE/v after the front. Body height and pitch come from the two axle responses.
Values are assumed for a typical passenger car and are NOT calibrated ("physically_calibrated": False): the film may say "simulation, assumed car",
never "this is what your car feels".
"""
from __future__ import annotations

import math

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


def profile(x: float, bump: dict) -> float:
    if x < 0.0 or x > bump["length"]:
        return 0.0
    return bump["height"] * math.sin(math.pi * x / bump["length"])


def simulate(bump: dict, speed_kmh: float = SPEED_KMH, car: dict = CAR, lead_m: float = 3.0, tail_s: float = 1.2):
    """Return dict of arrays sampled at FPS (real time): t, x (front axle, m, 0 = bump start), z_body_front/rear (m), body_height, pitch (rad),
    wheel_front/rear road height (m), body acceleration (g) at the front axle."""
    v = speed_kmh / 3.6
    wb = car["wheelbase"]
    total = (lead_m + bump["length"] + wb) / v + tail_s
    n = int(total / DT)
    out_n = int(total * FPS) + 1
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
        if i * DT * FPS >= next_i and next_i < out_n:
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
