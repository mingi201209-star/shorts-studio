"""Psychological Entertainment Contract (Layer 2), Phase 2.

16 adversarial fixtures on top of Phase 1's 10 (kept, unmodified, in
tests/test_entertainment_contract.py). These prove the Phase 2 additions --
a real SemanticJudge implementation's fail-closed safety net, hardened
Observed Narration/Visual Evidence, and explicit declared/observed/semantic
status separation -- actually hold under adversarial input, not just in the
happy path.
"""
import time

import pytest

from shorts_studio.models import Project, Scene, VisualBeat, GroundedClaim, CognitiveEvent, DeclaredEventGraph
from shorts_studio.entertainment_rules import (
    JUDGE_FAIL, JUDGE_NOT_EVALUATED, JUDGE_PASS,
    MISMATCH_CLUE_NO_NEW_INFORMATION, MISMATCH_NO_TIMING_EVIDENCE, MISMATCH_PAYOFF_MERE_REPETITION,
    MISMATCH_TEXT_DIVERGES_FROM_NARRATION, MISMATCH_VIOLATION_NO_CONTRADICTION, MISMATCH_VISUAL_BEAT_MISSING,
)
from shorts_studio.entertainment_qa import (
    AnthropicJudge, JudgeVerdict, NullJudge, _call_judge_safely, _dispatch,
    build_observed_evidence, compute_curiosity_loops, evaluate_overclaim,
    verify_unresolved_critical_gaps,
)
import shorts_studio.entertainment_qa as eqa


# ---------------------------------------------------------------------------
# Shared helpers (mirrors tests/test_entertainment_contract.py's fixtures)
# ---------------------------------------------------------------------------

def _scene(sid, fact=None, visual_beats=None):
    return Scene(id=sid, narration="x", visual_description="d",
                 factual_notes=[fact] if fact else [], visual_beats=visual_beats or [])


def _claim(cid, text, source_ref):
    return GroundedClaim(id=cid, text=text, source_ref=source_ref)


def _event(eid, etype, scene_id, text, *, critical=True, unit_index=None, beat_index=None,
           resolves=None, refs=None, info_role=None):
    return CognitiveEvent(id=eid, type=etype, critical=critical, scene_id=scene_id,
                           narration_unit_index=unit_index, visual_beat_index=beat_index,
                           text=text, resolves=resolves, grounded_claim_refs=refs or [], info_role=info_role)


GAP_CLAIM = _claim("cg", "배경 사실 주장", "출처")


def _gap(eid, scene_id, text, *, critical=True, unit_index=None):
    return _event(eid, "GAP", scene_id, text, critical=critical, unit_index=unit_index, refs=[GAP_CLAIM.id])


def _window(scene_id, start, units):
    return {"scene": scene_id, "start": start,
            "narration_units": [{"role": r, "text": t, "start": s, "end": e} for (r, t, s, e) in units]}


class ScriptedJudge:
    """Same test double as Phase 1's, extended with the two Phase 2 methods
    (judge_overclaim, judge_grounding_consistency)."""
    def __init__(self, violation=None, clue_novelty=None, resolution=None, payoff=None,
                 overclaim=None, grounding_consistency=None):
        self._violation = violation
        self._clue_novelty = clue_novelty
        self._resolution = resolution
        self._payoff = payoff
        self._overclaim = overclaim
        self._grounding_consistency = grounding_consistency

    def judge_violation(self, claim_text, violation_text):
        return self._violation(claim_text, violation_text) if self._violation else JudgeVerdict(status=JUDGE_NOT_EVALUATED)
    def judge_clue_novelty(self, prior_texts, new_text):
        return self._clue_novelty(prior_texts, new_text) if self._clue_novelty else JudgeVerdict(status=JUDGE_NOT_EVALUATED)
    def judge_resolution(self, gap_text, candidate_text):
        return self._resolution(gap_text, candidate_text) if self._resolution else JudgeVerdict(status=JUDGE_NOT_EVALUATED)
    def judge_payoff_reframing(self, prior_texts, payoff_text):
        return self._payoff(prior_texts, payoff_text) if self._payoff else JudgeVerdict(status=JUDGE_NOT_EVALUATED)
    def judge_overclaim(self, hook_text, evidence_text):
        return self._overclaim(hook_text, evidence_text) if self._overclaim else JudgeVerdict(status=JUDGE_NOT_EVALUATED)
    def judge_grounding_consistency(self, claim_text, tension_text):
        return self._grounding_consistency(claim_text, tension_text) if self._grounding_consistency else JudgeVerdict(status=JUDGE_NOT_EVALUATED)


