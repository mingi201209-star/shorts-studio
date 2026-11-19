"""EP.08 storyboard shots (plain data). dt = simulated seconds after first contact with the wall. Cameras are in the car frame (they move
with the car). "interior": the cabin set is drawn and the body hidden; "xray": the body is a see-through shell (exterior shots)."""
from __future__ import annotations

HALF = (1080, 960)
SIDE_XRAY = {"loc": (-2.05, 0.40, 1.12), "target": (-0.35, 0.68, 0.86), "lens": 24.0}
FACE = {"loc": (0.50, 0.62, 1.10), "target": (-0.36, 0.30, 0.95), "lens": 28.0}
HUB = {"loc": (0.10, 0.48, 1.28), "target": (-0.36, 0.72, 0.88), "lens": 45.0}
HUB_SIDE = {"loc": (0.25, 0.70, 1.00), "target": (-0.36, 0.72, 0.88), "lens": 50.0}
ACU = {"loc": (0.95, 0.10, 0.62), "target": (0.0, 0.30, 0.33), "lens": 110.0}

SHOTS = {
    "s01-top-on": {"variant": "on", "dt": 0.035, "frame": HALF, "xray": True, "cam": SIDE_XRAY},
    "s01-bottom-off": {"variant": "off", "dt": 0.035, "frame": HALF, "xray": True, "cam": SIDE_XRAY},
    "s01b-top-on": {"variant": "on", "dt": 0.068, "frame": HALF, "xray": True, "cam": SIDE_XRAY},
    "s01b-bottom-off": {"variant": "off", "dt": 0.068, "frame": HALF, "xray": True, "cam": SIDE_XRAY},
    "s02-face-off": {"variant": "off", "dt": 0.066, "interior": True, "cam": FACE},
    "s03-hub-folded": {"variant": "on", "dt": 0.005, "interior": True, "cam": HUB},
    "s04-flaps-open": {"variant": "on", "dt": 0.018, "interior": True, "cam": HUB_SIDE},
    "s05-acu": {"variant": "on", "dt": 0.013, "xray": True, "sensor": True, "cam": ACU},
    "s06-head-in-bag": {"variant": "on", "dt": 0.060, "interior": True, "cam": FACE},
}
