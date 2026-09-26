"""Psychological Entertainment Contract (Layer 2), Phase 1.

Ten adversarial fixtures, each proving this layer actually closes one of
the Goodhart gaps Phase 0 demonstrated against the real Layer-1 retention
contract functions (see final_video_qa.py's retention-engine section
header and the Phase 0 report). Core invariant under test throughout:
declared metadata alone can never prove entertainment success -- an event
only counts once Observed Evidence confirms it against real render data
AND (for gap-closing types) a SemanticJudge, never a lexical-overlap
heuristic, confirms its text actually does what it claims.
"""
import pytest
from pydantic import ValidationError

from shorts_studio.models import Project, Scene, GroundedClaim, CognitiveEvent, DeclaredEventGraph
from shorts_studio.entertainment_rules import JUDGE_FAIL, JUDGE_NOT_EVALUATED, JUDGE_PASS
from shorts_studio.entertainment_qa import (
    JudgeVerdict, NullJudge, build_observed_evidence, compute_curiosity_loops,
    verify_unresolved_critical_gaps, compute_entertainment_diagnostics,
    run_entertainment_contract_report,
)
from shorts_studio.retention_rules import token_overlap_ratio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _scene(sid, fact=None):
    return Scene(id=sid, narration="x", visual_description="d", factual_notes=[fact] if fact else [])


def _claim(cid, text, source_ref):
    return GroundedClaim(id=cid, text=text, source_ref=source_ref)


def _event(eid, etype, scene_id, text, *, critical=True, unit_index=None, resolves=None, refs=None, info_role=None):
    return CognitiveEvent(id=eid, type=etype, critical=critical, scene_id=scene_id,
                           narration_unit_index=unit_index, text=text, resolves=resolves,
                           grounded_claim_refs=refs or [], info_role=info_role)


# GAP and VIOLATION both require grounded_claim_refs (entertainment_rules.
# REQUIRES_GROUNDING). Fixtures below that are about GAP-closing behavior,
# not about grounding itself, use this shared claim so every GAP-typed
# _event(...) call can just pass refs=[GAP_CLAIM.id].
GAP_CLAIM = _claim("cg", "배경 사실 주장", "출처")


def _gap(eid, scene_id, text, *, critical=True, unit_index=None):
    return _event(eid, "GAP", scene_id, text, critical=critical, unit_index=unit_index, refs=[GAP_CLAIM.id])


def _window(scene_id, start, units):
    """units: list of (role, text, start, end) -- matches render.py's real
    scene_windows[i]["narration_units"] shape (see tts.py's unit_spans)."""
    return {"scene": scene_id, "start": start,
            "narration_units": [{"role": r, "text": t, "start": s, "end": e} for (r, t, s, e) in units]}


class ScriptedJudge:
    """Test double standing in for a real semantic judge (none is wired up
    in Phase 1 -- see entertainment_qa.py's module docstring). Each method
    defaults to NOT_EVALUATED (the safe default) unless a callable is
    supplied."""
    def __init__(self, violation=None, clue_novelty=None, resolution=None, payoff=None):
        self._violation = violation
        self._clue_novelty = clue_novelty
        self._resolution = resolution
        self._payoff = payoff

    def judge_violation(self, claim_text, violation_text):
        if self._violation:
            return self._violation(claim_text, violation_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)

    def judge_clue_novelty(self, prior_texts, new_text):
        if self._clue_novelty:
            return self._clue_novelty(prior_texts, new_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)

    def judge_resolution(self, gap_text, candidate_text):
        if self._resolution:
            return self._resolution(gap_text, candidate_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)

    def judge_payoff_reframing(self, prior_texts, payoff_text):
        if self._payoff:
            return self._payoff(prior_texts, payoff_text)
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)


