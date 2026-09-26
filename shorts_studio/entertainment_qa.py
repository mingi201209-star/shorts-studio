"""Psychological Entertainment Contract (Layer 2).

Phase 1 built the skeleton: a Declared Event Graph (models.DeclaredEventGraph
-- author intent) cross-checked against Observed Event Evidence (real
narration timing from the actual render, and an evidence-quoting semantic
judge) before any of it can count toward the contract's one hard invariant:

    unresolved_critical_gap_count == 0

Phase 2 fills the skeleton in:
  - a real, evidence-quoting SemanticJudge implementation (AnthropicJudge),
    kept behind the same fail-closed NullJudge default;
  - six narrow, independent assertion types (see entertainment_rules.
    ASSERTION_TYPES) instead of one fuzzy "is this good" question;
  - hardened Observed Narration Evidence (a coarse structural divergence
    check on top of Phase 1's presence/absence check) and new Observed
    Visual Evidence (visual_beat_index resolved against the real,
    pixel-diff-measured cut timestamps final_video_qa.py already computes,
    and the existing per-scene semantic visual QA result reused, not
    duplicated);
  - explicit declared_status / observed_status / semantic_status fields per
    event, plus a `mismatches` list -- never collapsed into one PASS string.

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
  - STRUCTURAL / deterministic (id references, grounding presence, does a
    referenced visual beat exist at all): these are either hard pydantic
    validation errors at manifest-construction time (see models.py) or
    simple presence/absence lookups against real render data here.
  - SEMANTIC / observed-evidence (is this REALLY a payoff, does this CLUE
    really add new information, does this RESOLUTION really answer its
    GAP, does this VIOLATION really contradict the claim beneath it, does
    the hook oversell what the video actually delivers, does the tension
    distort its own grounding): these require reading comprehension no
    regex/enum/lexical-overlap check can honestly provide, so they are
    handed to a SemanticJudge and reported -- see
    run_entertainment_contract_report. This is the design decision this
    whole module exists to protect, repeated here because it is easy to
    accidentally violate later: semantic fulfillment is NEVER approximated
    with retention_rules.token_overlap_ratio or any other lexical-overlap
    heuristic. The ONE place lexical overlap appears at all in this module
    is TEXT_DIVERGENCE_OVERLAP_FLOOR, and that is a coarse "is this even
    remotely the same sentence" sanity check surfaced as a `mismatches`
    diagnostic code -- it can flag a stale/wrong narration_unit_index, but
    it can never confirm a semantic assertion, and never appears anywhere
    near a PASS decision. A judge verdict of NOT_EVALUATED is not a pass --
    it means exactly what it says, and a GAP a NOT_EVALUATED verdict was
    supposed to close remains unresolved, the same way
    ClipSemanticVisionProvider's NOT_EVALUATED must never be silently
    promoted to PASS by anything else (visual_qa.py's
    CompositeVisionProvider).

Judge independence (Phase 2 section 2): every judge call in this module
goes through _dispatch -> _call_judge_safely -> _normalize_verdict, in that
order, REGARDLESS of which SemanticJudge implementation is plugged in.
That pipeline is the actual enforcement of "fail-open is never acceptable":
  - a judge that doesn't implement a given method (e.g. an older judge
    predating judge_overclaim) -> NOT_EVALUATED, not an AttributeError;
  - a judge call that raises -> NOT_EVALUATED, not a propagated exception;
  - a judge call that hangs past JUDGE_CALL_TIMEOUT_SECONDS -> NOT_EVALUATED,
    not a blocked report;
  - a non-JudgeVerdict / malformed return value -> NOT_EVALUATED;
  - a PASS/FAIL verdict with no quote, an EMPTY quote, or a quote that is
    not a literal substring of the real text(s) actually handed to the
    judge (a fabricated quote) -> NOT_EVALUATED;
  - a verdict citing a compared_event_id that is not a real id in this
    graph -> NOT_EVALUATED.
No caller of this module can opt out of this pipeline; there is no second
code path that calls a judge method directly.

REPORT-ONLY, still: nothing in this module ever raises, and nothing it
computes is folded into final_video_qa.run_final_video_qa's `checks` dict
or `overall` PASS/FAIL -- see run_entertainment_contract_report's own
docstring and models.Project.strict_entertainment_contract. A Project that
declares no event_graph is completely unaffected; none of Comet, Radium
Girls, Titanic, or Train Wheels declare one, and strict_entertainment_contract
stays False on every production manifest through Phase 2.

Human review boundary (Phase 2 section 6): this module NEVER decides
whether something is actually funny, emotionally intense, delivered in an
appealing voice, cheap-feeling, liked by its target audience, culturally
awkward, or "fun enough" overall -- see HUMAN_REVIEW_EXCLUSIONS below and
run_entertainment_contract_report's `human_review_required` field, which is
always True. A PASS from this whole contract means only: "the declared
cognitive structure was implemented in the real content, and no obvious
structural or semantic failure was found." It does not mean "this video is
entertaining."
"""
from __future__ import annotations

