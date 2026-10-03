import math

import numpy as np

from shorts_studio import hydroplaning3d as hp


def test_camera_is_fixed_across_the_whole_sequence():
    expected = hp.camera_for(0.0)
    for g in (0.0, 0.1, 0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0):
        assert hp.camera_for(g) == expected


def _samples(n=41):
    return [i / (n - 1) for i in range(n)]


def test_rotation_angle_is_continuous_and_always_increasing():
    gs = _samples()
    angles = [hp.rotation_angle_at(g) for g in gs]
    assert angles[0] == 0.0
    for a, b in zip(angles, angles[1:]):
        assert b > a


def test_wedge_size_monotonically_non_decreasing_and_starts_at_zero():
    gs = _samples()
    vals = [hp.wedge_size_at(g) for g in gs]
    assert vals[0] == 0.0
    assert vals[-1] > 0.9
    for a, b in zip(vals, vals[1:]):
        assert b >= a - 1e-9


def test_contact_width_monotonically_non_increasing_and_disappears():
    gs = _samples()
    vals = [hp.contact_width_at(g) for g in gs]
    assert vals[0] == 1.0
    assert vals[-1] < 0.05
    for a, b in zip(vals, vals[1:]):
        assert b <= a + 1e-9


def test_lift_monotonically_non_decreasing_and_reaches_full_float():
    gs = _samples()
    vals = [hp.lift_at(g) for g in gs]
    assert vals[0] == 0.0
    assert vals[-1] == hp._MAX_LIFT
    for a, b in zip(vals, vals[1:]):
        assert b >= a - 1e-9


def test_groove_outflow_present_during_normal_drainage_then_fades():
    # During the normal drainage phase (low g) there must be real groove
    # outflow -- the task's explicit "정상 배수 단계에서는 groove outflow가
    # 존재" requirement -- and it must fade to ~0 once hydroplaning is
    # complete, since there is no more groove-to-road contact left to drain.
    assert hp.groove_outflow_at(0.05) > 0.2
    assert hp.groove_outflow_at(0.10) > 0.2
    assert hp.groove_outflow_at(1.0) < 0.02


def test_road_contact_is_clearly_reduced_at_the_end_versus_the_start():
    assert hp.contact_width_at(0.0) - hp.contact_width_at(1.0) > 0.9
    assert hp.lift_at(1.0) - hp.lift_at(0.0) > 1.0


def test_no_state_function_jumps_or_reverses_across_fine_sampling():
    # A coarse abnormal jump (e.g. a sign error or an off-by-one in an easing
    # window) would show up as a large single-step delta relative to the
    # function's own total range. Guard against that directly.
    gs = _samples(201)
    for fn, max_total_range in (
        (hp.wedge_size_at, 1.0),
        (hp.contact_width_at, 1.0),
        (hp.lift_at, hp._MAX_LIFT),
        (hp.groove_outflow_at, 1.0),
    ):
        vals = [fn(g) for g in gs]
        deltas = [abs(b - a) for a, b in zip(vals, vals[1:])]
        assert max(deltas) < 0.15 * max_total_range


def test_rendered_frame_has_the_shorts_visual_beat_contract_size():
    frame = hp.render_hydroplaning_frame(0.5)
    assert frame.size == (hp.W, hp.H)
    assert frame.mode == "RGB"


def test_rendered_frames_differ_as_state_evolves():
    early = np.asarray(hp.render_hydroplaning_frame(0.02).convert("RGB"), dtype=int)
    late = np.asarray(hp.render_hydroplaning_frame(0.98).convert("RGB"), dtype=int)
    assert np.abs(early - late).mean() > 5.0


def test_tire_mesh_is_a_single_combined_mesh_for_correct_self_occlusion():
    verts, faces, colors = hp._tire_mesh(hp._HUB_CENTER, rotation=0.3)
    assert len(faces) == len(colors)
    assert verts.shape[1] == 3
    # every face index must reference a real vertex
    n = verts.shape[0]
    for face in faces:
        assert all(0 <= i < n for i in face)
