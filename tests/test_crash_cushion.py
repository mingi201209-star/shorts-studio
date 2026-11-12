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
    assert sum(len(b["narration_en"].split()) for b in beats) <= 100
    assert manifest["shots"][0]["start"] == 1 and manifest["shots"][-1]["end"] == manifest["total_frames"]
    source = (ROOT / "benchmarks/road_safety/render_crash_cushion.py").read_text()
    for shot in manifest["shots"]:
        for need in shot["must_show_while_spoken"]:
            assert f'events["{need["event"]}"]' in source, need["event"]