import concurrent.futures
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .entertainment_rules import (
    ASSERTION_CLUE_NOVELTY, ASSERTION_GAP_FULFILLMENT, ASSERTION_GROUNDING_CONSISTENCY,
    ASSERTION_OVERCLAIM, ASSERTION_PAYOFF_REFRAMING, ASSERTION_VIOLATION_INTEGRITY,
    GAP_CLOSING_TYPES, JUDGE_CALL_TIMEOUT_SECONDS, JUDGE_FAIL, JUDGE_NOT_EVALUATED, JUDGE_PASS,
    JUDGE_VERDICTS, MISMATCH_CLUE_NO_NEW_INFORMATION, MISMATCH_NO_TIMING_EVIDENCE,
    MISMATCH_PAYOFF_MERE_REPETITION, MISMATCH_RESOLUTION_DOES_NOT_FULFILL_GAP,
    MISMATCH_TEXT_DIVERGES_FROM_NARRATION, MISMATCH_VIOLATION_NO_CONTRADICTION,
    MISMATCH_VISUAL_BEAT_MISSING, REQUIRES_GROUNDING, TEXT_DIVERGENCE_OVERLAP_FLOOR,
)
from .retention_rules import token_overlap_ratio

_FORBID_EXTRA = ConfigDict(extra="forbid")

# Automated PASS is never allowed to mean any of the following -- see this
# module's docstring and run_entertainment_contract_report's
# human_review_required field, which is always True regardless of what the
# rest of this contract finds. Listed explicitly, in the user's own terms,
# so this boundary is a design artifact, not a hopeful assumption.
HUMAN_REVIEW_EXCLUSIONS = (
    "actually funny",
    "emotionally intense/compelling",
    "TTS delivery sounds humanly appealing",
    "video feels cheap/low-production-value",
    "the target audience actually likes this topic",
    "culturally awkward or tone-deaf phrasing",
    "overall 'fun' is sufficient",
)

PEC_PASS_MEANING = (
    "The declared cognitive structure was implemented in the real content, "
    "and no obvious structural or semantic failure was found. This does NOT "
    "mean the video is entertaining, funny, or worth watching -- see "
    "HUMAN_REVIEW_EXCLUSIONS. Only real post-publish data or human review "
    "can establish that."
)


class JudgeVerdict(BaseModel):
    """A SemanticJudge's answer to exactly one narrow question. Never a
    numeric score: Phase 0's Goodhart audit is precisely about metrics an
    author can satisfy without the underlying thing being true, and a
    'fun_score >= 7' gate just relocates that same problem one layer up.
    `quote` must be the specific span of real text the verdict is based on;
    a non-NOT_EVALUATED verdict with no quote, an empty quote, or a quote
    that isn't a literal substring of the real text(s) the judge was given
    is treated as malformed (see _normalize_verdict) and downgraded to
    NOT_EVALUATED -- unquotable is untrustworthy. `compared_event_ids`
    names which declared events the verdict is actually about (for
    diagnostics and for catching a judge that cites an id that doesn't
    exist); `reason` is a short, human-readable justification -- never
    itself trusted as evidence, only as an explanation of the verdict."""
    model_config = _FORBID_EXTRA
    status: str
    quote: str | None = None
    compared_event_ids: list[str] = Field(default_factory=list)
    reason: str | None = None


def _normalize_verdict(v, *, source_texts: tuple[str, ...] = (),
                        valid_event_ids: set[str] | None = None) -> JudgeVerdict:
    """The single enforcement point for every fail-closed rule in Phase 2
    section 2. Called on EVERY judge result, from EVERY call site in this
    module -- there is no other way a JudgeVerdict reaches a caller."""
    if not isinstance(v, JudgeVerdict):
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="judge returned a malformed (non-JudgeVerdict) response")
    if v.status not in JUDGE_VERDICTS:
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason=f"unrecognized status {v.status!r}")
    if v.status == JUDGE_NOT_EVALUATED:
        return v
    quote = v.quote
    if not (quote and quote.strip()):
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="verdict had no evidence quote")
    if source_texts and not any(quote in t for t in source_texts if t):
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="quote is not a literal substring of any real text given to the judge (fabricated quote)")
    if valid_event_ids is not None:
        bad_ids = [eid for eid in v.compared_event_ids if eid not in valid_event_ids]
        if bad_ids:
            return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason=f"cited nonexistent event id(s): {bad_ids}")
    return v


_JUDGE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="pec-judge")


def _call_judge_safely(fn, *args, timeout_seconds: float = JUDGE_CALL_TIMEOUT_SECONDS) -> JudgeVerdict:
    """Runs one judge method call with a hard wall-clock budget and catches
    every exception. This is the ONLY way this module ever invokes a judge
    method -- see _dispatch, which additionally covers a judge that doesn't
    implement the method at all. fail-open is never acceptable (Phase 2
    section 2): every branch below returns NOT_EVALUATED, never raises,
    never guesses PASS/FAIL."""
    try:
        future = _JUDGE_EXECUTOR.submit(fn, *args)
        result = future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="judge call exceeded the timeout budget")
    except Exception as e:
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason=f"judge call raised {type(e).__name__}")
    if not isinstance(result, JudgeVerdict):
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="judge returned a malformed (non-JudgeVerdict) response")
    return result