# ===========================================================================
# 1. Judge PASS but no quote -> NOT_EVALUATED
# ===========================================================================
def test_01_pass_with_no_quote_downgraded_to_not_evaluated():
    gap = _gap("gap1", "s1", "어떻게 될까요?", unit_index=0)
    res = _event("res1", "RESOLUTION", "s2", "이렇게 됩니다", resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, res], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]), _window("s2", 5.0, [("RESOLUTION", res.text, 0.0, 1.0)])]
    judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(status=JUDGE_PASS, quote=None))
    evidence = build_observed_evidence(graph, windows, judge)
    assert evidence["res1"].semantic_status == JUDGE_NOT_EVALUATED


# ===========================================================================
# 2. Fabricated quote (not a substring of any real text given to the judge)
# ===========================================================================
def test_02_fabricated_quote_downgraded_to_not_evaluated():
    gap = _gap("gap1", "s1", "어떻게 될까요?", unit_index=0)
    res = _event("res1", "RESOLUTION", "s2", "이렇게 됩니다", resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, res], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]), _window("s2", 5.0, [("RESOLUTION", res.text, 0.0, 1.0)])]
    judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(status=JUDGE_PASS, quote="이 문장은 실제 입력에 전혀 없습니다"))
    evidence = build_observed_evidence(graph, windows, judge)
    assert evidence["res1"].semantic_status == JUDGE_NOT_EVALUATED
    assert "fabricated" in (evidence["res1"].semantic_reason or "")


# ===========================================================================
# 3. Quote cites a compared_event_id that does not exist in the graph
# ===========================================================================
def test_03_quote_citing_nonexistent_event_id_downgraded_to_not_evaluated():
    gap = _gap("gap1", "s1", "어떻게 될까요?", unit_index=0)
    res = _event("res1", "RESOLUTION", "s2", "이렇게 됩니다", resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, res], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]), _window("s2", 5.0, [("RESOLUTION", res.text, 0.0, 1.0)])]
    judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(
        status=JUDGE_PASS, quote=c, compared_event_ids=["ghost_event_that_does_not_exist"]))
    evidence = build_observed_evidence(graph, windows, judge)
    assert evidence["res1"].semantic_status == JUDGE_NOT_EVALUATED
    assert "nonexistent" in (evidence["res1"].semantic_reason or "")


# ===========================================================================
# 4. Malformed judge JSON (AnthropicJudge's own response parsing)
# ===========================================================================
def test_04_malformed_judge_json_is_not_evaluated(monkeypatch):
    monkeypatch.setattr(eqa, "_call_anthropic_messages", lambda client, system, user, timeout=None: "not valid json { at all")
    judge = AnthropicJudge(client=object())
    verdict = judge.judge_resolution("GAP 텍스트", "후보 텍스트")
    assert verdict.status == JUDGE_NOT_EVALUATED
    assert "JSON" in (verdict.reason or "")


def test_04b_json_missing_status_field_is_not_evaluated(monkeypatch):
    monkeypatch.setattr(eqa, "_call_anthropic_messages", lambda client, system, user, timeout=None: '{"quote": "x"}')
    judge = AnthropicJudge(client=object())
    verdict = judge.judge_resolution("GAP", "text")
    assert verdict.status == JUDGE_NOT_EVALUATED


