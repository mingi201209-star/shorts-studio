"""Train Wheels V2 -- Psychological Entertainment Contract report-only pilot.

This is the FIRST real content to exercise the Declared Event Graph
end-to-end (examples/train_wheels_v2.json). It is deliberately separate
from PR #24 (content/train-wheel-conicity, the original Train Wheels
production) -- that content and manifest are untouched.

IMPORTANT SCOPE NOTE: this test does not render anything and does not call
real TTS. scene_windows below is built by _simulate_scene_windows(), which
estimates each narration_plan phrase's duration from a fixed Korean
reading-rate constant -- NOT a real, measured narration_unit timing from
tts.py. This is a deliberate, explicit simplification for a report-only
pilot (per instruction: no render yet), and it is why this test's "real
narration text" is identical to the manifest's declared text: in an actual
render, tts.py's real synthesis could split/reword a phrase and this
identity would no longer hold, which is exactly the scenario Phase 2's
TEXT_DIVERGES_FROM_ACTUAL_NARRATION mismatch check exists to catch. This
test demonstrates the CONTRACT MECHANISM working end-to-end on a real,
carefully-written script; it is not itself proof the mechanism catches a
production divergence (test_entertainment_contract_phase2.py's fixtures
already prove that, on synthetic data).

The judge used here (_HonestDemoJudge) is a test double whose verdicts are
hand-authored to reflect what a careful human reviewer would say about
THIS specific script -- it is not a real model call (see PR #27's
AnthropicJudge for that; wiring a real judge into this specific pilot is
Phase 2 section 8's "PEC report-only" step, expected to happen once PR #27
is merged and a real ANTHROPIC_API_KEY is configured, not part of this
content-only PR).
"""
from pathlib import Path

from shorts_studio.project import load_project
from shorts_studio.entertainment_rules import JUDGE_FAIL, JUDGE_NOT_EVALUATED, JUDGE_PASS
from shorts_studio.entertainment_qa import (
    JudgeVerdict, build_observed_evidence, compute_curiosity_loops,
    compute_entertainment_diagnostics, run_entertainment_contract_report,
    verify_unresolved_critical_gaps,
)

MANIFEST_PATH = "examples/train_wheels_v2.json"

# Korean reading-rate estimate ONLY -- see module docstring. Roughly matches
# this engine's own edge-tts pacing at a neutral rate, but is NOT a
# measurement.
_ESTIMATED_CHARS_PER_SECOND = 6.5
_INTER_PHRASE_PAUSE_SECONDS = 0.35


def _estimate_duration(text: str) -> float:
    return max(0.6, len(text) / _ESTIMATED_CHARS_PER_SECOND)


def _simulate_scene_windows(project) -> list[dict]:
    """Builds a scene_windows list shaped exactly like render.py's real
    output, but with ESTIMATED (not measured) per-unit timing -- see this
    module's docstring for why, and what that does and doesn't prove."""
    windows = []
    cumulative = 0.0
    for scene in project.scenes:
        units = []
        t = 0.0
        for phrase in scene.narration_plan:
            dur = _estimate_duration(phrase.text)
            units.append({"role": phrase.role, "text": phrase.text, "start": t, "end": t + dur})
            t += dur + _INTER_PHRASE_PAUSE_SECONDS
        scene_duration = max(t, 0.1)
        windows.append({"scene": scene.id, "start": cumulative, "duration": scene_duration, "narration_units": units})
        cumulative += scene_duration
    return windows


class _HonestDemoJudge:
    """Hand-authored verdicts reflecting a careful human read of THIS
    specific script -- see module docstring. Every quote is copied verbatim
    from the real (simulated) text it was given, exactly as a real judge
    would be required to."""

    def judge_violation(self, claim_text: str, violation_text: str) -> JudgeVerdict:
        if "바깥쪽 바퀴가 안쪽 바퀴보다 더 먼 거리" in violation_text:
            return JudgeVerdict(status=JUDGE_PASS, quote=violation_text)
        if "방향을 잡아주는 주된 원리는 이 돌출부가 아니라" in violation_text:
            return JudgeVerdict(status=JUDGE_PASS, quote=violation_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)

    def judge_clue_novelty(self, prior_texts: list[str], new_text: str) -> JudgeVerdict:
        if new_text and new_text not in prior_texts:
            return JudgeVerdict(status=JUDGE_PASS, quote=new_text)
        return JudgeVerdict(status=JUDGE_FAIL, quote=new_text)

    def judge_resolution(self, gap_text: str, candidate_text: str) -> JudgeVerdict:
        if "더 큰 원을 그리며 더 먼 거리를 이동" in candidate_text:
            return JudgeVerdict(status=JUDGE_PASS, quote=candidate_text)
        if "특수한 상황에서" in candidate_text and "안전장치" in candidate_text:
            return JudgeVerdict(status=JUDGE_PASS, quote=candidate_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)

    def judge_payoff_reframing(self, prior_texts: list[str], payoff_text: str) -> JudgeVerdict:
        if "조향 장치가 아니라" in payoff_text and "기울기 차이" in payoff_text:
            return JudgeVerdict(status=JUDGE_PASS, quote=payoff_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)


