"""Psychological Entertainment Contract (Layer 2), Phase 1: minimal
foundation.

A Declared Event Graph (models.DeclaredEventGraph -- author intent) is
cross-checked against Observed Event Evidence (real narration timing from
the actual render, and an evidence-quoting semantic judge) before any of
it can count toward the contract's one hard invariant:

    unresolved_critical_gap_count == 0

Phase 0's adversarial audit of the existing Layer-1 retention contracts
(final_video_qa.py's First-Second Hook / Information Change / Story
Progression / Ending Payoff / Runtime Discipline checks) demonstrated,
against the real functions, that a role label, an info_role string, or a
hook_type declaration all PASS today with no corresponding real content
change -- declared metadata alone proved nothing. This module exists to
close exactly that gap, not to replace Layer 1 (which stays, unweakened,
as a cheap deterministic early filter -- see final_video_qa.py's
retention-engine section header for the four-layer architecture this fits
into).

Two kinds of check live here, and they are never conflated:
  - STRUCTURAL / deterministic (id references, grounding presence): these
    are hard pydantic validation errors at manifest-construction time (see
    models.py) -- exactly as fail-closed as extra="forbid".
  - SEMANTIC / observed-evidence (is this REALLY a payoff, does this CLUE
    really add new information, does this RESOLUTION really answer its
    GAP): these require reading comprehension no regex/enum/lexical-overlap
    check can honestly provide, so they are handed to a SemanticJudge and
    reported -- see run_entertainment_contract_report. This is Phase 1's
    core design decision, repeated here because it is easy to accidentally
    violate later: semantic fulfillment is NEVER approximated with
    retention_rules.token_overlap_ratio or any other lexical-overlap
    heuristic. A judge verdict of NOT_EVALUATED is not a pass -- it means
    exactly what it says, and a GAP a NOT_EVALUATED verdict was supposed to
    close remains unresolved, the same way ClipSemanticVisionProvider's
    NOT_EVALUATED must never be silently promoted to PASS by anything else
    (visual_qa.py's CompositeVisionProvider).

REPORT-ONLY in Phase 1: nothing in this module ever raises, and nothing it
computes is folded into final_video_qa.run_final_video_qa's `checks` dict
or `overall` PASS/FAIL -- see run_entertainment_contract_report's own
docstring and models.Project.strict_entertainment_contract. A Project that
declares no event_graph is completely unaffected; none of Comet, Radium
Girls, Titanic, or Train Wheels declare one.

Known Phase 1 limitations (not fixed here, listed so they are not
mistaken for gaps in the architecture rather than gaps in this phase's
scope):
  - No real semantic judge is wired to an actual model. NullJudge (always
    NOT_EVALUATED) is the only shipped implementation; ScriptedJudge exists
    for tests only. Because NOT_EVALUATED can never close a GAP, a Project
    using NullJudge structurally cannot claim any critical GAP is
    fulfilled -- correct, fail-closed behavior, but it means this module
    cannot yet demonstrate an actually-fulfilled GAP end-to-end without a
    test double standing in for a real judge.
  - Observed Event Evidence only connects through narration_unit_index
    (real per-unit TTS timing, threaded through scene_windows by
    render.py). visual_beat_index is accepted on CognitiveEvent and
    reserved on ObservedEventEvidence, but Phase 1 does not yet resolve it
    against real per-beat visual-cut evidence -- that is a Phase 2
    extension, not implemented here.
  - No production manifest sets strict_entertainment_contract=True or
    declares an event_graph. Train Wheels V2 (or any real script using this
    contract) is explicitly out of Phase 1's scope.
"""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .entertainment_rules import (
    GAP_CLOSING_TYPES, JUDGE_FAIL, JUDGE_NOT_EVALUATED, JUDGE_PASS, JUDGE_VERDICTS,
)

_FORBID_EXTRA = ConfigDict(extra="forbid")


class JudgeVerdict(BaseModel):
    """A SemanticJudge's answer to exactly one narrow question. Never a
    numeric score: Phase 0's Goodhart audit is precisely about metrics an
    author can satisfy without the underlying thing being true, and a
    'fun_score >= 7' gate just relocates that same problem one layer up.
    `quote` must be the specific span of real text the verdict is based on;
    a non-NOT_EVALUATED verdict with no quote is treated as malformed (see
    _normalize_verdict) and downgraded to NOT_EVALUATED -- unquotable is
    untrustworthy."""
    model_config = _FORBID_EXTRA
    status: str
    quote: str | None = None