# ===========================================================================
# 5. Judge timeout -> NOT_EVALUATED, never blocks
# ===========================================================================
def test_05_judge_timeout_is_not_evaluated():
    def slow_judge(*args):
        time.sleep(2.0)
        return JudgeVerdict(status=JUDGE_PASS, quote="too late")
    verdict = _call_judge_safely(slow_judge, "a", "b", timeout_seconds=0.05)
    assert verdict.status == JUDGE_NOT_EVALUATED
    assert "timeout" in (verdict.reason or "").lower() or "timed out" in (verdict.reason or "").lower()


# ===========================================================================
# 6. Judge exception -> NOT_EVALUATED, never propagates
# ===========================================================================
def test_06_judge_exception_is_not_evaluated():
    def broken_judge(*args):
        raise RuntimeError("boom")
    verdict = _call_judge_safely(broken_judge, "a", "b")
    assert verdict.status == JUDGE_NOT_EVALUATED
    assert "RuntimeError" in (verdict.reason or "")


def test_06b_dispatch_on_judge_missing_the_method_is_not_evaluated():
    class IncompleteJudge:
        pass
    verdict = _dispatch(IncompleteJudge(), "judge_overclaim", "a", "b")
    assert verdict.status == JUDGE_NOT_EVALUATED
    assert "does not implement" in (verdict.reason or "")


# ===========================================================================
# 7. Declared event text differs grossly from the actual narration
# ===========================================================================
def test_07_declared_text_diverges_from_actual_narration_flagged_as_mismatch():
    payoff = _event("p1", "PAYOFF", "s1", "반지름 차이가 곡선 주행을 가능하게 합니다", unit_index=0)
    graph = DeclaredEventGraph(events=[payoff], grounded_claims=[])
    # Real synthesized narration is a COMPLETELY unrelated sentence -- as if
    # the manifest's narration_unit_index pointed at the wrong scene/unit.
    windows = [_window("s1", 0.0, [("PAYOFF", "오늘 날씨가 정말 좋네요", 0.0, 1.5)])]
    evidence = build_observed_evidence(graph, windows, NullJudge())
    ev = evidence["p1"]
    assert ev.observed is True  # it DID resolve to a real unit...
    assert MISMATCH_TEXT_DIVERGES_FROM_NARRATION in ev.mismatches  # ...but it's not the same sentence
    # And per section 3's explicit fixture: a declared PAYOFF whose real
    # narration is unrelated must never reach a PASS/semantic confirmation.
    assert ev.semantic_status in (JUDGE_NOT_EVALUATED, JUDGE_FAIL)


# ===========================================================================
# 8. Nonexistent narration_unit_index
# ===========================================================================
def test_08_nonexistent_narration_unit_index_is_not_observed():
    e = _event("e1", "CLAIM", "s1", "설명입니다", unit_index=7)
    graph = DeclaredEventGraph(events=[e], grounded_claims=[])
    windows = [_window("s1", 0.0, [("EXPLANATION", "실제 문장", 0.0, 1.0)])]  # only index 0 exists
    evidence = build_observed_evidence(graph, windows, NullJudge())
    assert evidence["e1"].observed is False
    assert evidence["e1"].observed_status == "NOT_OBSERVED"
    assert MISMATCH_NO_TIMING_EVIDENCE in evidence["e1"].mismatches