class AlwaysPass:
    def judge_violation(self, c, v): return JudgeVerdict(status=JUDGE_PASS, quote=v)
    def judge_clue_novelty(self, p, n): return JudgeVerdict(status=JUDGE_PASS, quote=n)
    def judge_resolution(self, g, c): return JudgeVerdict(status=JUDGE_PASS, quote=c)
    def judge_payoff_reframing(self, p, x): return JudgeVerdict(status=JUDGE_PASS, quote=x)


# ---------------------------------------------------------------------------
# 1. Fake PAYOFF label: a PAYOFF event whose real text just restates an
#    earlier REVEAL. Layer 1's equivalent (role="PAYOFF" on a flat sentence)
#    silently PASSed (Phase 0 adversarial #1). Layer 2 must not.
# ---------------------------------------------------------------------------
def test_fake_payoff_is_flagged_by_judge():
    reveal = _event("reveal1", "REVEAL", "s1", "반지름이 다르면 이동거리가 다릅니다", unit_index=0)
    payoff = _event("payoff1", "PAYOFF", "s2", "반지름이 다르면 이동거리가 다릅니다", unit_index=0)
    graph = DeclaredEventGraph(events=[reveal, payoff], grounded_claims=[])
    windows = [
        _window("s1", 0.0, [("REVEAL", reveal.text, 0.0, 2.0)]),
        _window("s2", 10.0, [("PAYOFF", payoff.text, 0.0, 2.0)]),
    ]
    judge = ScriptedJudge(payoff=lambda prior, text: JudgeVerdict(
        status=JUDGE_FAIL if text in prior else JUDGE_PASS, quote=text))
    evidence = build_observed_evidence(graph, windows, judge)
    assert evidence["payoff1"].observed is True
    assert evidence["payoff1"].judge_verdict == JUDGE_FAIL, "a payoff that just restates an earlier reveal must be flagged, not silently accepted"


# ---------------------------------------------------------------------------
# 2. Fake info_role novelty: two CLUEs with DIFFERENT info_role labels but
#    IDENTICAL real narration text. Layer 1's info_role check only compares
#    the label strings (Phase 0 adversarial #2) and PASSed. Layer 2's judge
#    is fed the real linked text, not the label, and must catch it.
# ---------------------------------------------------------------------------
def test_fake_info_role_novelty_is_flagged_by_judge():
    gap = _gap("gap1", "s1", "어떻게 가능할까요?", unit_index=0)
    clue1 = _event("clue1", "CLUE", "s2", "바깥쪽 바퀴가 더 큰 반지름으로 굴러갑니다",
                    resolves="gap1", unit_index=0, info_role="radius_diff_v1")
    clue2 = _event("clue2", "CLUE", "s3", "바깥쪽 바퀴가 더 큰 반지름으로 굴러갑니다",
                    resolves="gap1", unit_index=0, info_role="radius_diff_v2")
    graph = DeclaredEventGraph(events=[gap, clue1, clue2], grounded_claims=[GAP_CLAIM])
    windows = [
        _window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]),
        _window("s2", 5.0, [("CLUE", clue1.text, 0.0, 2.0)]),
        _window("s3", 10.0, [("CLUE", clue2.text, 0.0, 2.0)]),
    ]

    def clue_novelty(prior_texts, new_text):
        if new_text in prior_texts:
            return JudgeVerdict(status=JUDGE_FAIL, quote=new_text)
        return JudgeVerdict(status=JUDGE_PASS, quote=new_text)

    judge = ScriptedJudge(clue_novelty=clue_novelty)
    evidence = build_observed_evidence(graph, windows, judge)
    assert clue1.info_role != clue2.info_role, "fixture sanity: labels genuinely differ"
    assert evidence["clue2"].judge_verdict == JUDGE_FAIL, \
        "identical real content behind differently-labeled info_role must be caught by the judge, independent of the label"


