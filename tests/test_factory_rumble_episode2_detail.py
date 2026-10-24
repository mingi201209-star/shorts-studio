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


def test_recess_profile_matches_original_sixteen_mm_road_mesh():
    """The road cutaway and moving tyre must reference the actual asphalt profile."""
    from shorts_studio.factory.rumble_episode2 import groove_height

    assert groove_height(0.0) == pytest.approx(-0.016)
    assert groove_height(0.34) == pytest.approx(-0.016)
    assert groove_height(-0.34) == pytest.approx(-0.016)
    assert groove_height(0.1) == pytest.approx(-0.008, abs=1e-9)
    assert groove_height(-0.1) == pytest.approx(-0.008, abs=1e-9)
    for position in (0.115, 0.17, 0.225):
        assert groove_height(position) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        groove_height(float("nan"))


def test_cutaway_profile_exposes_real_substrate_not_free_floating_grooves():
    from shorts_studio.factory.rumble_episode2 import road_section_profile

    profile = road_section_profile()
    assert len(profile) > 200  # covers the actual 26 m milled run
    xs = [x for x, top, bottom in profile]
    assert xs == sorted(xs)
    assert xs[0] == pytest.approx(-13.0)
    assert xs[-1] == pytest.approx(13.0)
    assert any(abs(x) < 1e-9 and abs(z + .016) < 1e-9
               for x, z, lower in profile)
    assert all(bottom == pytest.approx(-.08) for x, top, bottom in profile)
    assert all(bottom < top <= 0.0 for x, top, bottom in profile)
    assert all(top == pytest.approx(
        __import__("shorts_studio.factory.rumble_episode2", fromlist=["groove_height"]).groove_height(x))
        for x, top, bottom in profile)


def test_road_cut_and_contact_camera_are_tighter_with_full_tyre_safety():
    from shorts_studio.factory.rumble_episode2 import camera_layout

    shots = {s["id"]: s for s in load_episode(EPISODE)["shots"]}
    cut = camera_layout(shots["road_cut"])
    contact = camera_layout(shots["tire_contact"])
    assert 3.97 <= cut["scale"] <= 4.10
    assert 3.45 <= contact["scale"] <= 3.65
    assert cut["target"] == contact["target"] == "wheel"
    assert cut["anchor_frame"] == 225 and contact["anchor_frame"] == 375
    for shot, view in ((shots["road_cut"], cut), (shots["tire_contact"], contact)):
        right, up = _up_and_right(view["offset"])
        half_width = .9 * view["scale"] * 9 / 32
        half_height = .9 * view["scale"] / 2
        for frame in (shot["start"], view["anchor_frame"], shot["end"]):
            dx = travel_x(frame) - travel_x(view["anchor_frame"])
            assert abs(dx * right[0]) + .30 < half_width, (shot["id"], frame)
            assert abs(dx * up[0]) + .30 < half_height, (shot["id"], frame)
        camera_z = .28 + view["target_z"] + view["offset"][2]
        assert camera_z - view["scale"] / 2 * up[2] >= .25


def test_native_renderer_uses_shared_geometry_for_section_and_tyre_contact():
    """Structural contract only; native Cycles32 screenshot still required."""
    renderer = (EPISODE.parents[2]
                / "benchmarks/road_safety/render_rumble_episode2.py").read_text()
    assert "module.groove_height(" in renderer
    assert "module.road_section_profile(" in renderer
    assert 'section_wall.hide_render = not visibility["section_face_visible"]' in renderer
    assert 'module.detail_stage(shot["id"]) == "rolling_contact"' in renderer

def test_mechanism_isolates_genuine_wheel_and_road_only_in_detail_beats():
    """Meaningful component close-ups, not a full car hiding the contact area."""
    from shorts_studio.factory.rumble_episode2 import detail_visibility
    cases = {
        "hook_warning": (True, True, False, False),
        "road_cut": (False, False, True, True),
        "tire_contact": (False, True, False, False),
        "rumble_mechanism": (True, True, False, False),
        "shoulder_location": (True, True, False, False),
        "driver_response": (True, True, False, False),
    }
    for shot, expected in cases.items():
        visible = detail_visibility(shot)
        assert (
            visible["body_visible"],
            visible["near_shoulder_visible"],
            visible["exposed_bank_visible"],
            visible["section_face_visible"],
        ) == expected
    with pytest.raises(ValueError, match="unknown"):
        detail_visibility("not-a-shot")


def test_native_renderer_reveals_actual_wheel_components_not_fake_cutouts():
    code = (EPISODE.parents[2]
            / "benchmarks/road_safety/render_rumble_episode2.py").read_text()
    assert 'wheel_explainer_meshes = set(groups["Front_tire"])' in code
    assert "ob.hide_render = not visibility[\"body_visible\"]" in code
    assert 'near_shoulder.hide_render = not visibility["near_shoulder_visible"]' in code
    assert 'exposed_bank.hide_render = not visibility["exposed_bank_visible"]' in code
    assert 'section_wall.hide_render = not visibility["section_face_visible"]' in code
    assert "if j == 0:" in code and "near_faces.append(face)" in code
    assert "car.location=(x,-.30+module.lane_return_offset(absolute_frame),bounce)" in code
