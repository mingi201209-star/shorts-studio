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
    beats = [{"start": s} for s in (0, 5.0, 11.3, 16.5, 21.9, 27.4)]
    assert g.narration_picture_timing({"beats": beats})["status"] == "PASS"
    beats[3]["start"] = 19.5
    assert g.narration_picture_timing({"beats": beats})["status"] == "FAIL"


def test_first_three_seconds_needs_both_cars_and_motion():
    rng = np.random.default_rng(0)
    a = rng.integers(60, 200, (1920, 1080, 3), dtype=np.uint8)
    b = rng.integers(60, 200, (1920, 1080, 3), dtype=np.uint8)
    assert g.first_three_seconds({10: a, 90: b}, 1.0)["status"] == "PASS"
    empty = a.copy()
    empty[0:1400, 540:1080] = 90
    assert g.first_three_seconds({10: empty, 90: b}, 1.0)["status"] == "FAIL"
    assert g.first_three_seconds({10: a, 90: a}, 1.0)["status"] == "FAIL"
    assert g.first_three_seconds({10: a, 90: b}, 3.5)["status"] == "FAIL"


def test_assumptions_must_be_spoken():
    ok = {"beats": [{"narration_en": "This is a computer simulation with assumed values."}]}
    bad = {"beats": [{"narration_en": "The short bump is harsher."}]}
    assert g.assumptions_in_narration(ok)["status"] == "PASS"
    assert g.assumptions_in_narration(bad)["status"] == "FAIL"