def _load_pilot_project():
    return load_project(MANIFEST_PATH)


def test_manifest_validates_and_declares_an_event_graph():
    project = _load_pilot_project()
    assert project.strict_entertainment_contract is False
    assert project.strict_retention_contract is False
    assert project.event_graph is not None
    assert len(project.event_graph.events) == 14
    assert len(project.event_graph.grounded_claims) == 3


def test_pec_report_only_pilot_end_to_end():
    project = _load_pilot_project()
    windows = _simulate_scene_windows(project)
    judge = _HonestDemoJudge()

    report = run_entertainment_contract_report(project, windows, judge=judge)
    assert report is not None
    assert report["mode"] == "report-only"
    assert report["strict_entertainment_contract"] is False

    # The core invariant: both curiosity loops (gap1: the rolling-radius
    # question, gap2: does the flange steer) are fulfilled by a real,
    # judge-confirmed closing event -- not by their mere declaration.
    gap_check = report["unresolved_critical_gaps"]
    assert gap_check["unresolved_critical_gap_count"] == 0, gap_check

    loops = {l["gap_id"]: l for l in report["curiosity_loops"]}
    assert loops["gap1"]["fulfilled"] is True
    # clue1, not resolution1, is the fulfilling event: it is the first
    # GAP_CLOSING_TYPES event in declaration order that the judge confirms
    # PASS (a genuinely novel clue), and compute_curiosity_loops stops at
    # the first confirmed closer -- this is the intended, approved Phase
    # 0.5 semantics (correction 1: curiosity can be satisfied progressively
    # by ANY of CLUE/REVEAL/RESOLUTION, not only by a single designated
    # RESOLUTION), not an accident of this script.
    assert loops["gap1"]["fulfilling_event_id"] == "clue1"
    assert loops["gap2"]["fulfilled"] is True
    assert loops["gap2"]["fulfilling_event_id"] == "resolution2"

    # Every declared event resolved to real (simulated) narration -- i.e.
    # no event silently fell back to declared-only (see Phase 0's
    # hook_type-no-op precedent this whole contract exists to prevent).
    evidence = report["observed_evidence"]
    assert all(ev["observed"] for ev in evidence.values()), {
        eid: ev for eid, ev in evidence.items() if not ev["observed"]
    }

    # The two VIOLATION events both genuinely contradict their grounded
    # claim, per the honest judge.
    assert evidence["violation1"]["judge_verdict"] == JUDGE_PASS
    assert evidence["violation2"]["judge_verdict"] == JUDGE_PASS

    # The PAYOFF genuinely reframes rather than repeats.
    assert evidence["payoff1"]["judge_verdict"] == JUDGE_PASS

    diagnostics = report["diagnostics"]
    assert diagnostics["event_count"] == 14
    assert diagnostics["critical_gap_count"] == 2
    assert diagnostics["fulfilled_gap_count"] == 2


def test_seed_and_relay_are_declared_but_not_gap_closing():
    """SEED (a CLAIM planting the flange visually/narratively) and RELAY
    (the natural pivot back to it) are deliberately NOT GAP_CLOSING_TYPES --
    they exist to make gap2 feel earned rather than dropped in as padding
    (the Phase 0 critique of "바퀴가 따로 도는 걸까요?"), but they do not
    themselves resolve anything, and are not required to for the contract
    to pass."""
    project = _load_pilot_project()
    graph = project.event_graph
    seed = next(e for e in graph.events if e.id == "seed_flange")
    relay = next(e for e in graph.events if e.id == "relay1")
    assert seed.type == "CLAIM"
    assert relay.type == "RELAY"
    assert seed.resolves is None
    assert relay.resolves is None


def test_no_event_claims_rolling_radius_is_the_sole_explanation():
    """Fact guardrail: the payoff must not claim the rolling-radius
    difference is the ONLY mechanism -- it must acknowledge other real
    factors (creep, suspension) exist, per Phase 2 section 7's guardrails."""
    project = _load_pilot_project()
    payoff_scene = next(s for s in project.scenes if s.id == "s_payoff")
    full_text = " ".join(p.text for p in payoff_scene.narration_plan)
    assert "크리프" in full_text or "서스펜션" in full_text
    assert "유일" not in full_text and "오직" not in full_text


def test_no_event_claims_a_perfect_cone():
    project = _load_pilot_project()
    for scene in project.scenes:
        for phrase in scene.narration_plan:
            assert "완벽한 원뿔" not in phrase.text
    clue1 = next(s for s in project.scenes if s.id == "s_clue1")
    assert "완만하게" in clue1.narration_plan[0].text