def _dispatch(judge, method_name: str, *args, source_texts: tuple[str, ...] = (),
              valid_event_ids: set[str] | None = None) -> JudgeVerdict:
    """Look up `method_name` on `judge` and safely invoke it, or return
    NOT_EVALUATED if the judge doesn't implement it -- treating a judge that
    predates a given assertion type exactly like one that declined to
    answer, never as a hard error. Always finishes by running the result
    through _normalize_verdict, so no call site in this module can
    accidentally skip the fail-closed pipeline."""
    fn = getattr(judge, method_name, None)
    if fn is None:
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason=f"judge does not implement {method_name}")
    raw = _call_judge_safely(fn, *args)
    return _normalize_verdict(raw, source_texts=source_texts, valid_event_ids=valid_event_ids)


class SemanticJudge(Protocol):
    """Evidence-quoting semantic judge interface. Six narrow, independent
    questions (entertainment_rules.ASSERTION_TYPES) -- never "is this good"
    or a numeric score. A judge implementation must never return a numeric
    score, must always be able to say NOT_EVALUATED instead of guessing, and
    must quote the real text a PASS/FAIL is based on. Method -> assertion
    type: judge_violation -> VIOLATION_INTEGRITY, judge_clue_novelty ->
    CLUE_NOVELTY, judge_resolution -> GAP_FULFILLMENT, judge_payoff_reframing
    -> PAYOFF_REFRAMING, judge_overclaim -> OVERCLAIM,
    judge_grounding_consistency -> GROUNDING_CONSISTENCY."""
    def judge_violation(self, claim_text: str, violation_text: str) -> JudgeVerdict: ...
    def judge_clue_novelty(self, prior_texts: list[str], new_text: str) -> JudgeVerdict: ...
    def judge_resolution(self, gap_text: str, candidate_text: str) -> JudgeVerdict: ...
    def judge_payoff_reframing(self, prior_texts: list[str], payoff_text: str) -> JudgeVerdict: ...
    def judge_overclaim(self, hook_text: str, strongest_evidence_text: str) -> JudgeVerdict: ...
    def judge_grounding_consistency(self, claim_text: str, tension_text: str) -> JudgeVerdict: ...


class NullJudge:
    """The safe default: NOT_EVALUATED for everything, always. Since
    NOT_EVALUATED can never close a GAP (verify_unresolved_critical_gaps),
    a Project that declares an event_graph without supplying a real judge
    gets a contract that structurally cannot claim any GAP is fulfilled --
    it fails closed, never open, exactly like ClipSemanticVisionProvider
    returning NOT_EVALUATED when the CLIP model isn't installed."""
    def _ne(self) -> JudgeVerdict:
        return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="NullJudge: no real judge configured")
    def judge_violation(self, claim_text, violation_text) -> JudgeVerdict: return self._ne()
    def judge_clue_novelty(self, prior_texts, new_text) -> JudgeVerdict: return self._ne()
    def judge_resolution(self, gap_text, candidate_text) -> JudgeVerdict: return self._ne()
    def judge_payoff_reframing(self, prior_texts, payoff_text) -> JudgeVerdict: return self._ne()
    def judge_overclaim(self, hook_text, strongest_evidence_text) -> JudgeVerdict: return self._ne()
    def judge_grounding_consistency(self, claim_text, tension_text) -> JudgeVerdict: return self._ne()


# ---------------------------------------------------------------------------
# Real judge implementation. Mirrors visual_qa.ClipSemanticVisionProvider's
# own pattern exactly: an optional heavy dependency loaded lazily through a
# small free function (_load_anthropic_client), a second free function that
# does the actual call (_call_anthropic_messages) so tests can monkeypatch
# both without a network call or an API key (see test_visual_qa.py's own
# monkeypatch of vq._load_clip / vq.clip_zero_shot_scores for the precedent
# this follows), and NOT_EVALUATED -- never an exception -- whenever the
# dependency or the call itself is unavailable.
# ---------------------------------------------------------------------------

