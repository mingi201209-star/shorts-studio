"""Train Wheels V2 -- Psychological Entertainment Contract report-only pilot.

Phase 2.6 revision: content-quality recovery after Phase 2.5's real-render
manual review found real defects (a Japanese-labeled recycled asset, weak
visual-narrative correspondence, a false "this has been on screen the whole
time" SEED claim, redundant flange-subplot phrasing, and an inflated
runtime). This manifest replaces every recycled generic diagram with 11
purpose-built local illustrations (examples/../assets/train_wheels_v2/),
merges the RELAY event into GAP2 (both were voicing the same question back
to back), rewrites the SEED line to introduce the flange honestly instead
of claiming false continuity, and compresses narration throughout --
187 fewer characters than the Phase 2.5 script, purely from cutting filler
and repetition (see the Phase 2.6 report for the full before/after).

Still separate from PR #24 (content/train-wheel-conicity) and, per
instruction, still self-contained against Phase 1's entertainment_qa as
already merged on main -- this test does not require PR #27 to run.

IMPORTANT SCOPE NOTE: this test does not render anything and does not call
real TTS. scene_windows below is built by _simulate_scene_windows(), which
estimates each narration_plan phrase's duration from a Korean reading-rate
CALIBRATED against Phase 2.5's real render (7.17 chars/sec, measured
directly from that render's per-unit timing.json files) -- still an
estimate, not a real measurement, but a materially better-grounded one
than Phase 2.5's first-guess rate.

The judge used here (_HonestDemoJudge) is a hand-authored test double
reflecting a careful human read of THIS specific script -- not a real
model call (see PR #27's AnthropicJudge for that).
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

# Calibrated directly from Phase 2.5's real render (845 real chars / 117.85s
# of real per-unit audio across all 15 scenes) -- see module docstring.
_ESTIMATED_CHARS_PER_SECOND = 7.17
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
        if "방향을 잡아주는 주된 원리는 플랜지가 아니라" in violation_text:
            return JudgeVerdict(status=JUDGE_PASS, quote=violation_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)

    def judge_clue_novelty(self, prior_texts: list[str], new_text: str) -> JudgeVerdict:
        if new_text and new_text not in prior_texts:
            return JudgeVerdict(status=JUDGE_PASS, quote=new_text)
        return JudgeVerdict(status=JUDGE_FAIL, quote=new_text)

    def judge_resolution(self, gap_text: str, candidate_text: str) -> JudgeVerdict:
        if "더 큰 원을 그려 더 먼 거리를 이동" in candidate_text:
            return JudgeVerdict(status=JUDGE_PASS, quote=candidate_text)
        if "궤도를 크게 벗어나려 할 때만" in candidate_text and "안전장치" in candidate_text:
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
    assert len(project.scenes) == 14
    # RELAY was merged into GAP2 (Phase 2.6 section 6: they were voicing the
    # same "does the flange steer?" question back to back) -- 13 events, not 14.
    assert len(project.event_graph.events) == 13
    assert len(project.event_graph.grounded_claims) == 3
    assert not any(e.type == "RELAY" for e in project.event_graph.events)


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
    # clue1, not resolution1, is the fulfilling event -- same intended,
    # approved Phase 0.5 semantics as Phase 2.5's pilot (curiosity can be
    # satisfied progressively by ANY of CLUE/REVEAL/RESOLUTION).
    assert loops["gap1"]["fulfilling_event_id"] == "clue1"
    assert loops["gap2"]["fulfilled"] is True
    # gap2 now has exactly one possible closing event (resolution2) -- RELAY
    # is gone and there is no separate CLUE for this sub-loop.
    assert loops["gap2"]["fulfilling_event_id"] == "resolution2"
    assert loops["gap2"]["clue_ids"] == ["resolution2"]

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
    assert diagnostics["event_count"] == 13
    assert diagnostics["critical_gap_count"] == 2
    assert diagnostics["fulfilled_gap_count"] == 2


def test_seed_flange_does_not_claim_prior_visibility():
    """Phase 2.5's manual review found the old SEED line ("이 튀어나온
    부분은 계속 화면에 보였습니다") false: no earlier diagram actually,
    consistently showed a recognizable flange. Fixed per Phase 2.6 section
    4's option B: rewritten as an honest, fresh introduction -- no earlier
    diagram was retrofitted with a contrived flange cameo just to make the
    old claim technically true."""
    project = _load_pilot_project()
    seed = next(s for s in project.scenes if s.id == "s_seed_flange")
    text = seed.narration_plan[0].text
    assert "계속" not in text and "지금까지" not in text and "등장하지 않았습니다" not in text
    assert "튀어나온 부분" in text


def test_flange_relay_and_gap_are_a_single_non_redundant_question():
    """The old RELAY ("혹시...방향을 잡아주는 걸까요?") and GAP2 ("그렇다면
    ...조향을 담당하는 부품일까요?") asked the same question twice in a
    row. Merged into gap2 alone."""
    project = _load_pilot_project()
    graph = project.event_graph
    assert not any(e.id == "relay1" for e in graph.events)
    gap2 = next(e for e in graph.events if e.id == "gap2")
    assert gap2.type == "GAP"
    scene = next(s for s in project.scenes if s.id == gap2.scene_id)
    assert len(scene.narration_plan) == 1


def test_no_event_claims_rolling_radius_is_the_sole_explanation():
    """Fact guardrail: the payoff must not claim the rolling-radius
    difference is the ONLY mechanism -- it must acknowledge other real
    factors (creep, suspension) exist, per Phase 2 section 7's guardrails."""
    project = _load_pilot_project()
    payoff_scenes = [s for s in project.scenes if s.id in ("s_payoff1", "s_payoff2")]
    full_text = " ".join(p.text for s in payoff_scenes for p in s.narration_plan)
    assert "크리프" in full_text or "서스펜션" in full_text
    assert "유일" not in full_text and "오직" not in full_text


def test_no_event_claims_a_perfect_cone():
    project = _load_pilot_project()
    for scene in project.scenes:
        for phrase in scene.narration_plan:
            assert "완벽한 원뿔" not in phrase.text
    clue1 = next(s for s in project.scenes if s.id == "s_clue1")
    assert "완만하게" in clue1.narration_plan[0].text


def test_flange_contact_is_stated_as_conditional_not_default():
    """Fact guardrail: resolution2 must frame flange-rail contact as a
    limit-case/conditional event, never as normal-running behavior."""
    project = _load_pilot_project()
    res2 = next(s for s in project.scenes if s.id == "s_resolution2")
    text = res2.narration_plan[0].text
    assert "할 때만" in text or "만 레일에 닿" in text


def test_no_recycled_japanese_labeled_asset_referenced():
    """The Phase 2.5 defect: one recycled asset ("%E8%B8%8F%E9%9D%A2%E5%8B%BE%E9%85%8D.png",
    Japanese-labeled) must not appear anywhere in the manifest -- every
    asset is now a local, purpose-built diagram under assets/train_wheels_v2/."""
    project = _load_pilot_project()
    for scene in project.scenes:
        assert scene.asset_url is None, f"{scene.id} still references a remote asset_url"
        for beat in scene.visual_beats:
            assert beat.asset is not None and beat.asset.startswith("assets/train_wheels_v2/")
            assert "%E8%B8%8F" not in (beat.asset_url or "")


def test_every_scene_has_visual_beats_with_no_adjacent_duplicate_asset():
    """verify_visual_cut_cadence (final_video_qa.py) fails closed on any
    scene with zero visual_beats, and Phase 2.5's real render proved
    adjacent identical assets (within OR across scene boundaries) produce
    real measured static holds -- both must hold for every scene now."""
    project = _load_pilot_project()
    prev_asset = None
    for scene in project.scenes:
        assert scene.visual_beats, f"{scene.id} has no visual_beats"
        assert scene.visual_beats[0].start == 0
        for beat in scene.visual_beats:
            assert beat.asset != prev_asset
            prev_asset = beat.asset
