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


def test_camera_keeps_the_established_opening_and_ends_behind_the_nose_on_the_right():
    first = rc.relative_path()[0]
    assert first.position == (2.7, 18.0, 0.45) and first.lens == 24.0
    last = rc.relative_path()[-1]                                      # the shipping (round 2) camera
    assert last.position[1] < -5 and last.position[0] > 5.0
    assert len(rc.relative_path()) == rc.LAST_FRAME - rc.FIRST_FRAME + 1


def test_round3_variant_ends_inside_the_gravel_bed_near_the_nose():
    last = rc.relative_path(3)[-1]
    assert 2.5 < last.position[0] <= 3.6 and last.position[1] > -2.0


def test_the_truck_outline_stays_readable_after_the_first_two_seconds():
    """Round-2 finding: hugging the wheels made the truck vanish. The outline (>= 4 of 8 bounding-box corners in the picture)
    must be on screen in most frames after frame 60, never gone for long, and the truck must not shrink to a speck."""
    rep = rc.silhouette_report(m.simulate(), min_corners=4)
    assert rep["share_from_frame_61"] >= 0.85
    assert rep["longest_run_without_s"] <= 1.5
    assert rep["truck_width_fraction_median_from_61"] >= 0.5 and rep["truck_width_fraction_p10_from_61"] >= 0.35


def test_manifest_selects_the_continuous_camera_and_keeps_shot_coverage():
    import json
    man = json.loads((Path(__file__).resolve().parents[1] / "examples/experiments/runaway-ramp-manifest.json").read_text())
    assert man["camera"] == "continuous" and man["realism"] == "B"
    assert man["shots"][0]["start"] == rc.FIRST_FRAME and man["shots"][1]["end"] == rc.LAST_FRAME


# ---------------------------------------------------------------- round 3 (frames 190-285)

def test_round3_keeps_frames_1_to_189_exactly_as_round_2():
    old = rc._round2_path()
    new = rc.relative_path(3)
    assert len(new) == len(old) == 285
    for a, b in zip(new[:189], old[:189]):
        assert a.position == b.position and a.aim == b.aim and a.lens == b.lens


def test_round3_joins_the_old_path_without_a_jump():
    rep = rc.junction_report(m.simulate(), 3)
    assert rep["speed_change_across_join_mps"] <= 1.0
    assert rep["turn_rate_change_across_join_dps"] <= 10.0
    assert abs(rep["lens"][1] - rep["lens"][2]) < 0.2


def test_round3_audit_still_passes_on_the_whole_opening():
    a = cam_audit_round(3)
    assert a.status == "PASS", a.problems


def cam_audit_round(round_):
    from benchmarks.road_safety import cinematic_camera as cc
    states = m.simulate()
    limits = cc.Limits(max_speed=40.0, max_accel=120.0, max_aim_rate=120.0, max_hold_seconds=1.0, min_subject_visible=0.9)
    return cc.audit(rc.world_path(states, round_), rc.FPS, subject=lambda t: rc.aim_point(states, t, round_), obstacles=(), limits=limits, moving_start=True)


def test_the_shipping_default_is_the_verified_round_2_camera():
    assert rc.ACTIVE_ROUND == 2
    assert [p.position for p in rc.relative_path()] == [p.position for p in rc.relative_path(2)]
    assert rc.audit(m.simulate()).status == "PASS"


def test_round3_picture_is_gravel_wheels_and_body_not_wall_and_empty_ground():
    """Measured with ray casting into the simplified scene; thresholds come from the review of the round-2 clip (earth ~33 %, gravel ~13 %)."""
    s = m.simulate()
    for first, last in ((190, 230), (231, 285)):
        rep = rc.composition_report(s, first, last, 3)
        med = rep["median"]
        assert med["gravel"] >= 0.30, (first, rep)
        assert med["earth"] <= 0.12, (first, rep)
        assert med["trailer"] <= 0.12, (first, rep)
        assert rep["wheel_gravel_body_together"] >= 0.9, (first, rep)
    rows = [rc.composition(rc.relative_path(3)[f - 1], rc.nose_y(s, f)) for f in range(190, 286)]
    assert min(r["wheel"] for r in rows) >= 0.015


def test_projection_centre_matches_the_renderers_shift():
    from benchmarks.road_safety import cinematic_camera as cc
    assert cc.PICTURE_CENTER_ROW == 700.0