def _load_anthropic_client():
    """Returns a live anthropic.Anthropic() client, or None if the
    'anthropic' package isn't installed or no API key is configured. Never
    raises -- mirrors visual_qa._load_clip's own "optional heavy dependency,
    NOT_EVALUATED if unavailable" contract."""
    import os
    try:
        import anthropic
    except ImportError:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def _call_anthropic_messages(client, system: str, user: str, *, timeout: float = JUDGE_CALL_TIMEOUT_SECONDS) -> str:
    """The one place an actual network call happens. Returns the raw text
    response; all interpretation (JSON parsing, field validation) happens in
    AnthropicJudge._ask, which is what actually gets exercised by real
    fixtures below (this function is monkeypatched out in tests, exactly
    like visual_qa.clip_zero_shot_scores is)."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user}],
        timeout=timeout,
    )
    return "".join(block.text for block in response.content if getattr(block, "type", None) == "text")


_JUDGE_SYSTEM_PROMPT = (
    "You judge exactly one narrow factual assertion about a short video script. "
    "You are given only the minimal text needed for this one assertion -- never "
    "the full script, never the generation prompt that produced it. Respond with "
    "ONLY a JSON object: {\"status\": \"PASS\"|\"FAIL\"|\"NOT_EVALUATED\", \"quote\": "
    "\"<exact substring of the text you were given>\"|null, \"reason\": \"<one "
    "short sentence>\"}. Use NOT_EVALUATED if the assertion cannot be judged from "
    "the given text alone. `quote` must be copied verbatim from the input text; "
    "never paraphrase it. Never invent information not present in the given text. "
    "Do not rate quality, humor, or overall entertainment value -- answer only the "
    "single narrow question asked."
)


class AnthropicJudge:
    """A real evidence-quoting SemanticJudge backed by the Anthropic Messages
    API. Each method sends ONLY the two text fields that specific assertion
    needs -- never the full manifest, never prior generation history (Phase
    2 section 2's judge-independence requirement) -- and asks a
    JSON-schema-constrained question with no numeric scoring.

    Fails closed at every stage: if the 'anthropic' package isn't installed,
    if ANTHROPIC_API_KEY isn't set, if the API call itself raises or times
    out, or if the response isn't valid JSON with a recognized status, every
    method here returns NOT_EVALUATED rather than guessing or raising. This
    class's own NOT_EVALUATED paths are a second, inner safety net; the
    outer one (_dispatch/_call_judge_safely/_normalize_verdict in this same
    module) applies on top regardless, so a bug in this class's own
    validation can never itself produce a false PASS/FAIL."""

    def __init__(self, client=None):
        self._client = client  # lazily loaded via _load_anthropic_client() if None

    def _client_or_none(self):
        if self._client is not None:
            return self._client
        return _load_anthropic_client()

    def _ask(self, question: str, *text_fields: str) -> JudgeVerdict:
        client = self._client_or_none()
        if client is None:
            return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="no anthropic client available (package missing or ANTHROPIC_API_KEY unset)")
        user_prompt = question + "\n\n" + "\n\n".join(f"[TEXT {i+1}]\n{t}" for i, t in enumerate(text_fields))
        try:
            raw = _call_anthropic_messages(client, _JUDGE_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason=f"anthropic API call raised {type(e).__name__}")
        import json
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="judge response was not valid JSON")
        if not isinstance(data, dict) or "status" not in data:
            return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="judge response JSON missing required fields")
        try:
            return JudgeVerdict(
                status=str(data.get("status")),
                quote=data.get("quote"),
                reason=str(data.get("reason")) if data.get("reason") is not None else None,
            )
        except Exception:
            return JudgeVerdict(status=JUDGE_NOT_EVALUATED, reason="judge response JSON had an invalid shape")

    def judge_violation(self, claim_text: str, violation_text: str) -> JudgeVerdict:
        return self._ask(
            "Does [TEXT 2] (the VIOLATION) meaningfully contradict or complicate "
            "the mental model established by [TEXT 1] (the CLAIM)? Answer only "
            "that; do not judge writing quality.",
            claim_text, violation_text,
        )

    def judge_clue_novelty(self, prior_texts: list[str], new_text: str) -> JudgeVerdict:
        prior_block = "\n---\n".join(prior_texts) if prior_texts else "(none)"
        return self._ask(
            "[TEXT 1] lists CLUEs already given (or '(none)' if this is the "
            "first). Does [TEXT 2] (the new CLUE) add genuinely NEW information "
            "not already present in TEXT 1, rather than restating it in "
            "different words?",
            prior_block, new_text,
        )

    def judge_resolution(self, gap_text: str, candidate_text: str) -> JudgeVerdict:
        return self._ask(
            "[TEXT 1] is a GAP (a question the video raised). Does [TEXT 2] "
            "actually answer that specific question, rather than merely "
            "restating it or sharing its vocabulary?",
            gap_text, candidate_text,
        )

    def judge_payoff_reframing(self, prior_texts: list[str], payoff_text: str) -> JudgeVerdict:
        prior_block = "\n---\n".join(prior_texts) if prior_texts else "(none)"
        return self._ask(
            "[TEXT 1] lists the video's prior REVEAL/RESOLUTION statements. "
            "Does [TEXT 2] (the PAYOFF) synthesize or reframe that information "
            "in a new way, rather than simply repeating it?",
            prior_block, payoff_text,
        )

    def judge_overclaim(self, hook_text: str, strongest_evidence_text: str) -> JudgeVerdict:
        return self._ask(
            "[TEXT 1] is the video's hook/title/framing question. [TEXT 2] is "
            "the strongest evidence/resolution the video actually delivers. "
            "Does TEXT 1 make a stronger claim than TEXT 2 actually supports "
            "(an overclaim)? Answer FAIL if it overclaims, PASS if the claim "
            "is supported.",
            hook_text, strongest_evidence_text,
        )

    def judge_grounding_consistency(self, claim_text: str, tension_text: str) -> JudgeVerdict:
        return self._ask(
            "[TEXT 1] is a GroundedClaim's factual premise. [TEXT 2] is a "
            "VIOLATION/GAP built on it. Does TEXT 2 stay consistent with TEXT "
            "1's actual facts, or does it distort/exaggerate them into "
            "something TEXT 1 doesn't really support? Answer PASS if "
            "consistent, FAIL if it distorts the premise.",
            claim_text, tension_text,
        )


class ObservedEventEvidence(BaseModel):
    """What the real render/synthesis actually shows for one declared
    CognitiveEvent -- always DERIVED, never authored. `observed=False`
    means the event's scene_id/narration_unit_index didn't resolve to
    anything real in the actual scene_windows data (out of range, missing
    entirely, etc.); such an event counts toward NOTHING, independent of
    what judge_verdict says, because there is no real content to have
    judged. This is the direct fix for the exact failure Phase 0 found
    live in production: a manifest field (hook_type) that existed only on
    paper with zero connection to engine behavior.

    declared_status / observed_status / semantic_status (Phase 2 section 5)
    are reported SEPARATELY and are never collapsed into one PASS string --
    a caller must look at all three (plus `mismatches`) to know what
    actually happened to a given event. judge_verdict/judge_quote are kept
    for Phase 1 backward compatibility and are exactly semantic_status/
    semantic_quote's values."""
    model_config = _FORBID_EXTRA
    event_id: str
    observed: bool
    real_narration_text: str | None = None
    real_start: float | None = None
    real_end: float | None = None
    real_visual_cut_nearby: bool = False
    judge_verdict: str = JUDGE_NOT_EVALUATED
    judge_quote: str | None = None

    # Phase 2: explicit three-way status split (section 5).
    declared_status: str = "DECLARED"
    observed_status: str = "NOT_OBSERVED"
    semantic_status: str = JUDGE_NOT_EVALUATED
    semantic_quote: str | None = None
    semantic_reason: str | None = None
    mismatches: list[str] = Field(default_factory=list)

    # Phase 2: grounding-consistency is a SEPARATE assertion from
    # violation-integrity (both apply to VIOLATION/GAP events; they ask
    # different questions -- see entertainment_rules.ASSERTION_TYPES).
    grounding_consistency_verdict: str = JUDGE_NOT_EVALUATED
    grounding_consistency_quote: str | None = None

    # Phase 2: Observed Visual Evidence (section 4). All independently
    # false/None when the event declares no visual_beat_index at all.
    visual_beat_declared: bool = False
    visual_beat_observed: bool = False
    real_visual_cut_at: float | None = None
    real_visual_cut_matches_beat: bool = False
    visual_semantic_status: str | None = None


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
                             visual_cut_timestamps: list[float] | None = None,
                             scenes_by_id: dict | None = None,
                             semantic_visual_results: list[dict] | None = None) -> dict[str, ObservedEventEvidence]:
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
    whole video (final_video_qa.measure_visual_activity's own
    "cut_timestamps" output) -- used both for the Phase 1 diagnostic
    (real_visual_cut_nearby) and, new in Phase 2, to confirm a declared
    visual_beat_index actually produced a real cut near its expected time
    (real_visual_cut_matches_beat).

    scenes_by_id: {Scene.id: Scene} for THIS project, new in Phase 2 --
    needed to check a declared visual_beat_index actually exists in that
    scene's real visual_beats list. Optional; visual evidence is simply
    left unresolved (visual_beat_observed=False) if omitted.

    semantic_visual_results: the same list render() already builds by
    appending each scene's ClipSemanticVisionProvider (or other provider)
    result -- REUSED here, never recomputed, per Phase 2 section 4's
    explicit instruction not to duplicate existing semantic visual QA.
    Optional; each entry is expected to have "scene" and "status" keys.
    """
    windows_by_scene = {w.get("scene"): w for w in scene_windows}
    cuts = sorted(visual_cut_timestamps or [])
    scenes_by_id = scenes_by_id or {}
    visual_status_by_scene = {r["scene"]: r.get("status") for r in (semantic_visual_results or []) if "scene" in r}

    all_event_ids = {e.id for e in graph.events}
    events_by_id = {e.id: e for e in graph.events}

    # Resolve every event's real text/timing first (pure lookup, no
    # judging yet), so judge calls below can reference other events' real
    # text (e.g. a GAP's real wording, or earlier CLUEs' real text) instead
    # of their merely-declared text.
    real_text_by_id: dict[str, str | None] = {}
    real_start_by_id: dict[str, float | None] = {}
    real_end_by_id: dict[str, float | None] = {}
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
        real_end_by_id[e.id] = end
        observed_by_id[e.id] = observed

    evidence: dict[str, ObservedEventEvidence] = {}
    for e in graph.events:
        observed = observed_by_id[e.id]
        text = real_text_by_id[e.id]
        start = real_start_by_id[e.id]
        cut_nearby = False
        if observed and start is not None and cuts:
            cut_nearby = any(abs(c - start) <= _VISUAL_CUT_PROXIMITY_SECONDS for c in cuts)

        # --- Semantic verdict (Phase 1 method names kept; each maps to one
        # of entertainment_rules.ASSERTION_TYPES -- see SemanticJudge). ---
        verdict = JudgeVerdict(status=JUDGE_NOT_EVALUATED)
        if observed and text:
            if e.type == "VIOLATION":
                claim_texts = [c.text for c in graph.grounded_claims if c.id in e.grounded_claim_refs]
                claim_text = claim_texts[0] if claim_texts else ""
                verdict = _dispatch(judge, "judge_violation", claim_text, text,
                                     source_texts=(claim_text, text), valid_event_ids=all_event_ids)
            elif e.type == "CLUE" and e.resolves:
                prior_ids = [
                    o.id for o in graph.events
                    if o.resolves == e.resolves and o.type == "CLUE"
                    and graph.events.index(o) < graph.events.index(e)
                ]
                prior_texts = [t for t in (real_text_by_id.get(pid) for pid in prior_ids) if t]
                verdict = _dispatch(judge, "judge_clue_novelty", prior_texts, text,
                                     source_texts=tuple(prior_texts) + (text,), valid_event_ids=all_event_ids)
            elif e.type in ("RESOLUTION", "REVEAL") and e.resolves:
                gap = events_by_id.get(e.resolves)
                gap_text = (real_text_by_id.get(e.resolves) if gap and observed_by_id.get(e.resolves) else None) \
                    or (gap.text if gap else "")
                verdict = _dispatch(judge, "judge_resolution", gap_text, text,
                                     source_texts=(gap_text, text), valid_event_ids=all_event_ids)
            elif e.type == "PAYOFF":
                prior_ids = [o.id for o in graph.events if o.type in ("REVEAL", "RESOLUTION")]
                prior_texts = [t for t in (real_text_by_id.get(pid) for pid in prior_ids) if t]
                verdict = _dispatch(judge, "judge_payoff_reframing", prior_texts, text,
                                     source_texts=tuple(prior_texts) + (text,), valid_event_ids=all_event_ids)

        # --- Grounding consistency (Phase 2, F): a SEPARATE question from
        # violation-integrity above, asked of every grounded VIOLATION/GAP
        # regardless of its primary verdict. ---
        gc_verdict = JudgeVerdict(status=JUDGE_NOT_EVALUATED)
        if observed and text and e.type in REQUIRES_GROUNDING and e.grounded_claim_refs:
            claim_texts = [c.text for c in graph.grounded_claims if c.id in e.grounded_claim_refs]
            claim_text = claim_texts[0] if claim_texts else ""
            gc_verdict = _dispatch(judge, "judge_grounding_consistency", claim_text, text,
                                    source_texts=(claim_text, text), valid_event_ids=all_event_ids)

        # --- Observed Visual Evidence (Phase 2, section 4). ---
        visual_beat_declared = e.visual_beat_index is not None
        visual_beat_observed = False
        real_visual_cut_at = None
        real_visual_cut_matches_beat = False
        visual_semantic_status = visual_status_by_scene.get(e.scene_id)
        if visual_beat_declared:
            scene_obj = scenes_by_id.get(e.scene_id)
            window = windows_by_scene.get(e.scene_id)
            if scene_obj is not None and 0 <= e.visual_beat_index < len(getattr(scene_obj, "visual_beats", [])):
                visual_beat_observed = True
                beat = scene_obj.visual_beats[e.visual_beat_index]
                if window is not None:
                    expected_real_time = float(window.get("start", 0.0) or 0.0) + float(beat.start)
                    if cuts:
                        nearest = min(cuts, key=lambda c: abs(c - expected_real_time))
                        if abs(nearest - expected_real_time) <= _VISUAL_CUT_PROXIMITY_SECONDS:
                            real_visual_cut_at = nearest
                            real_visual_cut_matches_beat = True

        # --- Declared/Observed/Semantic status split + mismatch codes
        # (Phase 2, section 5). ---
        observed_status = "OBSERVED" if observed else "NOT_OBSERVED"
        mismatches: list[str] = []
        if not observed:
            mismatches.append(MISMATCH_NO_TIMING_EVIDENCE)
        elif text:
            overlap = token_overlap_ratio(e.text, text)
            if overlap < TEXT_DIVERGENCE_OVERLAP_FLOOR:
                mismatches.append(MISMATCH_TEXT_DIVERGES_FROM_NARRATION)
        if visual_beat_declared and not visual_beat_observed:
            mismatches.append(MISMATCH_VISUAL_BEAT_MISSING)
        if e.type == "CLUE" and verdict.status == JUDGE_FAIL:
            mismatches.append(MISMATCH_CLUE_NO_NEW_INFORMATION)
        if e.type in ("RESOLUTION", "REVEAL") and verdict.status == JUDGE_FAIL:
            mismatches.append(MISMATCH_RESOLUTION_DOES_NOT_FULFILL_GAP)
        if e.type == "PAYOFF" and verdict.status == JUDGE_FAIL:
            mismatches.append(MISMATCH_PAYOFF_MERE_REPETITION)
        if e.type == "VIOLATION" and verdict.status == JUDGE_FAIL:
            mismatches.append(MISMATCH_VIOLATION_NO_CONTRADICTION)

        evidence[e.id] = ObservedEventEvidence(
            event_id=e.id, observed=observed,
            real_narration_text=text, real_start=start, real_end=real_end_by_id.get(e.id),
            real_visual_cut_nearby=cut_nearby,
            judge_verdict=verdict.status, judge_quote=verdict.quote,
            declared_status="DECLARED", observed_status=observed_status,
            semantic_status=verdict.status, semantic_quote=verdict.quote, semantic_reason=verdict.reason,
            mismatches=mismatches,
            grounding_consistency_verdict=gc_verdict.status, grounding_consistency_quote=gc_verdict.quote,
            visual_beat_declared=visual_beat_declared, visual_beat_observed=visual_beat_observed,
            real_visual_cut_at=real_visual_cut_at, real_visual_cut_matches_beat=real_visual_cut_matches_beat,
            visual_semantic_status=visual_semantic_status,
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
    must be 0 by the end of the video. Report-only (see module docstring) --
    this function's own 'status' is diagnostic, never wired into
    final_video_qa's overall PASS/FAIL."""
    unresolved = [l for l in loops if l.critical and not l.fulfilled]
    return {
        "status": "PASS" if not unresolved else "FAIL",
        "unresolved_critical_gap_count": len(unresolved),
        "unresolved_critical_gap_ids": [l.gap_id for l in unresolved],
    }