# ---------------------------------------------------------------------------
# 3. hook_type semantic mismatch (Layer 2 equivalent): a VIOLATION grounded
#    in a real claim, but its text is a flat danger statement with no
#    actual contradiction. Layer 1's hook_type enum check PASSed this
#    (Phase 0 adversarial #3, hook_type="contradiction" on a pure-danger
#    sentence). Layer 2's judge must be able to reject it.
# ---------------------------------------------------------------------------
def test_hook_type_style_semantic_mismatch_is_flagged_by_judge():
    claim = _claim("c1", "기차 바퀴는 축에 고정돼 있다", "두 바퀴는 하나의 축에 고정돼 있습니다")
    violation = _event("v1", "VIOLATION", "s1", "이 기차는 위험합니다",
                        unit_index=0, refs=["c1"])
    graph = DeclaredEventGraph(events=[violation], grounded_claims=[claim])
    windows = [_window("s1", 0.0, [("HOOK", violation.text, 0.0, 1.5)])]

    def judge_violation(claim_text, violation_text):
        # A real contradiction should reference/contrast the claim; a bare
        # danger word with no contrast marker is not one.
        contrast_markers = ("그런데", "하지만", "사실은", "반대로")
        if not any(m in violation_text for m in contrast_markers):
            return JudgeVerdict(status=JUDGE_FAIL, quote=violation_text)
        return JudgeVerdict(status=JUDGE_PASS, quote=violation_text)

    judge = ScriptedJudge(violation=judge_violation)
    evidence = build_observed_evidence(graph, windows, judge)
    assert evidence["v1"].judge_verdict == JUDGE_FAIL, \
        "a declared VIOLATION with no real contradiction in its text must be flagged, not passed just because it cites a grounded claim"


# ---------------------------------------------------------------------------
# 4. Relabeled flat story progression: a critical GAP with three CLUEs, all
#    judged as carrying no real new information. Layer 1's story-progression
#    check (4 distinct role labels) PASSed an equivalent flat script (Phase
#    0 adversarial #4). Layer 2's core invariant (unresolved_critical_gap_
#    count == 0) must catch it: none of the flat clues can fulfill the gap.
# ---------------------------------------------------------------------------
def test_relabeled_flat_progression_leaves_gap_unresolved():
    gap = _gap("gap1", "s1", "그것은 무엇일까요?", unit_index=0)
    clues = [
        _event(f"clue{i}", "CLUE", f"s{i+1}", text, resolves="gap1", unit_index=0)
        for i, text in enumerate(["그것은 A입니다", "그것은 B입니다", "그것은 C입니다"])
    ]
    graph = DeclaredEventGraph(events=[gap] + clues, grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)])] + [
        _window(f"s{i+2}", float(5 * (i + 1)), [("CLUE", c.text, 0.0, 1.0)]) for i, c in enumerate(clues)
    ]
    # A judge that always finds "no real new information" -- simulating a
    # human reviewer's actual verdict on a flat A-and-B-and-C script.
    judge = ScriptedJudge(clue_novelty=lambda prior, new: JudgeVerdict(status=JUDGE_FAIL, quote=new))
    evidence = build_observed_evidence(graph, windows, judge)
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["unresolved_critical_gap_count"] == 1
    assert "gap1" in result["unresolved_critical_gap_ids"]


