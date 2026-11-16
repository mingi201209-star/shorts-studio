import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.crumple_zone.capabilities import CAPABILITIES  # noqa: E402
from shorts_studio.scene_spec import EpisodeSpec, evaluate_episode, full_render_allowed, load_spec, production_blockers, resolve_windows, update_registry, validate  # noqa: E402

SPEC = ROOT / "examples/episodes/ep04-crumple-zone-scene-spec.json"
PLAN = ROOT / "examples/experiments/crumple-zone-speech-plan.json"


def beats():
    return [b["narration_en"] for b in json.loads(PLAN.read_text())["variants"][0]["beats"]]


def cues_for(spec):
    return [{"start": 0.0 + 1.5 * i, "end": 1.4 + 1.5 * i, "text": s.cue} for i, s in enumerate(spec.scenes)]


def test_ep04_spec_is_complete_and_covers_the_narration_exactly():
    assert validate(load_spec(SPEC), beats()) == []


def test_a_scene_without_a_phenomenon_is_rejected():
    spec = load_spec(SPEC)
    d = json.loads(SPEC.read_text())
    d["scenes"][0]["phenomenon"]["description"] = ""
    d["scenes"][1]["success"] = []
    problems = validate(EpisodeSpec.from_dict(d), beats())
    assert any("narration-only scene" in p for p in problems) and any("no success conditions" in p for p in problems)
    d = json.loads(SPEC.read_text())
    d["scenes"][2]["narration"] = d["scenes"][2]["narration"] + " extra words"
    assert any("do not cover the narration" in p for p in validate(EpisodeSpec.from_dict(d), beats()))
    assert spec


def test_unimplemented_capabilities_block_production():
    spec = load_spec(SPEC)
    blockers = production_blockers(spec, CAPABILITIES)
    assert any("distance_time_bars" in b for b in blockers) and any("force_arrows" in b for b in blockers) and any("restraint_occupant" in b for b in blockers)
    ok, reasons = full_render_allowed(spec, {"scenes": {}}, CAPABILITIES, beats())
    assert not ok and any("no low-cost preview evidence" in r for r in reasons)


def _evidence(frames, stroke_onset=8, xray_onset=61, replay_onset=80):
    """Hero crash from frame `stroke_onset`, X-ray replay (a new pass, the metrics restart at frame 61) with its crash from frame `replay_onset`."""
    ev = {}
    for f in range(1, frames + 1):
        if f < 61:
            stroke = min(0.62, max(0.0, (f - stroke_onset) * 0.02))
        else:
            stroke = min(0.62, max(0.0, (f - replay_onset) * 0.02))
        ev[f] = {"metrics": {"crumple.stroke_m": stroke, "xray.factor": min(1.0, max(0.0, (f - xray_onset) / 30)), "nose.penetration_mm": 0.0, "cell.max_displacement_mm": 0.0,
                             "caption.overlap": 0.0, "rails.shortening_m": 0.8 * stroke}, "in_view": {n: True for n in ("car_front", "barrier", "crush_rails", "bumper_beam", "safety_cell")}}
    return ev


def test_alignment_passes_what_is_measured_and_never_passes_what_only_a_person_can_judge():
    spec = load_spec(SPEC)
    cues = [{"start": 0.0, "end": 1.0, "text": "Cars are designed"}, {"start": 1.9, "end": 2.5, "text": "Inside, hidden"}, {"start": 2.6, "end": 3.3, "text": "structures fold and"},
            {"start": 3.4, "end": 4.0, "text": "slow the car down"}] + [{"start": 6.0 + i, "end": 6.7 + i, "text": s.cue} for i, s in enumerate(spec.scenes[4:])]
    rep = evaluate_episode(spec, cues, 30.0, _evidence(135))
    s01 = rep["scenes"]["s01"]
    assert s01["verdict"] == "AUTO_PASS_HUMAN_REVIEW_PENDING" and s01["criteria"]["sound_off_understandable"] == "NOT_VERIFIED"
    assert rep["scenes"]["s02c"]["verdict"] == "PENDING_MORE_FRAMES"      # windows beyond the evidence are not evaluated
    assert rep["overall"] in ("PENDING_MORE_FRAMES", "AUTO_PASS_HUMAN_REVIEW_PENDING")


def test_alignment_fails_when_the_object_exists_but_does_not_move_or_is_late():
    spec = load_spec(SPEC)
    cues = [{"start": 0.0, "end": 1.0, "text": "Cars are designed"}, {"start": 1.9, "end": 2.5, "text": "Inside, hidden"}, {"start": 2.6, "end": 3.3, "text": "structures fold and"},
            {"start": 3.4, "end": 4.0, "text": "slow the car down"}] + [{"start": 6.0 + i, "end": 6.7 + i, "text": s.cue} for i, s in enumerate(spec.scenes[4:])]
    still = _evidence(135, stroke_onset=500)         # the subjects are in view but nothing deforms
    rep = evaluate_episode(spec, cues, 30.0, still)
    assert rep["scenes"]["s01"]["verdict"] == "FAIL"
    late = _evidence(135, xray_onset=100)            # the reveal starts 1.3 s after the spoken cue
    rep = evaluate_episode(spec, cues, 30.0, late)
    assert any(r["check"] == "s02a-onset" and r["status"] == "FAIL" for r in rep["scenes"]["s02a"]["checks"])


def test_registry_keeps_the_better_informed_verdict_and_gates_full_render(tmp_path):
    spec = load_spec(SPEC)
    reg_path = tmp_path / "reg.json"
    report = {"overall": "PENDING_MORE_FRAMES", "covered_seconds": 4.5,
              "scenes": {s.id: {"verdict": "AUTO_PASS_HUMAN_REVIEW_PENDING" if s.id == "s01" else "PENDING_MORE_FRAMES", "criteria": {}} for s in spec.scenes}}
    reg = update_registry(reg_path, spec.episode, "p1", report)
    assert reg["scenes"]["s01"]["verdict"] == "AUTO_PASS_HUMAN_REVIEW_PENDING"
    ok, reasons = full_render_allowed(spec, reg, CAPABILITIES, beats())
    assert not ok and any("s02c" in r for r in reasons)


def test_resolve_windows_uses_the_real_cue_starts():
    spec = load_spec(SPEC)
    w = resolve_windows(spec, cues_for(spec), 30.0)
    assert w["s01"]["start"] == 0.0 and w["s01"]["end"] == 1.5 and w[spec.scenes[-1].id]["end"] == 30.0
    bad = cues_for(spec)[:-1]
    try:
        resolve_windows(spec, bad, 30.0)
    except ValueError as e:
        assert "no spoken cue" in str(e)
    else:
        raise AssertionError
    assert copy
