"""Content gates for the runaway-truck-ramp episode. Narration match, first
three seconds and caption safety are the generic telemetry gates in
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
#: hold ("about 130 m", "over three kilometres on pavement", "a quarter of the
#: truck's weight") and for nothing to be exaggerated. The rolling-resistance
#: values are ASSUMPTIONS (an illustrative published example, not a design
#: standard); the gate checks the film is consistent with them, not that they
#: are right.
LIMITS = {"stop_distance_m": (120.0, 145.0), "stop_time_s": (8.0, 14.0), "peak_decel_g": (0.2, 0.3),
          "paved_stop_distance_m": (3000.0, None), "energy_ratio": (0.98, 1.02)}


def motion_plausibility(summaries: dict) -> dict:
    problems = []
    for key, (low, high) in LIMITS.items():
        value = summaries[key]
        if (low is not None and value < low) or (high is not None and value > high):
            problems.append(f"{key}={value} outside [{low}, {high}]")
    if summaries.get("physically_calibrated") is not False:
        problems.append("physically_calibrated must stay False")
    ratio = summaries["paved_stop_distance_m"] / summaries["stop_distance_m"]
    if not 15.0 <= ratio <= 40.0:
        problems.append(f"paved/gravel stopping-distance ratio {ratio:.1f} outside 15-40x")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "summaries": summaries}