def _normalize_verdict(v: JudgeVerdict) -> JudgeVerdict:
    if v.status not in JUDGE_VERDICTS:
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, quote=None)
    if v.status != JUDGE_NOT_EVALUATED and not (v.quote and v.quote.strip()):
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, quote=None)
    return v


class SemanticJudge(Protocol):
    """Evidence-quoting semantic judge interface. No real model is wired up
    in Phase 1 -- see this module's docstring. A judge implementation must
    never return a numeric score, must always be able to say NOT_EVALUATED
    instead of guessing, and must quote the real text a PASS/FAIL is based
    on."""
    def judge_violation(self, claim_text: str, violation_text: str) -> JudgeVerdict: ...
    def judge_clue_novelty(self, prior_texts: list[str], new_text: str) -> JudgeVerdict: ...
    def judge_resolution(self, gap_text: str, candidate_text: str) -> JudgeVerdict: ...
    def judge_payoff_reframing(self, prior_texts: list[str], payoff_text: str) -> JudgeVerdict: ...


class NullJudge:
    """The safe default: NOT_EVALUATED for everything, always. Since
    NOT_EVALUATED can never close a GAP (verify_unresolved_critical_gaps),
    a Project that declares an event_graph without supplying a real judge
    gets a contract that structurally cannot claim any GAP is fulfilled --
    it fails closed, never open, exactly like ClipSemanticVisionProvider
    returning NOT_EVALUATED when the CLIP model isn't installed."""
    def _ne(self) -> JudgeVerdict:
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED)
    def judge_violation(self, claim_text, violation_text) -> JudgeVerdict: return self._ne()
    def judge_clue_novelty(self, prior_texts, new_text) -> JudgeVerdict: return self._ne()
    def judge_resolution(self, gap_text, candidate_text) -> JudgeVerdict: return self._ne()
    def judge_payoff_reframing(self, prior_texts, payoff_text) -> JudgeVerdict: return self._ne()


class ObservedEventEvidence(BaseModel):
    """What the real render/synthesis actually shows for one declared
    CognitiveEvent -- always DERIVED, never authored. `observed=False`
    means the event's scene_id/narration_unit_index didn't resolve to
    anything real in the actual scene_windows data (out of range, missing
    entirely, etc.); such an event counts toward NOTHING, independent of
    what judge_verdict says, because there is no real content to have
    judged. This is the direct fix for the exact failure Phase 0 found
    live in production: a manifest field (hook_type) that existed only on
    paper with zero connection to engine behavior."""
    model_config = _FORBID_EXTRA
    event_id: str
    observed: bool
    real_narration_text: str | None = None
    real_start: float | None = None
    real_end: float | None = None
    real_visual_cut_nearby: bool = False
    judge_verdict: str = JUDGE_NOT_EVALUATED
    judge_quote: str | None = None


class CuriosityLoop(BaseModel):
    """Derived (never authored) view of one GAP and everything declared to
    close it, in declaration order. `fulfilled` is true only if at least
    one GAP_CLOSING_TYPES event resolving this gap is BOTH observed AND
    carries judge_verdict == PASS -- see compute_curiosity_loops. A GAP may
    accumulate any number of CLUE/partial-REVEAL events before it is
    fulfilled, or never be fulfilled at all (see
    verify_unresolved_critical_gaps for what that means for a critical
    gap)."""
    model_config = _FORBID_EXTRA
    gap_id: str
    critical: bool
    clue_ids: list[str] = Field(default_factory=list)
    fulfilled: bool = False
    fulfilling_event_id: str | None = None


_VISUAL_CUT_PROXIMITY_SECONDS = 3.5  # matches final_video_qa's own visual-cut-cadence limit