def evaluate_overclaim(project, graph, evidence_by_id: dict[str, ObservedEventEvidence], judge: SemanticJudge) -> dict:
    """Assertion E (OVERCLAIM): does the video's own hook/title/framing
    question claim more than the evidence it actually delivers supports.

    NOT_EVALUATED (not FAIL) when there isn't yet enough REAL delivered
    evidence to compare against -- "no evidence delivered at all" is
    already a different, separately-reported failure
    (unresolved_critical_gap_count); OVERCLAIM only has an opinion about
    whether delivered evidence undersells or oversells relative to the
    hook, so it needs at least one real, judge-confirmed piece of evidence
    to ask that question honestly."""
    hook_parts = []
    if getattr(project, "title", None):
        hook_parts.append(project.title)
    for e in graph.events:
        if e.type == "GAP":
            ev = evidence_by_id.get(e.id)
            if ev and ev.observed and ev.real_narration_text:
                hook_parts.append(ev.real_narration_text)
    hook_text = " / ".join(hook_parts)

    evidence_parts = []
    for e in graph.events:
        if e.type in ("RESOLUTION", "REVEAL", "PAYOFF"):
            ev = evidence_by_id.get(e.id)
            if ev and ev.observed and ev.judge_verdict == JUDGE_PASS and ev.real_narration_text:
                evidence_parts.append(ev.real_narration_text)
    evidence_text = " / ".join(evidence_parts)

    if not hook_text or not evidence_text:
        return {
            "status": JUDGE_NOT_EVALUATED, "quote": None,
            "reason": "insufficient real hook and/or judge-confirmed delivered-evidence text to compare",
            "hook_text": hook_text or None, "evidence_text": evidence_text or None,
        }

    verdict = _dispatch(judge, "judge_overclaim", hook_text, evidence_text,
                         source_texts=(hook_text, evidence_text), valid_event_ids=None)
    return {"status": verdict.status, "quote": verdict.quote, "reason": verdict.reason,
            "hook_text": hook_text, "evidence_text": evidence_text}


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


