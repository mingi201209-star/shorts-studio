"""Deterministic visual suspension motion for a newly rendered rumble-strip pilot.

This is explanatory animation, not a calibrated dynamics simulation.
Never apply to legacy renders or accept as a human-visible PASS without review.
"""
import math


def vehicle_motion(frame, timeline):
    if type(frame) is not int or not 1 <= frame <= 900:
        raise ValueError("frame outside approved 30s timeline")
    offset = timeline.lane_return_offset(frame)
    overlap = max(0.0, min(1.0, (0.30 - offset) / 0.20))
    x = timeline.travel_x(frame)
    phase = x / 0.34 * math.tau
    # Wheels follow the grooves. Sprung mass lags with reduced amplitude.
    wheel_heave = 0.0025 * overlap * math.sin(phase)
    body_heave = 0.009 * overlap * math.sin(phase - 0.75)
    body_roll = 0.006 * overlap * math.sin(phase - 1.1)
    body_pitch = 0.004 * overlap * math.sin(phase - 0.45)
    return dict(wheel_heave=wheel_heave, body_heave=body_heave,
                body_roll=body_roll, body_pitch=body_pitch)