# ===========================================================================
# 9. Nonexistent visual_beat_index
# ===========================================================================
def test_09_nonexistent_visual_beat_index_flagged_as_mismatch():
    scene = _scene("s1", visual_beats=[VisualBeat(start=0, asset="a.jpg")])  # only index 0 exists
    e = _event("e1", "REVEAL", "s1", "화면이 바뀝니다", unit_index=0, beat_index=3)
    graph = DeclaredEventGraph(events=[e], grounded_claims=[])
    windows = [_window("s1", 0.0, [("REVEAL", e.text, 0.0, 1.0)])]
    evidence = build_observed_evidence(graph, windows, NullJudge(), scenes_by_id={"s1": scene})
    ev = evidence["e1"]
    assert ev.visual_beat_declared is True
    assert ev.visual_beat_observed is False
    assert MISMATCH_VISUAL_BEAT_MISSING in ev.mismatches


# ===========================================================================
# 10. Real visual cut exists near the declared beat, but the scene's own
#     existing semantic visual QA already found the WRONG content there --
#     "a cut happened" must not be conflated with "the cognitive event was
#     implemented" (section 4's explicit warning).
# ===========================================================================
def test_10_real_cut_present_but_wrong_semantic_content_is_not_conflated_with_success():
    scene = _scene("s1", visual_beats=[VisualBeat(start=0, asset="a.jpg"), VisualBeat(start=3.0, asset="b.jpg")])
    e = _event("e1", "REVEAL", "s1", "새로운 장면이 드러납니다", unit_index=0, beat_index=1)
    graph = DeclaredEventGraph(events=[e], grounded_claims=[])
    windows = [_window("s1", 0.0, [("REVEAL", e.text, 3.0, 4.5)])]
    # A real cut WAS measured right at the expected time...
    cuts = [3.1]
    # ...but this scene's existing (reused, not recomputed) semantic visual
    # QA result already says the wrong thing is on screen.
    semantic_results = [{"scene": "s1", "status": "FAIL"}]
    evidence = build_observed_evidence(graph, windows, NullJudge(), visual_cut_timestamps=cuts,
                                        scenes_by_id={"s1": scene}, semantic_visual_results=semantic_results)
    ev = evidence["e1"]
    assert ev.visual_beat_observed is True
    assert ev.real_visual_cut_matches_beat is True  # the cut is real...
    assert ev.visual_semantic_status == "FAIL"  # ...but the content shown there is wrong
    # Neither of these two facts, individually or combined, is a semantic
    # PASS for the event -- semantic_status is a SEPARATE field, and with
    # NullJudge it stays NOT_EVALUATED regardless of visual evidence.
    assert ev.semantic_status == JUDGE_NOT_EVALUATED


# ===========================================================================
# 11. GAP answered with HIGH lexical overlap but the judge says it doesn't
#     really answer the question (fulfillment is never lexical).
# ===========================================================================
def test_11_lexically_similar_but_semantically_unanswered_gap_stays_unresolved():
    gap = _gap("gap1", "s1", "바깥쪽 바퀴는 왜 더 멀리 갈까요?", unit_index=0)
    res = _event("res1", "RESOLUTION", "s2", "바깥쪽 바퀴는 확실히 더 멀리 갑니다", resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, res], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.5)]), _window("s2", 5.0, [("RESOLUTION", res.text, 0.0, 1.5)])]
    judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(status=JUDGE_FAIL, quote=c))
    evidence = build_observed_evidence(graph, windows, judge)
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["unresolved_critical_gap_count"] == 1


# ===========================================================================
# 12. GAP answered with DIFFERENT vocabulary (low lexical overlap) but the
#     judge correctly confirms it as a real answer -- low overlap must not
#     be penalized either (fulfillment is never lexical, in EITHER direction).
# ===========================================================================
def test_12_low_overlap_but_semantically_correct_resolution_fulfills_gap():
    gap = _gap("gap1", "s1", "왜 커브를 돌 수 있을까요?", unit_index=0)
    res = _event("res1", "RESOLUTION", "s2", "굴러가는 원의 크기가 양쪽에서 달라지기 때문입니다",
                 resolves="gap1", unit_index=0)
    from shorts_studio.retention_rules import token_overlap_ratio
    assert token_overlap_ratio(gap.text, res.text) < 0.2
    graph = DeclaredEventGraph(events=[gap, res], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.5)]), _window("s2", 5.0, [("RESOLUTION", res.text, 0.0, 1.5)])]
    judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(status=JUDGE_PASS, quote=c))
    evidence = build_observed_evidence(graph, windows, judge)
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["unresolved_critical_gap_count"] == 0
    assert loops[0].fulfilled is True