def compute_processing_fluency_diagnostics(evidence_by_id: dict[str, ObservedEventEvidence]) -> dict:
    """Soft, report-only diagnostics on how demanding the REAL (observed)
    narration text is to parse -- character length and comma-delimited
    clause count per observed unit. This is deliberately NOT a "readability
    score", is never a gate, and never feeds into any PASS/FAIL: cognitive
    fluency research suggests very easy-to-parse text aids comprehension,
    but this module has no way to know whether a given script SHOULD be
    simple (a quick fact) or complex (a deliberately dense reveal), so it
    only reports raw numbers a human can interpret in context -- the same
    "diagnostic, not verdict" stance as compute_entertainment_diagnostics."""
    lengths = []
    clause_counts = []
    for ev in evidence_by_id.values():
        if not (ev.observed and ev.real_narration_text):
            continue
        text = ev.real_narration_text
        lengths.append(len(text))
        clause_counts.append(text.count(",") + text.count("、") + 1)
    if not lengths:
        return {"observed_unit_count": 0, "average_length_chars": None,
                "max_length_chars": None, "average_clause_count": None}
    return {
        "observed_unit_count": len(lengths),
        "average_length_chars": sum(lengths) / len(lengths),
        "max_length_chars": max(lengths),
        "average_clause_count": sum(clause_counts) / len(clause_counts),
    }


