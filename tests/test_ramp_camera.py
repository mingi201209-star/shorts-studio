import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import ramp_camera as rc
from benchmarks.road_safety import runaway_ramp_motion as m


def test_opening_move_audit_passes_on_the_real_truck_track():
    a = rc.audit(m.simulate())
    assert a.status == "PASS", a.problems
    assert a.metrics["longest_hold_s"] < 1.0 and a.metrics["subject_visible_fraction"] >= 0.9


def test_sim_time_matches_the_old_shots_at_the_ends_and_is_smooth_between():
    assert abs(rc.sim_time(1) - (-0.72)) < 1e-9 and abs(rc.sim_time(285) - 5.6) < 1e-6
    ts = [rc.sim_time(f) for f in range(1, 286)]
    steps = [b - a for a, b in zip(ts, ts[1:])]
    assert all(s > 0 for s in steps)
    assert max(abs(b - a) for a, b in zip(steps, steps[1:])) < 0.0005     # no hard change of playback rate (old: 0.0115)


def test_nose_track_is_continuous_through_first_tyre_contact():
    s = m.simulate()
    ys = [rc.nose_y(s, f) for f in range(1, 286)]
    assert all(b > a for a, b in zip(ys, ys[1:]))
    assert max(b - a for a, b in zip(ys, ys[1:])) < 1.0                    # no jump (the old track jumped 0.83 m)
    assert min(abs(y) for y in ys) < 0.5                                   # passes through 0 (the contact point)


def test_camera_keeps_the_established_opening_and_ends_beside_the_rear_tandem():
    first = rc.relative_path()[0]
    assert first.position == (2.7, 18.0, 0.45) and first.lens == 24.0
    last = rc.relative_path()[-1]
    assert last.position[1] < -10 and last.position[2] > 3.0
    assert len(rc.relative_path()) == rc.LAST_FRAME - rc.FIRST_FRAME + 1


def test_manifest_selects_the_continuous_camera_and_keeps_shot_coverage():
    import json
    man = json.loads((Path(__file__).resolve().parents[1] / "examples/experiments/runaway-ramp-manifest.json").read_text())
    assert man["camera"] == "continuous" and man["realism"] == "B"
    assert man["shots"][0]["start"] == rc.FIRST_FRAME and man["shots"][1]["end"] == rc.LAST_FRAME
