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


def test_timeline_puts_the_first_impact_in_the_first_second_and_covers_135_frames():
    assert cm.first_contact_film_s("H") <= 1.0
    assert cm.TOTAL_FRAMES == 135 and cm.segment_at(1)["id"] == "H" and cm.segment_at(61)["id"] == "X"
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
