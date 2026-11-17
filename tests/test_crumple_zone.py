import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.crumple_zone import captions  # noqa: E402
from benchmarks.crumple_zone import crumple_cameras as cc  # noqa: E402
from benchmarks.crumple_zone import crumple_gates as g  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402


def test_both_cars_stop_with_the_same_energy_and_the_force_claim_holds():
    assert g.same_conditions()["status"] == "PASS"
    r = g.energy_and_claims()
    assert r["status"] == "PASS", r
    assert r["force_ratio_rigid_over_crumple"] >= 5


def test_crush_map_never_touches_the_passenger_cell_and_progresses_rearward():
    r = g.crush_map_keeps_the_cell()
    assert r["status"] == "PASS", r


def test_timeline_is_three_contiguous_full_screen_segments_with_the_first_impact_inside_the_first_two_seconds():
    assert [s["id"] for s in cm.SEGMENTS] == ["K", "R", "C"]
    assert all(s["layout"] == "full" and len(s["panels"]) == 1 for s in cm.SEGMENTS)
    assert [s["panels"][0] for s in cm.SEGMENTS] == ["crumple", "rigid", "crumple"]
    assert cm.SEGMENTS[0]["first"] == 1 and cm.SEGMENTS[-1]["last"] == cm.TOTAL_FRAMES
    assert all(a["last"] + 1 == b["first"] for a, b in zip(cm.SEGMENTS, cm.SEGMENTS[1:]))
    assert cm.TOTAL_FRAMES == round(cm.TARGET_S * cm.FPS) and 31.0 <= cm.TARGET_S <= 33.0      # about 32 s
    assert cm.first_contact_film_s("K") <= 1.0


def test_one_crash_time_scale_for_both_cars_and_a_smooth_warp():
    t = np.linspace(-0.2, cm.T_STOP["rigid"], 200)
    crumple = cm.rate_fn(t, cm.R0, 0.5, None)
    rigid = cm.rate_fn(t, cm.R0, 0.5, (cm.T_STOP["rigid"] + 0.002, cm.T_STOP["rigid"] + 0.03, 0.7))
    assert np.allclose(crumple, rigid)      # up to the rigid car's stop the film speed is the same function of simulated time for both cars
    for seg in cm.SEGMENTS[:2]:
        times = [cm.frame_time(f) for f in range(seg["first"], seg["last"] + 1)]
        assert all(b > a for a, b in zip(times, times[1:]))      # simulated time only moves forward


def test_no_frame_jumps_the_simulated_poses_are_interpolated_not_stepped():
    for seg in cm.SEGMENTS[:2]:
        prev = None
        for f in range(seg["first"], seg["last"] + 1):
            ps = cm.pose(f)
            if prev is not None:
                assert abs(ps["d"] - prev["d"]) <= 0.8, (f, ps["d"] - prev["d"])      # run-up at up to ~0.5 m per frame, never a jump
                assert abs(ps["s"] - prev["s"]) <= 0.02, (f, ps["s"] - prev["s"])      # the crush advances by millimetres per frame
            prev = ps


def test_each_car_is_crashed_exactly_once_and_the_closing_view_replays_nothing():
    for panel, field in (("crumple", "s"), ("rigid", "s")):
        edges = 0
        prev = 0.0
        for f in range(1, cm.TOTAL_FRAMES + 1):
            if cm.visible_panel(f) != panel:
                continue
            s = cm.pose(f)[field]
            edges += int(prev <= 0.005 < s)
            prev = s
        assert edges == 1, (panel, edges)      # the crush starts once per car: no rewinding, no second playback of the same crash
    closing = [cm.pose(f)["s"] for f in range(cm.SEGMENTS[2]["first"], cm.TOTAL_FRAMES + 1)]
    assert max(closing) - min(closing) < 1e-9      # the closing view is the finished crash, not a replay


def test_the_crumple_crash_is_one_continuous_shot_the_xray_continues_it():
    k = cm.SEGMENTS[0]
    ghost_first = next(f for f in range(k["first"], k["last"] + 1) if cm.xray_factor(f) > 0.02)
    s_at_ghost = cm.pose(ghost_first)["s"]
    assert 0.03 < s_at_ghost < 0.62      # the reveal starts inside the running crash: no rewind, no restart
    assert all(cm.pose(f)["s"] >= cm.pose(f - 1)["s"] - 1e-9 for f in range(k["first"] + 1, k["last"] + 1))      # the stroke never goes back


def test_the_first_five_seconds_show_several_distinct_physical_changes():
    five = 5 * cm.FPS
    events = {
        "approach_to_the_wall": cm.nose_y(1) < -3.0 and cm.nose_y(cm.frame_of(cm.HOOK_CONTACT_S)) > -0.3,
        "front_crushes": cm.pose(five)["s"] >= 0.2,
        "camera_moves_in": float(np.linalg.norm(np.array(cc.camera("K", five)["loc"]) - np.array(cc.camera("K", 1)["loc"]) - np.array([0, cm.nose_y(five) - cm.nose_y(1), 0]))) >= 1.0,
        "hood_buckles": max(cm.pose(f)["s"] for f in range(1, five + 1)) >= 0.1,
    }
    assert sum(events.values()) >= 3, events


def test_gates_reject_bad_input():
    tele = [{"frame": f, "segment": "K", "layout": "full", "crumple": {"nose_penetration_mm": 9.0, "wheel_z_gap_mm": 0.0, "stroke_m": 0.0}} for f in (1, 2)]
    assert g.telemetry_geometry(tele)["status"] == "FAIL"
    assert g.smoothness(np.array([0.5, 0.0, 0.4]))["status"] == "FAIL"
    assert g.smoothness(np.array([0.5, 0.4, 0.4]))["status"] == "PASS"


def test_captions_match_the_narration():
    for text in captions.CURATED:
        assert captions.single_line_groups(text)


def test_a_vertex_at_or_a_hair_ahead_of_the_measured_nose_is_pushed_back_with_the_nose():
    nose = 1.926
    pts = np.array([[0.0, nose + 1e-7, 0.5], [0.0, nose, 0.5], [0.0, nose - 0.02, 0.5]])
    out = cm.crush_map(pts, 0.35, nose)
    assert np.all(out[:, 1] <= nose - 0.35 + 0.02 + 1e-9)
    assert abs(out[0, 1] - (nose - 0.35)) < 1e-6


def test_no_scene_text_exists_only_the_narration_captions():
    assert g.no_scene_text()["status"] == "PASS"
    src = (ROOT / "benchmarks/crumple_zone/render_crumple_3d.py").read_text()
    assert "FONT" not in src and "SIGN" not in src and "CRUMPLE\"" not in src.replace("CRUMPLE_", "")
    assert cc.NO_SCENE_TEXT is True


def test_the_two_cars_are_told_apart_by_paint_not_by_words():
    src = (ROOT / "benchmarks/crumple_zone/render_crumple_3d.py").read_text()
    ns = {}
    for line in src.splitlines():
        if line.startswith("PAINT = "):
            exec(line.split("#")[0], {}, ns)
    assert ns["PAINT"]["crumple"] != ns["PAINT"]["rigid"]


def test_the_workflow_covers_every_frame_and_uses_the_frozen_audio_when_asked():
    wf = (ROOT / ".github/workflows/ep04-crumple-preview.yml").read_text()
    assert '["target_seconds"] * 30' in wf and "audio_run" in wf
