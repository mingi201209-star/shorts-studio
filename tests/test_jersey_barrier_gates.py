import json
import math
from pathlib import Path

from benchmarks.road_safety import jersey_barrier_gates as gates
from benchmarks.road_safety import jersey_barrier_motion as motion

MANIFEST = json.loads(Path("examples/experiments/jersey-barrier-manifest.json").read_text())


def _runs(angle=4.0):
    return {wall: motion.simulate(motion.Scenario(wall=wall, approach_deg=angle)) for wall in ("jersey", "flat")}


def test_profile_is_the_real_safety_shape():
    profile = motion.jersey_profile()
    assert profile[0] == (-0.305, 0.0) and profile[1] == (-0.305, 0.075)
    assert abs(profile[2][1] - 0.33) < 1e-9 and abs(profile[3][1] - 0.81) < 1e-9
    slope = math.degrees(math.atan2(profile[2][1] - profile[1][1], profile[2][0] - profile[1][0]))
    assert abs(slope - 55.0) < 1e-6


def test_wheel_lift_is_continuous_and_bounded():
    previous = 0.0
    for i in range(0, 400):
        lift = motion.wheel_lift(i / 1000.0)
        assert lift >= previous - 1e-12 and lift - previous < 0.004
        previous = lift
    assert motion.wheel_lift(-0.1) == 0.0 and previous == motion.SLOPE_TOP_HEIGHT


def test_shallow_hit_only_the_tyre_touches_the_jersey_barrier():
    summary = motion.summary(_runs()["jersey"])
    assert summary["first_tyre_contact_s"] is not None
    assert summary["first_body_contact_s"] is None and summary["min_body_gap_m"] > 0.02
    assert 0.05 < summary["peak_wheel_lift_m"] < motion.SLOPE_TOP_HEIGHT
    assert 0.02 < summary["peak_compression_m"] <= 0.09
    assert summary["min_heading_deg"] < 0 and abs(summary["end_heading_deg"]) < 1.0


def test_same_hit_on_a_flat_wall_lands_on_the_body():
    summary = motion.summary(_runs()["flat"])
    assert summary["first_body_contact_s"] is not None and summary["peak_wheel_lift_m"] == 0.0
    assert summary["end_speed_mps"] < 12.0  # friction along the wall costs speed


def test_car_never_slides_sideways_faster_than_its_heading_explains():
    for state in _runs()["jersey"][::50]:
        assert abs(state.yaw_rate) < math.radians(30)


def test_motion_gate_rejects_a_steeper_hit():
    ok = gates.motion_plausibility({w: motion.summary(s) for w, s in _runs(4.0).items()})
    assert ok["status"] == "PASS", ok
    steep = gates.motion_plausibility({w: motion.summary(s) for w, s in _runs(8.0).items()})
    assert steep["status"] == "FAIL"


def _telemetry(seen):
    """seen(frame, shot_id) -> set of events active and visible."""
    records = {}
    for shot in MANIFEST["shots"]:
        for frame in range(shot["start"], shot["end"] + 1):
            names = seen(frame, shot["id"])
            records[frame] = {"frame": frame, "shot_id": shot["id"],
                              "events": {n: {"active": True, "visible": True} for n in names}}
    return records


def _audio():
    beats, cues = [], []
    for shot in MANIFEST["shots"]:
        start, end = (shot["start"] - 1) / 30, shot["end"] / 30
        beats.append({"start": start, "end": end, "narration_en": shot["narration_en"]})
        cues.append({"start": start + 0.1, "end": end - 0.4, "text": "x"})
    return {"beats": beats, "cues": cues}


def _all_required(frame, shot_id):
    shot = next(s for s in MANIFEST["shots"] if s["id"] == shot_id)
    return {need["event"] for need in shot["must_show_while_spoken"]}


def test_narration_gate_passes_when_every_sentence_shows_its_event():
    result = gates.narration_screen_match(MANIFEST, _audio(), _telemetry(_all_required))
    assert result["status"] == "PASS", result["problems"]


def test_narration_gate_fails_a_sentence_spoken_over_a_car_doing_nothing():
    def seen(frame, shot_id):
        return set() if shot_id == "wheel_climb_macro" else _all_required(frame, shot_id)
    result = gates.narration_screen_match(MANIFEST, _audio(), _telemetry(seen))
    assert result["status"] == "FAIL"
    assert any("sentence 4" in p and "front_tyre_climbing" in p for p in result["problems"])


def test_narration_gate_fails_when_the_event_is_true_but_hidden():
    records = _telemetry(_all_required)
    for record in records.values():
        if record["shot_id"] == "flat_wall_strike":
            record["events"]["body_on_wall"]["visible"] = False
    assert gates.narration_screen_match(MANIFEST, _audio(), records)["status"] == "FAIL"


def test_narration_gate_fails_a_sentence_that_drifts_onto_the_next_shot():
    audio = _audio()
    audio["cues"][0]["end"] += 2.0
    audio["beats"][0]["end"] += 2.0
    audio["beats"][1]["start"] += 2.0
    audio["cues"][1]["start"] += 2.0
    result = gates.narration_screen_match(MANIFEST, audio, _telemetry(_all_required))
    assert any("spoken over another shot" in p for p in result["problems"])


def test_first_three_seconds_needs_two_things_starting_to_happen():
    def two(frame, shot_id):
        names = set()
        if frame >= 22:
            names.add("tyre_on_slope")
        if frame >= 40:
            names.add("suspension_compressed")
        return names
    assert gates.first_three_seconds(MANIFEST, _telemetry(two))["status"] == "PASS"
    # Already true on frame 1 is a state, not a change; one onset is not two.
    def one(frame, shot_id):
        return {"body_gap_open"} | ({"tyre_on_slope"} if frame >= 22 else set())
    assert gates.first_three_seconds(MANIFEST, _telemetry(one))["status"] == "FAIL"
    # Two events switching on together are one visual change.
    def together(frame, shot_id):
        return {"tyre_on_slope", "front_tyre_climbing"} if frame >= 22 else set()
    assert gates.first_three_seconds(MANIFEST, _telemetry(together))["status"] == "FAIL"


def test_caption_gate_keeps_text_above_the_shorts_overlay():
    cues = [{"start": 0.0, "end": 1.0, "text": "a"}, {"start": 1.0, "end": 2.0, "text": "b"}]
    assert gates.caption_safety(cues, [{"t": 0.5, "rows_in_band": [1447, 1498]}])["status"] == "PASS"
    assert gates.caption_safety(cues, [{"t": 0.5, "rows_in_band": [1657, 1708]}])["status"] == "FAIL"
    overlap = [{"start": 0.0, "end": 1.2, "text": "a"}, {"start": 1.0, "end": 2.0, "text": "b"}]
    assert gates.caption_safety(overlap, [{"t": 0.5, "rows_in_band": [1447, 1498]}])["status"] == "FAIL"
