"""Episode 2 mechanism-first detail shot contracts (real timeline, no Blender mock)."""

import math

import pytest

from shorts_studio.factory.rumble_episode2 import camera_layout, detail_stage, load_episode, travel_x

from pathlib import Path

EPISODE = Path(__file__).resolve().parents[1] / "examples/factory/rumble-episode2-30s.json"
TREATMENTS = {
    "hook_warning": "macro_warning",
    "road_cut": "road_section",
    "tire_contact": "rolling_contact",
    "rumble_mechanism": "wheel_body_vibration",
    "shoulder_location": "shoulder_context",
    "driver_response": "human_response",
}


def test_episode2_detail_treatment_is_exhaustive_and_ordered():
    shots = load_episode(EPISODE)["shots"]
    assert list(TREATMENTS) == [shot["id"] for shot in shots]
    assert [detail_stage(shot["id"]) for shot in shots] == list(TREATMENTS.values())
    with pytest.raises(ValueError, match="unknown"):
        detail_stage("generic-car-drive")


def _up_and_right(offset):
    length = math.sqrt(sum(coord * coord for coord in offset))
    view = tuple(-coord / length for coord in offset)
    flat = math.hypot(view[0], view[1])
    right = (view[1] / flat, -view[0] / flat, 0)
    up = (
        right[1] * view[2] - right[2] * view[1],
        right[2] * view[0] - right[0] * view[2],
        right[0] * view[1] - right[1] * view[0],
    )
    return right, up


def test_hook_macro_camera_keeps_tyre_inside_ninety_percent_safe_width():
    """Tread remains in the central 90%, at both ends of the *actual* 5s shot."""
    shot = load_episode(EPISODE)["shots"][0]
    camera = camera_layout(shot)
    assert camera["target"] == "wheel"
    assert camera["anchor_frame"] == 75
    right, _ = _up_and_right(camera["offset"])
    usable_half_width = .9 * camera["scale"] * (9 / 16) / 2
    for frame in (1, 75, 150):
        displacement = travel_x(frame) - travel_x(camera["anchor_frame"])
        horizontal = abs(displacement * right[0])
        assert horizontal + .30 <= usable_half_width, (frame, horizontal, usable_half_width)


def test_hook_macro_camera_keeps_bottom_plane_25cm_above_road():
    """Frustum floor should not cut through road on the macro opening shot."""
    shot = load_episode(EPISODE)["shots"][0]
    camera = camera_layout(shot)
    _, up = _up_and_right(camera["offset"])
    # Measured CC0 near-side Front_tire center z = 0.28m after scale/yaw.
    camera_z = .28 + camera["target_z"] + camera["offset"][2]
    floor_z = camera_z - camera["scale"] / 2 * up[2]
    assert floor_z >= .25, floor_z


def test_macro_treatment_does_not_change_six_shot_contract():
    shots = load_episode(EPISODE)["shots"]
    assert [(s["start"], s["end"]) for s in shots] == [
        (1, 150), (151, 300), (301, 450),
        (451, 600), (601, 750), (751, 900),
    ]
