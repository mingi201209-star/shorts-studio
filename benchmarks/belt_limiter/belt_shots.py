"""EP.05 shots as plain data (no Blender): which belt, when in the crash, which camera. A shot is a still of the film: the full film later maps every film frame to a shot-like state.
Camera positions are in the CAR frame for interior shots (the cabin set is parented to the car) and relative to the car's nose for exterior shots. `at` is the fraction of the frame
height, from the top, where the look-at point lands (the subject sits above the captions)."""
from __future__ import annotations

from benchmarks.belt_limiter import belt_motion as bm

SENSOR_W = 36.0
FRAME = (1080, 1920)

I_FACE = ((0.50, 0.62, 1.10), (-0.36, 0.18, 0.85))      # EP.04: from the front passenger seat looking back at the driver, the chest with the belt and the wheel
I_CHEST = ((0.62, 0.50, 0.95), (-0.34, 0.12, 0.70))      # closer and lower: the belt across the chest
REEL = ((-0.12, -0.28, 0.40), (-0.72, -0.30, 0.38))     # looks at the reel at the base of the driver's B pillar (the seat back is hidden in this shot)

SHOTS = {
    "sb1-run-up": {"line": 1, "text": "Your seatbelt is built to give way on purpose.", "variant": "modern", "dt": -0.40, "interior": False, "xray": 0.0, "cabin_xray": 0.0,
                   "cam": {"rel": "nose", "loc": (-4.4, -3.4, 1.5), "target": (0.0, -2.0, 0.6), "lens": 36.0, "at": 0.42}},
    "sb2-belt-hook": {"line": 1, "text": "Your seatbelt is built to give way on purpose.", "variant": "modern", "dt": -0.03, "interior": True, "xray": 0.0, "cabin_xray": 0.0,
                      "cam": {"rel": "car", "loc": I_CHEST[0], "target": I_CHEST[1], "lens": 26.0, "at": 0.42}},
    "sb3-snaps-tight": {"line": 2, "text": "In a crash it first snaps tight, pulling you back into the seat.", "variant": "modern", "dt": 0.009, "interior": True, "xray": 0.0, "cabin_xray": 0.0,
                        "cam": {"rel": "car", "loc": I_CHEST[0], "target": I_CHEST[1], "lens": 26.0, "at": 0.42}},
    "sb4-reel": {"line": 4, "text": "Then a twisting metal bar in the reel starts to give, letting out a little belt.", "variant": "modern", "dt": 0.050, "interior": True, "xray": 0.0, "cabin_xray": 0.0,
                 "hide_seat": True, "cam": {"rel": "car", "loc": REEL[0], "target": REEL[1], "lens": 55.0, "at": 0.45}},
    "sb5-gentle-stop": {"line": 6, "text": "Your chest gets a longer, gentler stop.", "variant": "modern", "dt": 0.060, "interior": True, "xray": 0.0, "cabin_xray": 0.0,
                        "cam": {"rel": "car", "loc": I_FACE[0], "target": I_FACE[1], "lens": 30.0, "at": 0.42}},
    "sb6-plain-belt": {"line": 7, "text": "A belt with no give stops it almost at once, with a harder push.", "variant": "plain", "dt": 0.060, "interior": True, "xray": 0.0, "cabin_xray": 0.0,
                       "cam": {"rel": "car", "loc": I_FACE[0], "target": I_FACE[1], "lens": 30.0, "at": 0.42}},
    "sb7-both-give": {"line": 8, "text": "Same idea as a crumple zone: a longer stop means a smaller peak force.", "variant": "modern", "dt": 0.110, "interior": False, "xray": 1.0, "cabin_xray": 1.0,
                      "cam": {"rel": "nose", "loc": (-3.4, -1.7, 1.0), "target": (0.0, -1.3, 0.72), "lens": 30.0, "at": 0.45}},
}


def sim_time(shot: dict) -> float:
    return bm.contact_time_s() + shot["dt"]


def shift_y(cam: dict) -> float:
    return (cam["at"] - 0.5) * (FRAME[1] / FRAME[0])
