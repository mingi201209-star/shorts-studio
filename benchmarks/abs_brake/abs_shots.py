"""EP.06 storyboard shots as plain data (no Blender). `rel`: "world" = fixed camera, "car" = offset from the car's reference point.
Split-screen halves are rendered at 1080x960 and stacked later (top = ABS, bottom = locked, same camera, same time)."""
from __future__ import annotations

FRAME = (1080, 1920)
HALF = (1080, 960)

OPEN_CAM = {"rel": "chase", "loc": (3.4, -6.5, 4.2), "target": (-1.0, 7.0, -1.3), "lens": 28.0}    # x/z fixed, follows the car along the road

SHOTS = {
    "s01-top-abs": {"variant": "abs", "t": 1.15, "frame": HALF, "cam": OPEN_CAM},
    "s01-bottom-locked": {"variant": "locked", "t": 1.15, "frame": HALF, "cam": OPEN_CAM},
    "s01b-top-abs": {"variant": "abs", "t": 1.75, "frame": HALF, "cam": OPEN_CAM},
    "s01b-bottom-locked": {"variant": "locked", "t": 1.75, "frame": HALF, "cam": OPEN_CAM},
    "s02-locked-wheel": {"variant": "locked", "t": 0.9, "cam": {"rel": "car", "loc": (-3.2, 1.6, 0.45), "target": (-0.7, 1.0, 0.35), "lens": 30.0}},
    "s04-tone-ring": {"variant": "abs", "t": 0.62, "macro": True, "cam": {"rel": "car", "loc": (-1.75, 0.70, 0.30), "target": (-0.78, 1.09, 0.25), "lens": 30.0}},
    "s05-caliper": {"variant": "abs", "t": 0.66, "macro": True, "cam": {"rel": "car", "loc": (-1.30, 0.80, 0.70), "target": (-0.77, 1.00, 0.40), "lens": 40.0}},
}
