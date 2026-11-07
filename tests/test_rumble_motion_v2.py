"""Opt-in Blender motion must never change default 30-second rendering."""
import math
import pytest
from shorts_studio.factory.rumble_motion_v2 import vehicle_motion


class StubTimeline:
    @staticmethod
    def lane_return_offset(frame):
        return 0.36 if frame < 90 else 0.0

    @staticmethod
    def travel_x(frame):
        return frame / 30


def test_no_vibration_before_contact():
    assert all(value == 0 for value in vehicle_motion(1, StubTimeline).values())


def test_actual_motion_after_contact():
    values = [vehicle_motion(i, StubTimeline) for i in range(90, 110)]
    assert any(abs(v["wheel_heave"]) > 0.001 for v in values)
    assert any(abs(v["body_heave"]) > 0.004 for v in values)
    assert any(abs(v["body_roll"]) > 0.003 for v in values)
    assert any(abs(v["body_pitch"]) > 0.002 for v in values)
    assert all(all(math.isfinite(x) for x in v.values()) for v in values)


@pytest.mark.parametrize("frame", [0, -1, 901, 1.5, True])
def test_out_of_range_frames_fail(frame):
    with pytest.raises(ValueError):
        vehicle_motion(frame, StubTimeline)