# ---------------------------------------------------------------------------
# 5. Paraphrased redundant narration: two CLUEs with near-ZERO lexical
#    overlap but the same real meaning. Layer 1's token-overlap-based
#    duplicate check missed this (Phase 0 adversarial #5). Layer 2 must
#    catch it via the judge, NOT via lexical overlap (which we prove here
#    is actually low, to show we are not secretly relying on it).
# ---------------------------------------------------------------------------
def test_paraphrased_redundant_clue_is_flagged_by_judge_not_by_overlap():
    gap = _gap("gap1", "s1", "무엇이 다를까요?", unit_index=0)
    clue1 = _event("clue1", "CLUE", "s2", "바깥쪽 바퀴가 더 먼 거리를 이동합니다", resolves="gap1", unit_index=0)
    clue2 = _event("clue2", "CLUE", "s3", "가장자리 차륜은 훨씬 긴 궤적을 그리며 굴러갑니다", resolves="gap1", unit_index=0)
    overlap = token_overlap_ratio(clue1.text, clue2.text)
    assert overlap < 0.3, f"fixture sanity: lexical overlap must be genuinely low, got {overlap}"

    graph = DeclaredEventGraph(events=[gap, clue1, clue2], grounded_claims=[GAP_CLAIM])
    windows = [
        _window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]),
        _window("s2", 5.0, [("CLUE", clue1.text, 0.0, 2.0)]),
        _window("s3", 10.0, [("CLUE", clue2.text, 0.0, 2.0)]),
    ]
    # A judge that correctly recognizes semantic equivalence despite low
    # lexical overlap (standing in for a real semantic model).
    judge = ScriptedJudge(clue_novelty=lambda prior, new: JudgeVerdict(
        status=JUDGE_FAIL if prior else JUDGE_PASS, quote=new))
    evidence = build_observed_evidence(graph, windows, judge)
    assert evidence["clue2"].judge_verdict == JUDGE_FAIL, \
        "a semantically-redundant paraphrase must be caught even when lexical overlap is low"


# ---------------------------------------------------------------------------
# 6. Declared event exists but Observed Evidence is missing: the direct
#    generalization of the real hook_type no-op bug (Phase 0/0.5) -- a
#    manifest can declare anything; only real render evidence makes it
#    count. Even a judge that would unconditionally PASS must not be able
#    to fulfill a gap whose closing event was never actually observed.
# ---------------------------------------------------------------------------
def test_unobserved_event_cannot_fulfill_a_gap_even_with_an_always_pass_judge():
    gap = _gap("gap1", "s1", "어떻게 될까요?", unit_index=0, critical=True)
    # Declares narration_unit_index=5, but the real scene only has 1 unit.
    resolution = _event("res1", "RESOLUTION", "s2", "이렇게 됩니다", resolves="gap1", unit_index=5)
    graph = DeclaredEventGraph(events=[gap, resolution], grounded_claims=[GAP_CLAIM])
    windows = [
        _window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]),
        _window("s2", 5.0, [("EXPLANATION", "실제로 합성된 단 하나의 문장", 0.0, 2.0)]),
    ]
    evidence = build_observed_evidence(graph, windows, AlwaysPass())
    assert evidence["res1"].observed is False
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["unresolved_critical_gap_count"] == 1, \
        "an unobserved event must not fulfill a gap even when the judge would unconditionally pass it"


# ---------------------------------------------------------------------------
# 7. Declared RESOLUTION that does not actually answer the GAP: real,
#    observed text with HIGH lexical overlap with the gap's own wording,
#    but the judge correctly determines it doesn't actually answer the
#    question. Proves fulfillment is never decided by lexical overlap
#    (Phase 0.5 design correction 2).
# ---------------------------------------------------------------------------
def test_high_overlap_non_answer_resolution_does_not_fulfill_gap():
    gap = _gap("gap1", "s1", "바깥쪽 바퀴는 왜 더 멀리 갈까요?", unit_index=0)
    # Deliberately shares many tokens with the gap text, but is not an
    # answer -- just a restatement of the question as a non-answer.
    resolution = _event("res1", "RESOLUTION", "s2", "바깥쪽 바퀴는 확실히 더 멀리 갑니다",
                         resolves="gap1", unit_index=0)
    overlap = token_overlap_ratio(gap.text, resolution.text)
    assert overlap >= 0.4, f"fixture sanity: lexical overlap must be genuinely high, got {overlap}"

    graph = DeclaredEventGraph(events=[gap, resolution], grounded_claims=[GAP_CLAIM])
    windows = [
        _window("s1", 0.0, [("GAP", gap.text, 0.0, 1.5)]),
        _window("s2", 5.0, [("RESOLUTION", resolution.text, 0.0, 1.5)]),
    ]
    judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(status=JUDGE_FAIL, quote=c))
    evidence = build_observed_evidence(graph, windows, judge)
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["unresolved_critical_gap_count"] == 1, \
        "high lexical overlap must not substitute for the judge's semantic verdict"