# ===========================================================================
# 13. PAYOFF paraphrases the previous REVEAL without reframing it
# ===========================================================================
def test_13_payoff_paraphrase_without_reframing_flagged_as_mismatch():
    reveal = _event("reveal1", "REVEAL", "s1", "반지름이 다르면 이동거리가 다릅니다", unit_index=0)
    payoff = _event("payoff1", "PAYOFF", "s2", "그러니까 반지름 차이 때문에 이동 거리가 달라지는 거죠", unit_index=0)
    graph = DeclaredEventGraph(events=[reveal, payoff], grounded_claims=[])
    windows = [_window("s1", 0.0, [("REVEAL", reveal.text, 0.0, 2.0)]), _window("s2", 10.0, [("PAYOFF", payoff.text, 0.0, 2.0)])]
    judge = ScriptedJudge(payoff=lambda prior, text: JudgeVerdict(status=JUDGE_FAIL, quote=text, reason="paraphrase, not reframing"))
    evidence = build_observed_evidence(graph, windows, judge)
    ev = evidence["payoff1"]
    assert ev.semantic_status == JUDGE_FAIL
    assert MISMATCH_PAYOFF_MERE_REPETITION in ev.mismatches


# ===========================================================================
# 14. A REAL reframing with LOW lexical overlap must be recognized as a
#     genuine payoff, not penalized for not sharing the reveal's words.
# ===========================================================================
def test_14_real_reframing_with_low_overlap_is_recognized():
    reveal = _event("reveal1", "REVEAL", "s1", "양쪽 바퀴의 회전 반경이 다릅니다", unit_index=0)
    payoff = _event("payoff1", "PAYOFF", "s2", "결국 기차는 스스로 방향을 잡는 셈입니다", unit_index=0)
    from shorts_studio.retention_rules import token_overlap_ratio
    assert token_overlap_ratio(reveal.text, payoff.text) < 0.2
    graph = DeclaredEventGraph(events=[reveal, payoff], grounded_claims=[])
    windows = [_window("s1", 0.0, [("REVEAL", reveal.text, 0.0, 2.0)]), _window("s2", 10.0, [("PAYOFF", payoff.text, 0.0, 2.0)])]
    judge = ScriptedJudge(payoff=lambda prior, text: JudgeVerdict(status=JUDGE_PASS, quote=text, reason="genuine synthesis"))
    evidence = build_observed_evidence(graph, windows, judge)
    ev = evidence["payoff1"]
    assert ev.semantic_status == JUDGE_PASS
    assert MISMATCH_PAYOFF_MERE_REPETITION not in ev.mismatches


# ===========================================================================
# 15. Fake contradiction: dramatic-sounding VIOLATION text that the judge
#     determines does not actually contradict its grounded claim.
# ===========================================================================
def test_15_fake_contradiction_flagged_as_mismatch():
    claim = _claim("c1", "기차 바퀴는 축에 고정돼 있다", "두 바퀴는 하나의 축에 고정돼 있습니다")
    violation = _event("v1", "VIOLATION", "s1", "충격적이게도 이 기차는 위험할 수 있습니다", unit_index=0, refs=["c1"])
    graph = DeclaredEventGraph(events=[violation], grounded_claims=[claim])
    windows = [_window("s1", 0.0, [("HOOK", violation.text, 0.0, 1.5)])]
    judge = ScriptedJudge(violation=lambda c, v: JudgeVerdict(status=JUDGE_FAIL, quote=v, reason="dramatic wording, no real contradiction of the claim"))
    evidence = build_observed_evidence(graph, windows, judge)
    ev = evidence["v1"]
    assert ev.semantic_status == JUDGE_FAIL
    assert MISMATCH_VIOLATION_NO_CONTRADICTION in ev.mismatches