def _assertions_by_type(graph, evidence_by_id: dict[str, ObservedEventEvidence], overclaim_result: dict) -> dict:
    """Groups every judged event by which of the six Phase 2 assertion
    types it was evaluated under -- the explicit per-assertion breakdown
    Phase 2 section 8 asks the Train Wheels V2 pilot report to surface."""
    by_assertion: dict[str, list[dict]] = {
        ASSERTION_VIOLATION_INTEGRITY: [], ASSERTION_CLUE_NOVELTY: [],
        ASSERTION_GAP_FULFILLMENT: [], ASSERTION_PAYOFF_REFRAMING: [],
        ASSERTION_GROUNDING_CONSISTENCY: [],
    }
    type_to_assertion = {
        "VIOLATION": ASSERTION_VIOLATION_INTEGRITY, "CLUE": ASSERTION_CLUE_NOVELTY,
        "RESOLUTION": ASSERTION_GAP_FULFILLMENT, "REVEAL": ASSERTION_GAP_FULFILLMENT,
        "PAYOFF": ASSERTION_PAYOFF_REFRAMING,
    }
    for e in graph.events:
        ev = evidence_by_id.get(e.id)
        if ev is None:
            continue
        assertion = type_to_assertion.get(e.type)
        if assertion:
            by_assertion[assertion].append({
                "event_id": e.id, "status": ev.semantic_status, "quote": ev.semantic_quote, "reason": ev.semantic_reason,
            })
        if e.type in REQUIRES_GROUNDING and e.grounded_claim_refs:
            by_assertion[ASSERTION_GROUNDING_CONSISTENCY].append({
                "event_id": e.id, "status": ev.grounding_consistency_verdict, "quote": ev.grounding_consistency_quote,
            })
    by_assertion[ASSERTION_OVERCLAIM] = [overclaim_result]
    return by_assertion


