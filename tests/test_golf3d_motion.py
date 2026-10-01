import numpy as np

from shorts_studio import golf3d


def _frame(kind: str, progress: float, seconds: float) -> np.ndarray:
    image = golf3d.render_golf_frame(
        kind,
        progress,
        time_seconds=seconds,
    ).convert("RGB")
    return np.asarray(image, dtype=np.int16)


def _mad(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a - b).mean())


def test_secondary_motion_keeps_running_after_story_state_settles():
    # Once the causal transition is complete, the clip must still feel alive.
    # This catches the old failure mode where a 3-second state finished and
    # the remaining narration looked like a held frame.
    for kind in golf3d.KINDS:
        before = _frame(kind, 1.0, 2.0)
        after = _frame(kind, 1.0, 2.5)
        assert _mad(before, after) > 0.10, kind


def test_consecutive_golf_states_are_not_visual_replays():
    sequence = (
        "hero_dimples",
        "smooth_morph",
        "smooth_wake",
        "boundary_layer",
        "separation_compare",
        "dimple_wake",
        "trip_turbulence",
        "attached_flow",
        "wake_shrink",
        "drag_compare",
        "flight_payoff",
    )
    frames = [_frame(kind, 1.0, 1.5) for kind in sequence]
    for left_kind, right_kind, left, right in zip(
        sequence,
        sequence[1:],
        frames,
        frames[1:],
    ):
        assert _mad(left, right) > 0.45, (left_kind, right_kind)


def test_transition_states_move_toward_their_final_physical_state():
    # One-shot story progress must change the physical result substantially;
    # micro-motion alone must never be the only difference between these
    # causal states.
    for kind in ("smooth_morph", "dimple_wake", "trip_turbulence", "wake_shrink"):
        start = _frame(kind, 0.0, 0.1)
        settled = _frame(kind, 1.0, 1.2)
        assert _mad(start, settled) > 0.65, kind
