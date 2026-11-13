import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import breakaway_sign_gates as gates
from benchmarks.road_safety import breakaway_sign_motion as motion

ROOT = Path(__file__).resolve().parents[1]


def test_only_the_fixed_post_stops_the_car():
    s = motion.summary()
    assert s["rigid"]["delta_v_mps"] > 24.0 and s["rigid"]["stop_distance_m"] < 1.0
    assert s["breakaway"]["speed_kept_fraction"] > 0.95
    assert gates.motion_plausibility(s)["status"] == "PASS"


def test_impulse_obeys_linear_and_angular_momentum():
    hit = motion.impact()
    m, _cm, inertia = motion.post_inertia()
    # linear: what the car loses to the post, the post gains
    assert abs(hit["post_cm_speed_mps"] * m - hit["impulse_Ns"]) < 1e-6
    # angular, about the post's centre of mass: J * arm = I * spin
    assert abs(hit["impulse_Ns"] * hit["arm_m"] - inertia * hit["post_spin_radps"]) < 1e-6
    # plastic contact: the struck point leaves at the car's speed (before the base impulse)
    struck = hit["post_cm_speed_mps"] + hit["post_spin_radps"] * hit["arm_m"]
    assert abs(struck - (motion.SPEED - hit["impulse_Ns"] / motion.CAR_MASS)) < 1e-6


def test_post_goes_over_the_car_and_lands_behind_it():
    b = motion.summary()["breakaway"]
    assert b["min_clearance_m"] >= 0.10
    assert b["post_landed"] and b["post_landing_y_m"] < b["car_tail_at_landing_m"]


def test_slip_base_holds_in_wind_and_releases_in_a_crash():
    b = motion.summary()["breakaway"]
    assert b["wind_shear_N"] < 0.5 * b["slip_force_N"] < 0.25 * b["mean_impact_force_N"]


def test_gate_catches_a_post_that_would_hit_the_roof():
    s = motion.summary()
    s["breakaway"] = {**s["breakaway"], "min_clearance_m": -0.2}
    assert gates.motion_plausibility(s)["status"] == "FAIL"


def test_gate_catches_a_fixed_post_that_stops_too_softly():
    s = motion.summary()
    s["rigid"] = {**s["rigid"], "stop_distance_m": 3.0}
    assert gates.motion_plausibility(s)["status"] == "FAIL"


def test_manifest_plan_captions_and_events_agree():
    from benchmarks.road_safety.caption_phrases import phrase_groups
    manifest = json.loads((ROOT / "examples/experiments/breakaway-sign-manifest.json").read_text())
    plan = json.loads((ROOT / "examples/experiments/breakaway-sign-speech-plan.json").read_text())
    beats = plan["variants"][0]["beats"]
    assert [b["narration_en"] for b in beats] == [s["narration_en"] for s in manifest["shots"]]
    assert sum(len(b["narration_en"].split()) for b in beats) <= 108
    assert manifest["shots"][0]["start"] == 1 and manifest["shots"][-1]["end"] == manifest["total_frames"]
    source = (ROOT / "benchmarks/road_safety/render_breakaway_sign.py").read_text()
    for shot in manifest["shots"]:
        for need in shot["must_show_while_spoken"]:
            assert f'events["{need["event"]}"]' in source, need["event"]
        tokens = shot["narration_en"].split()
        spans = phrase_groups(shot["narration_en"])
        assert spans[0][0] == 0 and spans[-1][1] == len(tokens)
        assert all(len(" ".join(tokens[i:j])) <= 24 and j - i >= 2 for i, j in spans)
