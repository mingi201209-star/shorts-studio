"""EP.04 mesh / wall / camera / timing checks on the REAL sedan vertices (fixture dumped by Blender once), in plain Python: seconds instead of a 17-minute preview."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.crumple_zone import crumple_gates as gates  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.crumple_zone import evidence_sim as es  # noqa: E402
from shorts_studio.scene_spec import evaluate_episode, load_spec  # noqa: E402

CAR = es.Car(es.load_fixture())
EVIDENCE = es.timeline_evidence(CAR)
CUES = cm._cues()


def test_nothing_goes_through_the_barrier_including_plate_bumper_and_wheels():
    worst = max(e["metrics"].get("nose.penetration_mm", 0.0) for e in EVIDENCE.values())
    assert worst <= 5.0, worst
    names = {p["name"] for p in es.load_fixture()["parts"] if p["wheel"] is None}
    assert {"Blank registration panel", "Bumper", "Grille bar", "Headlamp"} <= names


def test_the_front_wheel_stays_on_the_ground_and_never_ahead_of_the_crushed_nose():
    for s in np.linspace(0.0, cm.PROFILES["crumple"]["stroke"], 40):
        y = cm.wheel_y(float(CAR.wheels["front_right"][1]), float(s), CAR.nose)
        assert y + es.TYRE_RADIUS <= CAR.nose - s + 1e-9


def test_the_passenger_cell_geometry_never_moves():
    assert max(e["metrics"].get("cell.max_displacement_mm", 0.0) for e in EVIDENCE.values()) <= 1.0


def test_the_action_is_never_under_the_captions():
    assert max(e["metrics"]["caption.overlap"] for e in EVIDENCE.values()) <= 0.2


def test_the_car_front_is_in_view_through_both_crashes_and_the_run_ups():
    for f in range(1, cm.SEGMENTS[1]["last"] + 1):
        v = EVIDENCE[f]["in_view"]
        assert v.get("car_front") or v.get("rigid_car_front") or v.get("driver") or v.get("rigid_driver"), f      # the film shows the car front or (owner request) only the driver's seat


def test_the_ghost_body_is_seen_against_road_and_barrier_not_the_sky():
    assert gates.xray_against_road(CAR, range(1, cm.TOTAL_FRAMES + 1))["status"] == "PASS"


def test_the_rails_only_ever_shorten_during_the_crash_and_the_front_stays_crushed_after_it():
    k = cm.SEGMENTS[0]
    shorten = [EVIDENCE[f]["metrics"]["rails.shortening_m"] for f in range(k["first"], k["last"] + 1)]
    assert all(b >= a - 1e-9 for a, b in zip(shorten, shorten[1:]))
    assert shorten[-1] >= 0.5
    c = cm.SEGMENTS[2]
    assert all(EVIDENCE[f]["metrics"]["crumple.crushed_depth_m"] >= 0.8 for f in range(c["first"], c["last"] + 1))


def test_the_rigid_car_stays_within_six_centimetres_and_then_really_moves_away_from_the_wall():
    r = cm.SEGMENTS[1]
    stroke = max(EVIDENCE[f]["metrics"]["rigid.stroke_m"] for f in range(r["first"], r["last"] + 1))
    assert 0.04 <= stroke <= 0.06
    assert max(EVIDENCE[f]["metrics"]["rigid.rebound_m"] for f in range(r["first"], r["last"] + 1)) >= 1.0
    assert max(EVIDENCE[f]["metrics"]["rigid.speed_away_mps"] for f in range(r["first"], r["last"] + 1)) >= 1.0


def test_every_scene_of_the_spec_is_aligned_on_the_simulated_evidence_with_the_measured_cues():
    spec = load_spec(ROOT / "examples/episodes/ep04-crumple-zone-scene-spec.json")
    rep = evaluate_episode(spec, CUES["cues"], CUES["target_seconds"], EVIDENCE)
    fails = {sid: [c for c in sc["checks"] if c["status"] == "FAIL"] for sid, sc in rep["scenes"].items()}
    assert rep["overall"] != "FAIL", {k: v for k, v in fails.items() if v}
    assert all(sc["verdict"] == "AUTO_PASS_HUMAN_REVIEW_PENDING" for sc in rep["scenes"].values())      # software cannot decide the rest: a person has to watch it


def test_the_scene_windows_follow_the_cues_in_order():
    from shorts_studio.scene_spec import alignment
    spec = load_spec(ROOT / "examples/episodes/ep04-crumple-zone-scene-spec.json")
    windows = alignment.resolve_windows(spec, CUES["cues"], CUES["target_seconds"])
    starts = [windows[s.id]["start"] for s in spec.scenes]
    assert starts == sorted(starts) and windows[spec.scenes[-1].id]["end"] == CUES["target_seconds"]
