"""Regression tests for opt-in frame counting; existing 30s output stays unchanged."""
import math
import pytest
from shorts_studio.factory.rumble_duration import expected_frame_count, progressive_cuts


def test_legacy_and_extended_frames():
    assert expected_frame_count(30) == 900
    assert expected_frame_count(48) == 1440
    assert expected_frame_count(48, 60) == 2880


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf"), True, 1.01])
def test_invalid_durations_fail_closed(seconds):
    with pytest.raises(ValueError):
        expected_frame_count(seconds)


def test_progressive_legacy_coverage_unchanged():
    ends = [50, 135, 310, 460, 606, 719, 767, 900]
    roles = ["hook_warning", "shoulder_location", "road_cut", "tire_contact",
             "rumble_mechanism", "rumble_mechanism", "rumble_mechanism", "driver_response"]
    assert len(progressive_cuts(ends, roles)) == 8
    with pytest.raises(ValueError):
        progressive_cuts(ends[:-1] + [1440], roles)


def test_extended_coverage_is_explicit():
    roles = ["tire_contact", "driver_response"]
    assert progressive_cuts([720, 1440], roles, total_frames=1440)[-1][0] == 1440
    with pytest.raises(ValueError):
        progressive_cuts([720, 1439], roles, total_frames=1440)


@pytest.mark.parametrize("ends,roles,total", [
    ([], [], 900),
    ([900], ["tire_contact"], 0),
    ([900], ["tire_contact"], True),
    ([29, 900], ["tire_contact", "driver_response"], 900),
    ([500, 529, 900], ["tire_contact", "driver_response", "road_cut"], 900),
    ([500, 900], ["tire_contact"], 900),
])
def test_malformed_cut_coverage_fails_closed(ends, roles, total):
    with pytest.raises(ValueError):
        progressive_cuts(ends, roles, total_frames=total)
