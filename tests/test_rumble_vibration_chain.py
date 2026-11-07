"""Regression tests for the storyboard's real wheel-to-body vibration chain."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "rumble_episode2_isolated",
    Path(__file__).resolve().parents[1] / "shorts_studio/factory/rumble_episode2.py",
)
episode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(episode)


def test_phase_delayed_suspension_has_nonidentical_wheel_and_body_motion():
    values = [episode.vibration_chain(frame) for frame in range(1, 901)]
    assert len(values) == 900
    assert any(abs(v["relative_suspension_z_m"]) > 0.001 for v in values)
    assert all(abs(v["body_z_m"]) <= 0.00321 for v in values)
    assert all(abs(v["wheel_z_m"]) <= 0.00801 for v in values)
    assert all(abs(v["wheel_z_m"] - v["body_z_m"] -
                   v["relative_suspension_z_m"]) < 1e-12 for v in values)


def test_absolute_frame_motion_is_stable_across_shards():
    assert episode.vibration_chain(451) == episode.vibration_chain(451)
    assert episode.vibration_chain(451) != episode.vibration_chain(452)
    assert episode.vibration_chain(900) == episode.vibration_chain(900)
