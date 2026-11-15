"""EP.03 preview gates (objective checks on rendered preview frames) + the first-3-seconds curiosity checklist.

Objective (pixels): both cars and both bump shapes visible in the first frame; subjects fill enough of the picture; the bump shapes differ visibly;
body motion between the calmest and the most displaced frame is large enough to see. Editorial items (question on screen in the first second, a visible
difference event within 3 s) are listed as REQUIRED and stay UNVERIFIED until a person confirms them on the real video: no PASS without evidence.
"""
from __future__ import annotations

import numpy as np

MIN_CAR_HEIGHT_FRACTION = 0.22      # a car's bounding box height / panel height (first frame)
MIN_BODY_MOTION_PX_FRACTION = 0.012  # vertical motion of the car's top edge / panel height across the shot
MIN_BUMP_LENGTH_RATIO_ON_SCREEN = 2.0


def masks(rgb: np.ndarray):
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    car = (b > r + 60) & (b > g + 25) & (b > 110) & (r < 75)
    bump = (r > 150) & (g > 110) & (b < 110) & (r > b + 80)
    return car, bump


def bbox(mask: np.ndarray):
    ys, xs = np.nonzero(mask)
    if len(xs) < 20:
        return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def panel_report(first: np.ndarray, others: list[np.ndarray]) -> dict:
    car, bump = masks(first)
    h, w = car.shape
    cb, bb = bbox(car), bbox(bump)
    top_edges = [bbox(masks(o)[0])[1] for o in others if bbox(masks(o)[0])]
    motion = (max(top_edges + [cb[1]]) - min(top_edges + [cb[1]])) / h if cb else 0.0
    return {
        "car_visible": cb is not None,
        "bump_visible": bb is not None,
        "car_height_fraction": 0.0 if cb is None else (cb[3] - cb[1] + 1) / h,
        "bump_width_px": 0 if bb is None else int(bb[2] - bb[0] + 1),
        "body_motion_fraction": motion,
    }


def evaluate(first_panels: dict[str, np.ndarray], series: dict[str, list[np.ndarray]]) -> dict:
    rep = {k: panel_report(first_panels[k], series[k]) for k in first_panels}
    checks = {
        "both_cars_visible_first_frame": all(r["car_visible"] for r in rep.values()),
        "both_bumps_visible_first_frame": all(r["bump_visible"] for r in rep.values()),
        "cars_fill_picture": all(r["car_height_fraction"] >= MIN_CAR_HEIGHT_FRACTION for r in rep.values()),
        "body_motion_visible": all(r["body_motion_fraction"] >= MIN_BODY_MOTION_PX_FRACTION for r in rep.values()),
    }
    widths = sorted(r["bump_width_px"] for r in rep.values() if r["bump_width_px"])
    checks["bump_shapes_differ_on_screen"] = len(widths) == 2 and widths[1] / max(1, widths[0]) >= MIN_BUMP_LENGTH_RATIO_ON_SCREEN
    return {"panels": rep, "checks": checks, "objective_pass": all(checks.values())}


#: first three seconds: required for every episode; item status is UNVERIFIED until evidence from the real video exists
FIRST_THREE_SECONDS = {
    "objective_both_subjects_in_first_frame": "pixel check above",
    "question_text_on_screen_within_1s": "UNVERIFIED (needs overlay + look at the video)",
    "difference_visible_within_3s": "UNVERIFIED (needs look at the video)",
    "narration_hook_starts_within_0.5s": "UNVERIFIED (needs captured speech timing)",
}