def run_entertainment_contract_report(project, scene_windows: list[dict], judge: SemanticJudge | None = None,
                                       visual_cut_timestamps: list[float] | None = None,
                                       semantic_visual_results: list[dict] | None = None) -> dict | None:
    """The Phase 2 aggregate. Returns None (nothing to report) when the
    project declares no event_graph -- every existing production manifest
    (Comet, Radium Girls, Titanic, Train Wheels) takes this path and is
    completely unaffected.

    REPORT-ONLY, unconditionally, through Phase 2: the returned dict's own
    "status" fields are informational only. Callers (render.py) must attach
    this under qa_report.json's top-level "entertainment_contract" key,
    OUTSIDE final_video_qa's `checks` dict, so it can never affect
    `overall` PASS/FAIL no matter what it finds -- see
    models.Project.strict_entertainment_contract's docstring for why this
    is deliberate at this phase, not an oversight.

    `human_review_required` is always True -- see this module's docstring
    and HUMAN_REVIEW_EXCLUSIONS. A PASS anywhere in this report means only
    PEC_PASS_MEANING, never "this video is entertaining"."""
    graph = getattr(project, "event_graph", None)
    if graph is None:
        return None
    judge = judge or NullJudge()
    scenes_by_id = {s.id: s for s in getattr(project, "scenes", [])}
    evidence = build_observed_evidence(graph, scene_windows, judge, visual_cut_timestamps,
                                        scenes_by_id=scenes_by_id, semantic_visual_results=semantic_visual_results)
    loops = compute_curiosity_loops(graph, evidence)
    gap_check = verify_unresolved_critical_gaps(loops)
    diagnostics = compute_entertainment_diagnostics(graph, loops)
    processing_fluency = compute_processing_fluency_diagnostics(evidence)
    overclaim_result = evaluate_overclaim(project, graph, evidence, judge)
    return {
        "mode": "report-only",
        "strict_entertainment_contract": bool(getattr(project, "strict_entertainment_contract", False)),
        "pec_pass_meaning": PEC_PASS_MEANING,
        "human_review_required": True,
        "human_review_exclusions": list(HUMAN_REVIEW_EXCLUSIONS),
        "unresolved_critical_gaps": gap_check,
        "curiosity_loops": [loop.model_dump() for loop in loops],
        "observed_evidence": {eid: ev.model_dump() for eid, ev in evidence.items()},
        "assertions": _assertions_by_type(graph, evidence, overclaim_result),
        "overclaim": overclaim_result,
        "diagnostics": diagnostics,
        "processing_fluency": processing_fluency,
    }