# ---------------------------------------------------------------------------
# 8. Invented/ungrounded VIOLATION: zero grounded_claim_refs on a VIOLATION
#    event. This is a STRUCTURAL defect (can a claim even be cited), not a
#    semantic one, so it is rejected at construction time -- the strongest
#    possible proof, matching extra="forbid"'s own fail-closed philosophy.
# ---------------------------------------------------------------------------
def test_ungrounded_violation_is_rejected_at_construction_time():
    with pytest.raises(ValidationError, match="requires at least one grounded_claim_refs"):
        CognitiveEvent(id="v1", type="VIOLATION", scene_id="s1", text="아무 근거 없는 반전입니다", grounded_claim_refs=[])


def test_violation_referencing_unknown_claim_is_rejected():
    with pytest.raises(ValidationError, match="not a declared GroundedClaim id"):
        DeclaredEventGraph(
            events=[_event("v1", "VIOLATION", "s1", "그런데 사실은 다릅니다", refs=["does-not-exist"])],
            grounded_claims=[],
        )


# ---------------------------------------------------------------------------
# 9. Unresolved critical GAP: a critical GAP with no closing event declared
#    at all. THE core invariant this whole contract exists to enforce.
# ---------------------------------------------------------------------------
def test_gap_with_no_closing_event_is_unresolved():
    gap = _gap("gap1", "s1", "어떻게 될까요?", unit_index=0, critical=True)
    graph = DeclaredEventGraph(events=[gap], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)])]
    evidence = build_observed_evidence(graph, windows, NullJudge())
    loops = compute_curiosity_loops(graph, evidence)
    assert len(loops) == 1
    assert loops[0].fulfilled is False
    result = verify_unresolved_critical_gaps(loops)
    assert result["status"] == "FAIL"
    assert result["unresolved_critical_gap_count"] == 1


def test_non_critical_gap_left_open_does_not_fail_the_invariant():
    gap = _gap("gap1", "s1", "사소한 질문입니다", unit_index=0, critical=False)
    graph = DeclaredEventGraph(events=[gap], grounded_claims=[GAP_CLAIM])
    windows = [_window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)])]
    evidence = build_observed_evidence(graph, windows, NullJudge())
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["status"] == "PASS"
    assert result["unresolved_critical_gap_count"] == 0


# ---------------------------------------------------------------------------
# 10. Judge NOT_EVALUATED must never count as a pass. Mirrors visual_qa.py's
#     ClipSemanticVisionProvider: an inconclusive semantic check must not be
#     silently promoted to PASS by anything else.
# ---------------------------------------------------------------------------
def test_not_evaluated_judge_verdict_does_not_fulfill_gap():
    gap = _gap("gap1", "s1", "어떻게 될까요?", unit_index=0)
    resolution = _event("res1", "RESOLUTION", "s2", "이렇게 됩니다", resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, resolution], grounded_claims=[GAP_CLAIM])
    windows = [
        _window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]),
        _window("s2", 5.0, [("RESOLUTION", resolution.text, 0.0, 1.0)]),
    ]
    evidence = build_observed_evidence(graph, windows, NullJudge())  # always NOT_EVALUATED
    assert evidence["res1"].observed is True
    assert evidence["res1"].judge_verdict == JUDGE_NOT_EVALUATED
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["unresolved_critical_gap_count"] == 1, "NOT_EVALUATED must never count as fulfillment"


