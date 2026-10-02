import numpy as np

from shorts_studio import hydro3d


def _frame(kind: str, progress: float, seconds: float) -> np.ndarray:
    image = hydro3d.render_hydro_frame(
        kind,
        progress,
        time_seconds=seconds,
    ).convert("RGB")
    return np.asarray(image, dtype=np.int16)


def _mad(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).mean())


def test_hydro_camera_is_fixed_and_topic_specific():
    camera = hydro3d.OPTIMAL_HYDRO_CAMERA
    assert -0.30 < camera.yaw < -0.10
    assert -0.34 < camera.pitch < -0.14
    assert camera.cx < 490
    for kind in hydro3d.KINDS:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            assert hydro3d.camera_for(kind, t) == camera


def test_hydro_frames_are_nonblank():
    for kind in hydro3d.KINDS:
        arr = _frame(kind, 1.0, 1.4)
        assert float(arr.mean()) > 8.0, kind
        assert float(arr.std()) > 10.0, kind


def test_hydro_secondary_motion_never_freezes():
    # Road scroll, tire rotation, and coherent water motion must remain alive
    # after the causal transition has already settled.
    for kind in hydro3d.KINDS:
        before = _frame(kind, 1.0, 2.0)
        after = _frame(kind, 1.0, 2.5)
        assert _mad(before, after) > 3.0, kind


def test_hydro_causal_transitions_change_the_physical_state():
    for kind in (
        "water_wedge",
        "contact_shrink",
        "speed_ramp",
        "pressure_lift",
        "recover_contact",
    ):
        start = _frame(kind, 0.0, 0.1)
        settled = _frame(kind, 1.0, 1.6)
        assert _mad(start, settled) > 1.25, kind


def test_consecutive_hydro_states_add_new_visual_information():
    sequence = (
        "hero_contact",
        "water_wedge",
        "contact_shrink",
        "full_hydroplane",
        "drainage_channels",
        "speed_ramp",
        "pressure_lift",
        "wedge_closeup",
        "steering_loss",
        "braking_loss",
        "recover_contact",
        "final_drive",
        "final_cutaway",
    )
    frames = [_frame(kind, 1.0, 1.5) for kind in sequence]
    for left_kind, right_kind, left, right in zip(
        sequence,
        sequence[1:],
        frames,
        frames[1:],
    ):
        assert _mad(left, right) > 0.55, (left_kind, right_kind)
