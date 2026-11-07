"""Motion recipes require an explicit scene target and a visible event interval."""
import math
import pytest
from shorts_studio.factory.motion_recipes import SUPPORTED, evaluate_motion, validate_motion_bindings


@pytest.mark.parametrize("kind", SUPPORTED)
def test_motion_is_inactive_outside_event(kind):
    recipe = dict(kind=kind, object_id="scene/part", start_frame=60, end_frame=120,
                  frequency_hz=3, amplitude=0.01)
    before = evaluate_motion(recipe, frame=59)
    after = evaluate_motion(recipe, frame=121)
    assert all(value == 0 for key, value in before.items() if key != "object_id")
    assert all(value == 0 for key, value in after.items() if key != "object_id")
    inside = evaluate_motion(recipe, frame=72)
    assert any(value != 0 for key, value in inside.items() if key != "object_id")
    assert all(math.isfinite(v) for k, v in inside.items() if k != "object_id")


@pytest.mark.parametrize("kind", SUPPORTED)
def test_unknown_scene_target_is_rejected(kind):
    recipe = dict(kind=kind, object_id="missing", start_frame=1, end_frame=90,
                  frequency_hz=2, amplitude=0.01)
    with pytest.raises(ValueError):
        validate_motion_bindings(recipe, {"known"})


@pytest.mark.parametrize("change", [
    {"kind": "unknown"}, {"object_id": ""}, {"amplitude": 1},
    {"frequency_hz": 20}, {"frequency_hz": float("nan")},
    {"start_frame": 0}, {"end_frame": 0}, {"extra": True},
])
def test_bad_recipes_fail_closed(change):
    recipe = dict(kind="vehicle_suspension", object_id="car",
                  start_frame=1, end_frame=90, frequency_hz=2, amplitude=0.01)
    recipe.update(change)
    with pytest.raises(ValueError):
        evaluate_motion(recipe, frame=20)