def test_malformed_pass_verdict_with_no_quote_is_downgraded_to_not_evaluated():
    """A judge implementation that 'cheats' by returning PASS with no
    evidence quote must be caught by the framework itself, not merely by
    convention -- see entertainment_qa._normalize_verdict."""
    gap = _gap("gap1", "s1", "어떻게 될까요?", unit_index=0)
    resolution = _event("res1", "RESOLUTION", "s2", "이렇게 됩니다", resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, resolution], grounded_claims=[GAP_CLAIM])
    windows = [
        _window("s1", 0.0, [("GAP", gap.text, 0.0, 1.0)]),
        _window("s2", 5.0, [("RESOLUTION", resolution.text, 0.0, 1.0)]),
    ]
    cheating_judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(status=JUDGE_PASS, quote=None))
    evidence = build_observed_evidence(graph, windows, cheating_judge)
    assert evidence["res1"].judge_verdict == JUDGE_NOT_EVALUATED


# ---------------------------------------------------------------------------
# Positive case: everything lines up (observed + judge PASS with a real
# quote) -- proves the mechanism can actually confirm a real fulfillment,
# not just reject fake ones.
# ---------------------------------------------------------------------------
def test_a_real_observed_judge_confirmed_resolution_fulfills_the_gap():
    gap = _gap("gap1", "s1", "왜 커브를 돌 수 있을까요?", unit_index=0)
    resolution = _event("res1", "RESOLUTION", "s2", "반지름 차이 덕분에 축이 스스로 중앙으로 돌아옵니다",
                         resolves="gap1", unit_index=0)
    graph = DeclaredEventGraph(events=[gap, resolution], grounded_claims=[GAP_CLAIM])
    windows = [
        _window("s1", 0.0, [("GAP", gap.text, 0.0, 1.5)]),
        _window("s2", 5.0, [("RESOLUTION", resolution.text, 0.0, 2.5)]),
    ]
    judge = ScriptedJudge(resolution=lambda g, c: JudgeVerdict(status=JUDGE_PASS, quote=c))
    evidence = build_observed_evidence(graph, windows, judge)
    loops = compute_curiosity_loops(graph, evidence)
    result = verify_unresolved_critical_gaps(loops)
    assert result["status"] == "PASS"
    assert result["unresolved_critical_gap_count"] == 0
    assert loops[0].fulfilled is True
    assert loops[0].fulfilling_event_id == "res1"


# ---------------------------------------------------------------------------
# Structural regressions: extra="forbid" applies to the new models too;
# existing manifests are completely unaffected.
# ---------------------------------------------------------------------------
def test_new_models_forbid_unknown_fields():
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        CognitiveEvent(id="e1", type="CLAIM", scene_id="s1", text="x", made_up_field=True)
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        GroundedClaim(id="c1", text="x", source_ref="y", made_up_field=True)
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        DeclaredEventGraph(events=[], grounded_claims=[], made_up_field=True)


def test_grounded_claim_source_ref_must_match_a_real_factual_note():
    with pytest.raises(ValidationError, match="does not match any"):
        Project(title="t", scenes=[_scene("s1", fact="실제 사실 A")],
                event_graph=DeclaredEventGraph(
                    events=[], grounded_claims=[_claim("c1", "주장", "존재하지 않는 사실")]))


def test_event_scene_id_must_reference_a_real_scene():
    with pytest.raises(ValidationError, match="does not match any real Scene.id"):
        Project(title="t", scenes=[_scene("s1")],
                event_graph=DeclaredEventGraph(
                    events=[_event("e1", "CLAIM", "does-not-exist", "x")], grounded_claims=[]))


@pytest.mark.parametrize("path", ["examples/comet.json", "examples/radium_girls.json"])
def test_existing_manifests_declare_no_event_graph_and_are_unaffected(path):
    import json
    from shorts_studio.project import load_project
    project = load_project(path)
    assert project.event_graph is None
    assert project.strict_entertainment_contract is False
    assert run_entertainment_contract_report(project, scene_windows=[]) is None
