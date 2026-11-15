import numpy as np
from benchmarks.speed_bump import speed_bump_gates as g
from benchmarks.speed_bump import speed_bump_motion as m


def test_numbers_agree_with_simulation():
    assert g.narration_numbers(m.pass_summaries())["status"] == "PASS"


def test_numbers_gate_fails_when_claims_do_not_hold():
    peaks = m.pass_summaries()
    peaks["B"]["short"]["peak_body_g"] = 3.0
    assert g.narration_numbers(peaks)["status"] == "FAIL"


def test_first_contact_inside_three_seconds():
    assert g.first_contact_film_seconds() <= 3.0


def test_timing_gate():
    beats = [{"start": s} for s in (0, 5.3, 10.7, 16.0, 21.3, 26.7)]
    assert g.narration_picture_timing({"beats": beats})["status"] == "PASS"
    beats[3]["start"] = 19.5
    assert g.narration_picture_timing({"beats": beats})["status"] == "FAIL"


def test_first_three_seconds_needs_hook_and_motion():
    rng = np.random.default_rng(0)
    a = rng.integers(60, 200, (1920, 1080, 3), dtype=np.uint8)
    b = rng.integers(60, 200, (1920, 1080, 3), dtype=np.uint8)
    a[565:675, 40:1040] = 250
    b[565:675, 40:1040] = 20
    assert g.first_three_seconds({10: a, 90: b, 120: b}, 1.0)["status"] == "PASS"
    assert g.first_three_seconds({10: b, 90: b, 120: b}, 1.0)["status"] == "FAIL"
