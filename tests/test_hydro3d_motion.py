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


def test_hydro_secondary_motion_never_freezes_after_state_settles():
    for kind in hydro3d.KINDS:
        before = _frame(kind, 1.0, 2.0)
        after = _frame(kind, 1.0, 2.5)
        assert _mad(before, after) > 12.5, kind


def test_hydro_story_states_are_visually_distinct():
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
        assert _mad(left, right) > 0.45, (left_kind, right_kind)


def test_hydro_causal_transitions_change_physical_state():
    for kind in ("water_wedge", "contact_shrink", "speed_ramp", "pressure_lift", "recover_contact"):
        start = _frame(kind, 0.0, 0.1)
        settled = _frame(kind, 1.0, 1.5)
        assert _mad(start, settled) > 0.75, kind


def test_full_hydroplane_is_not_normal_wet_contact():
    contact = _frame("hero_contact", 1.0, 1.5)
    hydro = _frame("full_hydroplane", 1.0, 1.5)
    assert _mad(contact, hydro) > 1.5
