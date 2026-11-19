"""EP.07 storyboard shots (plain data). `rel`: "car" = offset in the car's own frame (turns with the car), "chase" = fixed x/z, follows the
car along the road, "world" = fixed. Split halves are 1080x960 (top = ESC, bottom = no ESC, same camera and time)."""
from __future__ import annotations

FRAME = (1080, 1920)
HALF = (1080, 960)

OPEN_CAM = {"rel": "follow", "loc": (4.5, -7.5, 6.5), "target": (-0.5, 4.0, -1.8), "lens": 28.0}

SHOTS = {
    "s01-top-esc": {"variant": "esc", "t": 2.0, "frame": HALF, "cam": OPEN_CAM},
    "s01-bottom-off": {"variant": "off", "t": 2.0, "frame": HALF, "cam": OPEN_CAM},
    "s01b-top-esc": {"variant": "esc", "t": 2.8, "frame": HALF, "cam": OPEN_CAM},
    "s01b-bottom-off": {"variant": "off", "t": 2.8, "frame": HALF, "cam": OPEN_CAM},
    "s02-rear-slides": {"variant": "off", "t": 2.2, "cam": {"rel": "car", "loc": (-2.6, -3.8, 0.9), "target": (-0.5, -1.0, 0.3), "lens": 28.0}},
    "s04-yaw-sensor": {"variant": "esc", "t": 1.0, "xray": True, "cam": {"rel": "car", "loc": (0.95, -0.25, 0.80), "target": (0.0, 0.05, 0.40), "lens": 120.0}},
    "s05-steering-sensor": {"variant": "esc", "t": 0.8, "xray": True, "cam": {"rel": "car", "loc": (-1.35, 0.20, 1.20), "target": (-0.36, 0.68, 0.82), "lens": 95.0}},
    "s06-hydraulic-unit": {"variant": "esc", "t": 1.0, "xray": True, "cam": {"rel": "car", "loc": (-1.20, 2.55, 1.55), "target": (-0.40, 1.45, 0.62), "lens": 50.0}},
    "s07-outer-brake": {"variant": "esc", "t": 1.0, "xray": True, "macro": True, "cam": {"rel": "car", "loc": (1.28, 0.82, 0.40), "target": (0.80, 1.09, 0.28), "lens": 38.0}},
}