def build_observed_evidence(graph, scene_windows: list[dict], judge: SemanticJudge,
                             visual_cut_timestamps: list[float] | None = None) -> dict[str, ObservedEventEvidence]:
    """Resolve every declared CognitiveEvent against real render output.

    scene_windows: the same structure render() already produces per scene
    (see final_video_qa.compute_first_10s_narration_timeline for the
    precedent this generalizes) -- a list of dicts with "scene", "start",
    and "narration_units" (real per-unit text/start/end from tts.py's
    unit_spans, scene-relative). Nothing here trusts a manifest-declared
    timestamp; if scene_windows doesn't have real narration_units for an
    event's declared scene_id/narration_unit_index, that event is simply
    not observed.

    visual_cut_timestamps: real, measured pixel-diff cut times for the
    whole video (final_video_qa.measure_visual_activity's own output) --
    optional; only used to fill in the real_visual_cut_nearby diagnostic
    field, never a gate in Phase 1.
    """
    windows_by_scene = {w.get("scene"): w for w in scene_windows}
    cuts = sorted(visual_cut_timestamps or [])

    # Resolve every event's real text/timing first (pure lookup, no
    # judging yet), so judge calls below can reference other events' real
    # text (e.g. a GAP's real wording, or earlier CLUEs' real text) instead
    # of their merely-declared text.
    real_text_by_id: dict[str, str | None] = {}
    real_start_by_id: dict[str, float | None] = {}
    observed_by_id: dict[str, bool] = {}
    for e in graph.events:
        window = windows_by_scene.get(e.scene_id)
        text = None; start = None; end = None; observed = False
        if window is not None and e.narration_unit_index is not None:
            units = window.get("narration_units") or []
            if 0 <= e.narration_unit_index < len(units):
                u = units[e.narration_unit_index]
                text = u.get("text"); start = u.get("start"); end = u.get("end")
                observed = True
                base = float(window.get("start", 0.0) or 0.0)
                if start is not None:
                    start = base + float(start)
                if end is not None:
                    end = base + float(end)
        real_text_by_id[e.id] = text
        real_start_by_id[e.id] = start
        observed_by_id[e.id] = observed

    events_by_id = {e.id: e for e in graph.events}
    evidence: dict[str, ObservedEventEvidence] = {}
    for e in graph.events:
        observed = observed_by_id[e.id]
        text = real_text_by_id[e.id]
        start = real_start_by_id[e.id]
        cut_nearby = False
        if observed and start is not None and cuts:
            cut_nearby = any(abs(c - start) <= _VISUAL_CUT_PROXIMITY_SECONDS for c in cuts)

        verdict = JudgeVerdict(status=JUDGE_NOT_EVALUATED)
        if observed and text:
            if e.type == "VIOLATION":
                claim_texts = [c.text for c in graph.grounded_claims if c.id in e.grounded_claim_refs]
                claim_text = claim_texts[0] if claim_texts else ""
                verdict = _normalize_verdict(judge.judge_violation(claim_text, text))
            elif e.type == "CLUE" and e.resolves:
                prior_ids = [
                    o.id for o in graph.events
                    if o.resolves == e.resolves and o.type == "CLUE"
                    and graph.events.index(o) < graph.events.index(e)
                ]
                prior_texts = [t for t in (real_text_by_id.get(pid) for pid in prior_ids) if t]
                verdict = _normalize_verdict(judge.judge_clue_novelty(prior_texts, text))
            elif e.type in ("RESOLUTION", "REVEAL") and e.resolves:
                gap = events_by_id.get(e.resolves)
                gap_text = (real_text_by_id.get(e.resolves) if gap and observed_by_id.get(e.resolves) else None) \
                    or (gap.text if gap else "")
                verdict = _normalize_verdict(judge.judge_resolution(gap_text, text))
            elif e.type == "PAYOFF":
                prior_ids = [o.id for o in graph.events if o.type in ("REVEAL", "RESOLUTION")]
                prior_texts = [t for t in (real_text_by_id.get(pid) for pid in prior_ids) if t]
                verdict = _normalize_verdict(judge.judge_payoff_reframing(prior_texts, text))

        evidence[e.id] = ObservedEventEvidence(
            event_id=e.id, observed=observed,
            real_narration_text=text, real_start=start, real_end=real_start_by_id.get(e.id),
            real_visual_cut_nearby=cut_nearby,
            judge_verdict=verdict.status, judge_quote=verdict.quote,
        )
    return evidence


