"""Content gates for the sand-barrel crash cushion episode. Narration match,
first three seconds and caption safety are the generic telemetry gates in
jersey_barrier_gates.py (unchanged); only the motion-plausibility limits are
specific to this topic. Pure functions, unit-tested."""
from __future__ import annotations

from benchmarks.road_safety.jersey_barrier_gates import (  # noqa: F401  (re-exported)
    caption_safety,
    first_three_seconds,
    narration_screen_match,
    spoken_windows,
)

#: Bounds the simulated motion has to stay inside for the film's claims to
#: hold and for nothing to be exaggerated.
MOTION_LIMITS = {
    "array": {"stop_distance_m": (5.5, 7.0), "peak_decel_g": (4.0, 15.0), "peak_pitch_deg": (0.5, 5.0),
              "speed_at_wall_line_mps": (18.0, None), "total_sand_kg": (3000.0, 8000.0)},
    "wall": {"stop_distance_m": (0.6, 1.2), "peak_decel_g": (15.0, 60.0)},
}


def motion_plausibility(summaries: dict) -> dict:
    problems = []
    for case, limits in MOTION_LIMITS.items():
        for key, (low, high) in limits.items():
            value = summaries[case][key]
            if (low is not None and value < low) or (high is not None and value > high):
                problems.append(f"{case}.{key}={value} outside [{low}, {high}]")
    a, w = summaries["array"], summaries["wall"]
    # "slowed lightly at first and harder deeper in": the first third of the
    # stop is gentler than the middle third and the peak is not at the front.
    if not a["mean_decel_first_third_g"] < a["mean_decel_middle_third_g"]:
        problems.append("array: the first third of the stop is not gentler than the middle third")
    if a["peak_decel_at_m"] < 0.3 * a["stop_distance_m"]:
        problems.append("array: peak deceleration is at the very front, not deeper in")
    # "about one meter" against "about six": a real, large difference.
    if not 4.0 <= a["stop_distance_m"] / w["stop_distance_m"] <= 9.0:
        problems.append("array/wall stopping-distance ratio is outside 4-9x")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "summaries": summaries}
