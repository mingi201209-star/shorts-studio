import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
from pathlib import Path

from benchmarks.road_safety import crash_cushion_gates as gates
from benchmarks.road_safety import crash_cushion_motion as motion

ROOT = Path(__file__).resolve().parents[1]


def _summaries():
    return {c: motion.summary(motion.simulate(motion.Scenario(case=c)), c) for c in ("array", "wall")}


def test_array_stops_over_about_six_metres_and_wall_over_about_one():
    s = _summaries()
    assert 5.5 <= s["array"]["stop_distance_m"] <= 7.0
    assert 0.6 <= s["wall"]["stop_distance_m"] <= 1.2
    assert gates.motion_plausibility(s)["status"] == "PASS"


def test_rows_get_heavier_toward_the_back():
    kg = [k for _, k in motion.ROWS]
    assert kg == sorted(kg) and kg[-1] > 3 * kg[0]


def test_deceleration_is_lighter_at_first_and_peaks_deeper_in():
    a = _summaries()["array"]
    assert a["mean_decel_first_third_g"] < a["mean_decel_middle_third_g"]
    assert a["peak_decel_at_m"] > 0.3 * a["stop_distance_m"]


def test_car_never_speeds_up_and_ends_stopped():
    states = motion.simulate()
    assert all(b.speed <= a.speed + 1e-9 for a, b in zip(states, states[1:]))
    assert motion.stop_state(states).speed <= motion.STOPPED_SPEED


def test_sand_leaves_at_about_the_cars_speed_and_only_after_the_nose_arrives():
    states = motion.simulate()
    times = motion.burst_times(states)
    parts = motion.build_particles(states)
    assert parts and all(p.t0 == times[p.barrel] for p in parts)
    for p in parts:
        assert motion.particle_state(p, p.t0 - 1e-3) is None
        car = motion.sample(states, p.t0).speed
        assert 0.78 * car <= p.v0[1] <= 1.13 * car


def test_particles_end_on_the_ground():
    states = motion.simulate()
    for p in motion.build_particles(states)[:80]:
        pos, _angle, airborne = motion.particle_state(p, p.t0 + 5.0)
        assert not airborne and pos[2] < 0.05


def test_plausibility_gate_catches_a_wall_that_stops_too_softly():
    s = _summaries()
    s["wall"] = {**s["wall"], "stop_distance_m": 3.0}
    verdict = gates.motion_plausibility(s)
    assert verdict["status"] == "FAIL"


def test_manifest_matches_plan_and_names_real_events():
    manifest = json.loads((ROOT / "examples/experiments/sand-barrel-manifest.json").read_text())
    plan = json.loads((ROOT / "examples/experiments/sand-barrel-speech-plan.json").read_text())
    beats = plan["variants"][0]["beats"]
    assert [b["narration_en"] for b in beats] == [s["narration_en"] for s in manifest["shots"]]
    assert sum(len(b["narration_en"].split()) for b in beats) <= 105
    assert manifest["shots"][0]["start"] == 1 and manifest["shots"][-1]["end"] == manifest["total_frames"]
    source = (ROOT / "benchmarks/road_safety/render_crash_cushion.py").read_text()
    for shot in manifest["shots"]:
        for need in shot["must_show_while_spoken"]:
            assert f'events["{need["event"]}"]' in source, need["event"]


def test_barrels_are_squashed_before_their_shell_gives_way():
    states = motion.simulate()
    times = motion.burst_times(states)
    for row, t_burst in enumerate(times):
        before = motion.sample(states, t_burst - 0.01)
        after = motion.sample(states, t_burst + 0.001)
        assert 0.0 < motion.crush_fraction(before.nose, row) <= 1.0
        assert motion.crush_fraction(after.nose, row) == 1.0
        # the squashed barrel's front face never lags behind the nose
        front_face = motion.barrel_back(row) - motion.BARREL_D * (1 - motion.CRUSH_RATIO * motion.crush_fraction(after.nose, row))
        assert front_face >= after.nose - 0.06


def test_caption_phrases_cover_each_sentence_exactly_and_stay_short():
    from benchmarks.road_safety.caption_phrases import phrase_groups
    plan = json.loads((ROOT / "examples/experiments/sand-barrel-speech-plan.json").read_text())
    for beat in plan["variants"][0]["beats"]:
        text, tokens = beat["narration_en"], beat["narration_en"].split()
        spans = phrase_groups(text)
        assert spans[0][0] == 0 and spans[-1][1] == len(tokens)
        assert all(a[1] == b[0] for a, b in zip(spans, spans[1:]))
        assert all(len(" ".join(tokens[i:j])) <= 31 and j - i >= 2 for i, j in spans)