# ===========================================================================
# 16. Grounded premise distorted into a sensational hook: violation_integrity
#     and grounding_consistency are SEPARATE assertions -- a VIOLATION can
#     look like a real contradiction (integrity PASS) while still distorting
#     its own factual premise (grounding_consistency FAIL).
# ===========================================================================
def test_16_grounding_distortion_is_a_separate_failure_from_violation_integrity():
    claim = _claim("c1", "바퀴 답면은 원뿔 형태로 설계되어 있다", "바퀴 답면은 완만한 원뿔 형태입니다")
    violation = _event("v1", "VIOLATION", "s1", "사실 바퀴는 완벽한 원뿔이라 절대 미끄러지지 않습니다",
                        unit_index=0, refs=["c1"])
    graph = DeclaredEventGraph(events=[violation], grounded_claims=[claim])
    windows = [_window("s1", 0.0, [("HOOK", violation.text, 0.0, 1.5)])]
    judge = ScriptedJudge(
        violation=lambda c, v: JudgeVerdict(status=JUDGE_PASS, quote=v, reason="does complicate the mental model"),
        grounding_consistency=lambda c, v: JudgeVerdict(
            status=JUDGE_FAIL, quote=v, reason="claim says 'gentle cone shape', violation overclaims 'perfect cone, never slips'"),
    )
    evidence = build_observed_evidence(graph, windows, judge)
    ev = evidence["v1"]
    assert ev.semantic_status == JUDGE_PASS  # integrity: yes, it IS a contradiction/complication
    assert ev.grounding_consistency_verdict == JUDGE_FAIL  # but it distorts its own premise
    assert MISMATCH_VIOLATION_NO_CONTRADICTION not in ev.mismatches  # these are independent codes


# ===========================================================================
# Bonus: OVERCLAIM (assertion E) -- project-level, not per-event.
# ===========================================================================
def test_overclaim_flagged_when_hook_promises_more_than_delivered_evidence():
    gap = _gap("gap1", "s1", "정말로 기차가 스스로 방향을 아는 걸까요?", unit_index=0)
    res = _event("res1", "RESOLUTION", "s2", "반지름 차이 덕분에 일부 상황에서 방향이 맞춰집니다",
                 resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, res], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.5)]), _window("s2", 5.0, [("RESOLUTION", res.text, 0.0, 1.5)])]
    judge = ScriptedJudge(
        resolution=lambda g, c: JudgeVerdict(status=JUDGE_PASS, quote=c),
        overclaim=lambda hook, evi: JudgeVerdict(status=JUDGE_FAIL, quote=hook, reason="hook claims full autonomy; evidence only covers a partial/conditional effect"),
    )
    project = Project(title="기차는 스스로 방향을 안다?!",
                      scenes=[_scene("s1", fact="출처"), _scene("s2")], event_graph=graph)
    evidence = build_observed_evidence(graph, windows, judge)
    result = evaluate_overclaim(project, graph, evidence, judge)
    assert result["status"] == JUDGE_FAIL


def test_overclaim_not_evaluated_when_no_delivered_evidence_yet():
    gap = _gap("gap1", "s1", "질문입니다", unit_index=0)
    graph = DeclaredEventGraph(events=[gap], grounded_claims=[GAP_CLAIM])
    project = Project(title="제목", scenes=[_scene("s1", fact="출처")], event_graph=graph)
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)])]
    evidence = build_observed_evidence(graph, windows, NullJudge())
    result = evaluate_overclaim(project, graph, evidence, NullJudge())
    assert result["status"] == JUDGE_NOT_EVALUATED