def compute_curiosity_loops(graph, evidence_by_id: dict[str, ObservedEventEvidence]) -> list[CuriosityLoop]:
    """A GAP may accumulate any number of CLUE/partial-REVEAL events (Phase
    0.5 correction: this replaces an earlier, discarded 'exactly one
    RESOLUTION' rule). It is fulfilled the moment ANY closing event for it
    is both observed and judge-confirmed PASS -- never by lexical overlap,
    never by the mere existence of a RESOLUTION-typed event."""
    loops = []
    for gap in (e for e in graph.events if e.type == "GAP"):
        closing = [e for e in graph.events if e.resolves == gap.id and e.type in GAP_CLOSING_TYPES]
        fulfilled = False
        fulfilling_id = None
        for c in closing:
            ev = evidence_by_id.get(c.id)
            if ev and ev.observed and ev.judge_verdict == JUDGE_PASS:
                fulfilled = True
                fulfilling_id = c.id
                break
        loops.append(CuriosityLoop(
            gap_id=gap.id, critical=gap.critical,
            clue_ids=[c.id for c in closing],
            fulfilled=fulfilled, fulfilling_event_id=fulfilling_id,
        ))
    return loops


def verify_unresolved_critical_gaps(loops: list[CuriosityLoop]) -> dict:
    """THE core invariant of this whole contract: unresolved_critical_gap_count
    must be 0 by the end of the video. Report-only in Phase 1 (see module
    docstring) -- this function's own 'status' is diagnostic, never wired
    into final_video_qa's overall PASS/FAIL."""
    unresolved = [l for l in loops if l.critical and not l.fulfilled]
    return {
        "status": "PASS" if not unresolved else "FAIL",
        "unresolved_critical_gap_count": len(unresolved),
        "unresolved_critical_gap_ids": [l.gap_id for l in unresolved],
    }


def compute_entertainment_diagnostics(graph, loops: list[CuriosityLoop]) -> dict:
    """Soft, report-only numbers. None of these are optimization targets or
    gates -- there is deliberately no 'correct' event density or gap count
    (see the PEC design report's critique of Berlyne's inverted-U as a
    literal formula). Reported purely so a human reviewing qa_report.json
    can see the shape of the graph without re-deriving it by hand."""
    by_type: dict[str, int] = {}
    for e in graph.events:
        by_type[e.type] = by_type.get(e.type, 0) + 1
    fulfilled = sum(1 for l in loops if l.fulfilled)
    return {
        "event_count": len(graph.events),
        "event_count_by_type": by_type,
        "gap_count": len(loops),
        "critical_gap_count": sum(1 for l in loops if l.critical),
        "fulfilled_gap_count": fulfilled,
        "grounded_claim_count": len(graph.grounded_claims),
    }


def run_entertainment_contract_report(project, scene_windows: list[dict], judge: SemanticJudge | None = None,
                                       visual_cut_timestamps: list[float] | None = None) -> dict | None:
    """The Phase 1 aggregate. Returns None (nothing to report) when the
    project declares no event_graph -- every existing production manifest
    (Comet, Radium Girls, Titanic, Train Wheels) takes this path and is
    completely unaffected.

    REPORT-ONLY, unconditionally, in Phase 1: the returned dict's own
    "status" field is informational only. Callers (render.py) must attach
    this under qa_report.json's top-level "entertainment_contract" key,
    OUTSIDE final_video_qa's `checks` dict, so it can never affect
    `overall` PASS/FAIL no matter what it finds -- see
    models.Project.strict_entertainment_contract's docstring for why this
    is deliberate at this phase, not an oversight."""
    graph = getattr(project, "event_graph", None)
    if graph is None:
        return None
    judge = judge or NullJudge()
    evidence = build_observed_evidence(graph, scene_windows, judge, visual_cut_timestamps)
    loops = compute_curiosity_loops(graph, evidence)
    gap_check = verify_unresolved_critical_gaps(loops)
    diagnostics = compute_entertainment_diagnostics(graph, loops)
    return {
        "mode": "report-only",
        "strict_entertainment_contract": bool(getattr(project, "strict_entertainment_contract", False)),
        "unresolved_critical_gaps": gap_check,
        "curiosity_loops": [loop.model_dump() for loop in loops],
        "observed_evidence": {eid: ev.model_dump() for eid, ev in evidence.items()},
        "diagnostics": diagnostics,
    }
