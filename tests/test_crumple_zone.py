import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.crumple_zone import crumple_gates as g  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.crumple_zone import captions  # noqa: E402


def test_both_cars_stop_with_the_same_energy_and_the_force_claim_holds():
    assert g.same_conditions()["status"] == "PASS"
    r = g.energy_and_claims()
    assert r["status"] == "PASS", r
    assert r["force_ratio_rigid_over_crumple"] >= 5


def test_crush_map_never_touches_the_passenger_cell_and_progresses_rearward():
    r = g.crush_map_keeps_the_cell()
    assert r["status"] == "PASS", r


def test_timeline_puts_the_first_impact_in_the_first_second_and_covers_the_whole_film():
    assert cm.first_contact_film_s("H") <= 1.0
    assert cm.TOTAL_FRAMES == 780 and cm.segment_at(1)["id"] == "H" and cm.segment_at(61)["id"] == "X"
    assert [cm.frame_time(f) for f in (1, 2, 3)] == sorted(cm.frame_time(f) for f in (1, 2, 3))


def test_pose_sampling_is_finer_than_a_film_frame():
    # one film frame covers SLOW / FPS seconds of simulated time; the simulation must have at least 4 samples per frame (the EP.03 stutter lesson)
    assert cm.RENDER_HZ * cm.SLOW / cm.FPS >= 4


def test_gates_reject_bad_input():
    tele = [{"frame": f, "segment": "H", "layout": "full", "crumple": {"nose_penetration_mm": 9.0, "wheel_z_gap_mm": 0.0, "stroke_m": 0.0, "sign_in_view": False}} for f in (1, 2)]
    assert g.telemetry_geometry(tele)["status"] == "FAIL"
    assert g.smoothness(np.array([0.5, 0.0, 0.4]))["status"] == "FAIL"
    assert g.smoothness(np.array([0.5, 0.4, 0.4]))["status"] == "PASS"


def test_captions_match_the_narration():
    for text in captions.CURATED:
        assert captions.single_line_groups(text)


def test_a_vertex_at_or_a_hair_ahead_of_the_measured_nose_is_pushed_back_with_the_nose():
    # preview 6: the registration plate sat 1e-7 m ahead of the measured nose, was not moved and stuck 0.62 m into the barrier
    nose = 1.926
    pts = np.array([[0.0, nose + 1e-7, 0.5], [0.0, nose, 0.5], [0.0, nose - 0.02, 0.5]])
    out = cm.crush_map(pts, 0.35, nose)
    assert np.all(out[:, 1] <= nose - 0.35 + 0.02 + 1e-9)
    assert abs(out[0, 1] - (nose - 0.35)) < 1e-6


def test_full_timeline_is_planned_on_the_real_cues_and_every_offline_check_passes():
    """The whole 26 s film is checked offline (no render): sync to the measured speech, scene alignment, no wall penetration, nothing under the captions, X-ray against the road."""
    import json
    from pathlib import Path
    from benchmarks.crumple_zone import evidence_sim as es
    from shorts_studio.scene_spec import evaluate_episode, load_spec
    root = Path(__file__).resolve().parents[1]
    rc = json.loads((root / "examples/experiments/crumple-zone-real-cues.json").read_text())
    car = es.Car(es.load_fixture())
    ev = es.timeline_evidence(car)
    assert len(ev) == cm.TOTAL_FRAMES == round(rc["target_seconds"] * cm.FPS)
    assert g.sync_to_speech(rc["cues"])["status"] == "PASS"
    al = evaluate_episode(load_spec(root / "examples/episodes/ep04-crumple-zone-scene-spec.json"), rc["cues"], rc["target_seconds"], ev)
    assert al["overall"] != "FAIL", {sid: [r for r in sc["checks"] if r["status"] == "FAIL"] for sid, sc in al["scenes"].items()}
    assert max(e["metrics"]["nose.penetration_mm"] for e in ev.values()) <= 5.0
    assert max(e["metrics"]["caption.overlap"] for e in ev.values()) <= 0.2
    assert max(e["metrics"]["cell.max_displacement_mm"] for e in ev.values()) <= 1.0
    assert g.xray_against_road(car, range(61, cm.TOTAL_FRAMES + 1))["status"] == "PASS"


def test_every_segment_keeps_moving_and_the_workflow_covers_all_frames():
    """No frozen frame by construction (the crush lasts to the last frame of each replay), and the preview workflow renders exactly TOTAL_FRAMES."""
    from pathlib import Path
    rec = cm.simulate("crumple")
    t = np.array(rec["t"])
    stop = float(t[np.argmax(np.array(rec["v"]) <= 1e-9)]) - cm.LEAD_SIM / (cm.V0_KMH / 3.6)
    assert abs(stop - cm.T_MOTION_END_S) <= 0.01      # the constant the replay fit is built on
    for seg in cm.SEGMENTS[3:]:
        slow = seg["slow"]
        assert abs(cm.first_contact_film_s(seg["id"]) - cm.CONTACT_FILM_S) < 0.01
        assert cm.CONTACT_FILM_S + cm.T_MOTION_END_S / slow >= (seg["last"] - seg["first"]) / cm.FPS      # still moving at the last frame
    wf = (Path(__file__).resolve().parents[1] / ".github/workflows/ep04-crumple-preview.yml").read_text()
    assert f"(1, {cm.TOTAL_FRAMES})" in wf


def test_only_the_two_comparison_signs_exist_besides_captions_and_they_are_in_the_mobile_safe_area():
    from benchmarks.crumple_zone import crumple_cameras as cc
    assert cc.SIGN["words"] == {"crumple": "CRUMPLE", "rigid": "RIGID"}      # one word per car, nothing else is drawn as text in the scene
    assert g.text_safe_area()["status"] == "PASS"
    old = dict(cc.SIGN, pos=(-1.55, -2.0, 0.25), size=0.3)      # the first placement: it sat on the caption rows
    try:
        cc.SIGN = old
        assert g.text_safe_area()["status"] == "FAIL"
    finally:
        cc.SIGN = {"pos": (-1.2, -2.0, 0.25), "size": 0.18, "char_w": 0.75, "words": {"crumple": "CRUMPLE", "rigid": "RIGID"}}
