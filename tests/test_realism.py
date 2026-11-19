import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import realism as r


def test_levels_a_and_b_keep_the_steady_pitch():
    for level in ("A", "B"):
        assert r.suspension(0.5, -0.02, level) == (-0.02, 0.0)


def test_level_c_is_still_before_contact_and_settles_to_the_steady_pitch():
    assert r.suspension(-0.3, -0.02, "C") == (-0.02, 0.0)
    p, h = r.suspension(6.0, -0.02, "C")
    assert abs(p - (-0.02)) < 1e-3 and abs(h) < 1e-3


def test_level_c_overshoots_then_returns():
    ps = [r.suspension(t / 30.0, -0.02, "C")[0] for t in range(1, 90)]
    assert min(ps) < -0.02 * 1.1          # overshoot of a damped system (nose dives deeper first)
    assert abs(ps[-1] - (-0.02)) < 4e-3


def test_step_response_bounds():
    assert r.step_response(0.0) == 0.0
    assert max(r.step_response(t / 100.0) for t in range(0, 300)) < 1.6
