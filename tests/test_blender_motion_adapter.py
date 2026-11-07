"""Run cross-topic Blender adapter checks with lightweight object stand-ins."""
import pytest
from shorts_studio.factory.blender_motion_adapter import BlenderMotionDriver

class Obj:
    def __init__(self):
        self.location = [1.0, 2.0, 3.0]
        self.rotation_euler = [0.1, 0.2, 0.3]

@pytest.mark.parametrize("kind,channels", [
    ("vehicle_suspension", ["wheel_z", "body_z", "body_roll"]),
    ("aircraft_wing_flex", ["wing_tip_z"]),
    ("mechanical_rotation", ["angle_rad"]),
    ("structure_sway", ["sway_angle_rad"]),
])
def test_real_object_channels_are_driven_and_reset(kind, channels):
    root = "shot/subject"
    objects = {root: Obj(), **{f"{root}/{channel}": Obj() for channel in channels}}
    recipe = dict(kind=kind, object_id=root, start_frame=10, end_frame=60,
                  frequency_hz=2, amplitude=0.02)
    driver = BlenderMotionDriver(objects, recipe)
    driver.capture_rest()
    baseline = {key: (list(obj.location), list(obj.rotation_euler)) for key, obj in objects.items()}
    driver.apply(16)
    assert any((obj.location, obj.rotation_euler) != baseline[key] for key, obj in objects.items())
    driver.apply(1)
    assert all((obj.location, obj.rotation_euler) == baseline[key] for key, obj in objects.items())


def test_missing_control_rejected_before_any_mutation():
    recipe = dict(kind="aircraft_wing_flex", object_id="wing", start_frame=1,
                  end_frame=30, frequency_hz=2, amplitude=0.01)
    with pytest.raises(ValueError, match="missing explicit Blender motion control"):
        BlenderMotionDriver({"wing": Obj()}, recipe)


def test_capture_rest_is_required():
    recipe = dict(kind="mechanical_rotation", object_id="rotor", start_frame=1,
                  end_frame=30, frequency_hz=2, amplitude=0.01)
    driver = BlenderMotionDriver({"rotor": Obj(), "rotor/angle_rad": Obj()}, recipe)
    with pytest.raises(RuntimeError):
        driver.apply(10)
