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
    assert blockers == []  # owner scope: bars/arrows/occupant are not part of EP.04, every scene uses an implemented capability
    assert production_blockers(spec, {**CAPABILITIES, "xray_reveal": False})  # a missing capability still blocks
    assert production_blockers(spec, {**CAPABILITIES, "rigid_stop_rebound": False})
    ok, reasons = full_render_allowed(spec, {"scenes": {}}, CAPABILITIES, beats())
    assert not ok and any("no low-cost preview evidence" in r for r in reasons)


def _real_evidence():
    from benchmarks.crumple_zone import evidence_sim as es
    return es.timeline_evidence(es.Car(es.load_fixture()))


def _cues():
    from benchmarks.crumple_zone import crumple_motion as cm
    c = cm._cues()
    return c["cues"], c["target_seconds"]


def test_alignment_passes_what_is_measured_and_never_passes_what_only_a_person_can_judge():
    spec = load_spec(SPEC)
    cues, total = _cues()
    rep = evaluate_episode(spec, cues, total, _real_evidence())
    s01 = rep["scenes"]["s01"]
    assert s01["verdict"] == "AUTO_PASS_HUMAN_REVIEW_PENDING" and s01["criteria"]["sound_off_understandable"] == "NOT_VERIFIED"
    assert rep["overall"] == "AUTO_PASS_HUMAN_REVIEW_PENDING"
    short = {f: e for f, e in _real_evidence().items() if f <= 150}
    rep = evaluate_episode(spec, cues, total, short)
    assert rep["scenes"]["s05c"]["verdict"] == "PENDING_MORE_FRAMES"       # windows beyond the evidence are not evaluated


def test_alignment_fails_when_the_object_exists_but_does_not_move_or_is_late():
    import copy as cp
    spec = load_spec(SPEC)
    cues, total = _cues()
    still = cp.deepcopy(_real_evidence())             # the subjects are in view but nothing deforms
    for e in still.values():
        for k in ("crumple.stroke_m", "crumple.crushed_depth_m", "body.max_rise_m", "rails.shortening_m"):
            if k in e["metrics"]:
                e["metrics"][k] = 0.0
    rep = evaluate_episode(spec, cues, total, still)
    assert rep["scenes"]["s01"]["verdict"] == "FAIL" and rep["scenes"]["s02b"]["verdict"] == "FAIL"
    ev = _real_evidence()
    late = {f: cp.deepcopy(ev[max(1, f - 90)]) for f in ev}      # every picture event arrives 3 s after the words
    rep = evaluate_episode(spec, cues, total, late)
    assert any(r["check"] == "s03a-onset" and r["status"] == "FAIL" for r in rep["scenes"]["s03a"]["checks"])


def test_registry_keeps_the_better_informed_verdict_and_gates_full_render(tmp_path):
    spec = load_spec(SPEC)
    reg_path = tmp_path / "reg.json"
    report = {"overall": "PENDING_MORE_FRAMES", "covered_seconds": 4.5,
              "scenes": {s.id: {"verdict": "AUTO_PASS_HUMAN_REVIEW_PENDING" if s.id == "s01" else "PENDING_MORE_FRAMES", "criteria": {}} for s in spec.scenes}}
    reg = update_registry(reg_path, spec.episode, "p1", report)
    assert reg["scenes"]["s01"]["verdict"] == "AUTO_PASS_HUMAN_REVIEW_PENDING"
    ok, reasons = full_render_allowed(spec, reg, CAPABILITIES, beats())
    assert not ok and any("s02" in r for r in reasons)


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
