import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import runaway_ramp_motion as m


def test_gravel_stops_the_truck_within_the_clip():
    s = m.simulate()
    assert s[-1]["v"] == 0.0
    assert m.stop_time(s) < 25.0


def test_stop_distance_close_to_constant_decel_estimate():
    s = m.simulate()
    ideal = m.SPEED0 ** 2 / (2 * m.GRAVEL_C * m.G)
    # sink-in ramp lengthens it a little but not by more than ~10 m
    assert ideal < s[-1]["x"] < ideal + 10.0


def test_paved_road_takes_far_longer_than_gravel():
    assert m.stop_distance(m.PAVED_C) > 10 * m.stop_distance(m.GRAVEL_C)


def test_speed_never_increases_and_distance_never_decreases():
    s = m.simulate()
    for a, b in zip(s, s[1:]):
        assert b["v"] <= a["v"] + 1e-12 and b["x"] >= a["x"] - 1e-12


def test_energy_audit_balances():
    assert abs(m.audit_energy(m.simulate())["ratio"] - 1.0) < 0.02


def test_never_claims_calibration():
    assert m.summary(m.simulate())["physically_calibrated"] is False
