"""Prompt V2: hook and story generation, with generation deliberately
separated from judging.

Product principle this module exists to enforce (see the request that
created it): PROMPTS create quality; QA prevents regressions. The engine
already had a growing stack of post-hoc detectors (crop/zoom equivalence,
meaningful-visual-change, source-diversity, the retention/PEC contracts) --
all of them necessary, none of them able to make a boring hook interesting.
Real audience data on a recent production (train wheel conicity: ~1.1K
views, ~34s average view duration, ~38.8% viewed vs ~61.1% swiped away,
near-zero comments) points at the opening and the overall curiosity pull,
not at anything a QA gate can catch -- the video technically passed every
existing check. This module is the smallest architectural change that gives
better PROMPTING real, testable influence over what gets produced, instead
of adding yet another QA rule that can only reject bad output after the
fact, never manufacture a good one.

Two independent stages, mirroring entertainment_qa.py's SemanticJudge
pattern exactly (Protocol interface, a deterministic default, an optional
real-model-call implementation that fails closed to the deterministic
default when unavailable -- no API key is configured or invented here):

  1. Generation (HookGenerator): turns a structured TopicBrief into several
     genuinely different, strategy-tagged HookCandidates. The default
     TemplateHookGenerator is deterministic and offline; it exists so
     "generate multiple candidates, then judge them" is a real, always-
     runnable, testable step for every topic, not something that only
     happens when a human author remembers to do it by hand.

  2. Judging (HookJudge): NEVER lets a generator's first output silently
     become the winner. RuleBasedHookJudge filters every candidate through
     reject_hook_candidate (the concrete rejection rules a real hook must
     survive) and scores the survivors independently. AnthropicHookJudge is
     a genuinely separate model call (reusing entertainment_qa's own lazy
     Anthropic client loader) that re-ranks whatever RuleBasedHookJudge
     already let survive -- it can only break ties among structurally valid
     candidates, never override a rejection. Both implement the same
     HookJudge Protocol, so a future external judge (e.g. Jev) can be
     plugged in with zero change to generate_and_judge or its callers; no
     such integration is added here.

Story Prompt V2 (verify_curiosity_maintained) builds on the EXISTING
role-tagged narration_plan infrastructure (models.NarrationPhrase.role,
final_video_qa.verify_story_progression/verify_ending_payoff_role) instead
of inventing a parallel scheme, and is a strictly ADDITIONAL, stricter check
-- every existing gate stays exactly as strict as before.
"""
from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import entertainment_qa as _eqa
from .retention_rules import (
    hook_violation, is_generic_establishing_text,
    is_bare_why_question, reveals_payoff_prematurely, tension_marker_strength,
    token_overlap_ratio, normalize_text,
)

_FORBID_EXTRA = ConfigDict(extra="forbid")

# The six mechanisms requirement 2 names, chosen to produce an immediate
# "wait, what? then why/how?" reaction rather than a topic announcement.
# Each maps 1:1 onto a retention_rules.HOOK_TYPES member (contradiction and
# visible_anomaly already existed there; the other four were added
# alongside these for exactly this module).
HOOK_STRATEGIES = (
    "contradiction", "surprising_consequence", "counterintuitive_fact",
    "visible_anomaly", "mistaken_assumption", "unresolved_cause_effect",
)

# A topic with fewer than this many real strategy facts cannot produce
# genuinely different candidates -- generate_and_judge refuses rather than
# padding with paraphrases of one angle (requirement 4).
MIN_STRATEGY_FACTS = 3


class TopicBrief(BaseModel):
    """Structured input Prompt V2 generates hook candidates FROM -- written
    before any hook sentence is drafted, mirroring idea_gate.IdeaPitch's own
    "judge the structure before the prose" precedent. Each `*_fact` field is
    optional (not every topic naturally supports all six strategies), but
    generate_and_judge refuses to run below MIN_STRATEGY_FACTS distinct
    ones. `payoff_text` and `grounded_facts` exist so candidates can be
    checked against real content instead of trusted on the generator's own
    say-so: `reject_hook_candidate` rejects a candidate that already reveals
    `payoff_text`, and `is_grounded_claim` rejects one whose claimed
    grounding isn't traceable to anything actually declared here."""
    model_config = _FORBID_EXTRA
    topic_id: str = Field(min_length=1)
    familiar_subject: str = Field(min_length=1, description="the everyday thing/situation the viewer already recognizes")
    contradiction_fact: str | None = None
    surprising_consequence_fact: str | None = None
    counterintuitive_fact: str | None = None
    anomaly_fact: str | None = None
    mistaken_assumption_fact: str | None = None
    cause_effect_fact: str | None = None
    payoff_text: str = Field(min_length=1, description="the strongest explanatory/payoff line the story actually delivers")
    grounded_facts: list[str] = Field(default_factory=list, description="additional real, source-backed facts available for this topic")

    def fact_by_strategy(self) -> dict[str, str | None]:
        return {
            "contradiction": self.contradiction_fact,
            "surprising_consequence": self.surprising_consequence_fact,
            "counterintuitive_fact": self.counterintuitive_fact,
            "visible_anomaly": self.anomaly_fact,
            "mistaken_assumption": self.mistaken_assumption_fact,
            "unresolved_cause_effect": self.cause_effect_fact,
        }

    def available_strategies(self) -> list[str]:
        return [s for s, fact in self.fact_by_strategy().items() if fact and fact.strip()]

    def all_declared_facts(self) -> list[str]:
        facts = list(self.fact_by_strategy().values())
        facts.append(self.payoff_text)
        facts.extend(self.grounded_facts)
        return [f for f in facts if f and f.strip()]


class HookCandidate(BaseModel):
    model_config = _FORBID_EXTRA
    strategy: str
    text: str = Field(min_length=1)
    grounded_in: str = Field(min_length=1, description="the exact fact text this candidate is built from")

    @model_validator(mode="after")
    def _valid_strategy(self):
        if self.strategy not in HOOK_STRATEGIES:
            raise ValueError(f"strategy must be one of {HOOK_STRATEGIES}, got {self.strategy!r}")
        return self


def is_grounded_claim(candidate: HookCandidate, brief: TopicBrief, threshold: float = 0.6) -> bool:
    """A candidate's claimed grounding must genuinely correspond to
    something the author actually declared as real for this topic -- never
    trust a generator's own claim that a candidate is grounded (requirement
    3: no unsupported sensationalism). Uses the same token-overlap-ratio
    near-duplicate proxy the rest of the engine relies on, not exact string
    equality, so minor rephrasing of a declared fact still counts."""
    facts = brief.all_declared_facts()
    return any(token_overlap_ratio(candidate.grounded_in, f) >= threshold for f in facts)


def reject_hook_candidate(candidate: HookCandidate, brief: TopicBrief) -> str | None:
    """Requirement-5 rejection rules, layered ON TOP of (never replacing)
    the existing Layer-1 hook_violation/has_tension_marker contract. Returns
    a short reason string, or None if the candidate survives to judging."""
    text = candidate.text.strip()

    reason = hook_violation(text)
    if reason:
        return f"Layer-1 hook contract violation: {reason}"

    if is_bare_why_question(text):
        return "ordinary 'why does X happen' question with no information gap beyond the trailing question mark"

    if is_generic_establishing_text(text):
        return "reads as a generic establishing statement"

    if reveals_payoff_prematurely(text, brief.payoff_text):
        return "gives away the ending payoff immediately, leaving no information gap"

    # Per-token substring, not whole-phrase substring or whitespace-token
    # overlap: Korean particles attach directly to a noun with no space
    # (e.g. "유리컵인데"), so exact whitespace-token matching would wrongly
    # treat that as zero overlap with the bare noun "유리컵"; and a natural
    # sentence rarely repeats a multi-word familiar_subject phrase verbatim
    # in the same word order, so requiring the whole phrase as one
    # contiguous substring is too strict for a multi-word subject. Checking
    # each subject token as a substring (so "냉동실에" still matches inside
    # "냉동실에서") catches both cases; only true "shares nothing at all"
    # candidates are rejected here.
    normalized_text = normalize_text(text)
    subject_tokens = normalize_text(brief.familiar_subject).split()
    if subject_tokens and not any(tok in normalized_text for tok in subject_tokens):
        return "shares no reference to the familiar subject -- requires the viewer to already know what this is about"

    if not is_grounded_claim(candidate, brief):
        return "claimed grounding is not traceable to any fact actually declared for this topic (unsupported sensationalism)"

    return None


class CandidateVerdict(BaseModel):
    model_config = _FORBID_EXTRA
    candidate: HookCandidate
    status: str  # SURVIVED | REJECTED
    reason: str | None = None
    score: float | None = None


class HookJudgeResult(BaseModel):
    model_config = _FORBID_EXTRA
    verdicts: list[CandidateVerdict]
    winner: HookCandidate | None = None
    judge_name: str = "rule_based"

    @property
    def survivors(self) -> list[CandidateVerdict]:
        return [v for v in self.verdicts if v.status == "SURVIVED"]


class HookGenerator(Protocol):
    """Generation stage. Must produce candidates covering more than one
    strategy -- see generate_and_judge, which enforces this regardless of
    which generator is plugged in."""
    def generate(self, brief: TopicBrief) -> list[HookCandidate]: ...


_STRATEGY_TEMPLATES = {
    "contradiction": "{subject}, 하지만 {fact}",
    "surprising_consequence": "놀랍게도, {subject} 때문에 {fact}",
    "counterintuitive_fact": "{subject}인데, 사실은 {fact}",
    "visible_anomaly": "{subject}를 자세히 보면, 이상하게도 {fact}",
    "mistaken_assumption": "많은 사람들이 {subject}에 대해 착각합니다 — 사실은 {fact}",
    "unresolved_cause_effect": "{fact}. 그런데 왜 {subject}일까?",
}


class TemplateHookGenerator:
    """Deterministic, offline, always-available default generator: turns a
    TopicBrief's strategy facts into strategy-tagged candidate sentences via
    fixed templates. This is NOT meant to be the final polished narration
    line for a real production -- a human/agent author still writes the
    actual delivered Korean sentence for whichever strategy the judge picks
    -- its job is to make "generate several genuinely different candidates,
    then judge them" a real, runnable, testable step for every topic, every
    time, across every available strategy, instead of a single unexamined
    first draft."""
    def generate(self, brief: TopicBrief) -> list[HookCandidate]:
        candidates = []
        for strategy, fact in brief.fact_by_strategy().items():
            if not fact or not fact.strip():
                continue
            text = _STRATEGY_TEMPLATES[strategy].format(subject=brief.familiar_subject, fact=fact.strip())
            candidates.append(HookCandidate(strategy=strategy, text=text, grounded_in=fact.strip()))
        return candidates


_STRATEGY_PRIORITY = {
    "surprising_consequence": 3, "contradiction": 3, "counterintuitive_fact": 2,
    "visible_anomaly": 2, "mistaken_assumption": 2, "unresolved_cause_effect": 1,
}


def _score_candidate(candidate: HookCandidate) -> float:
    strategy_score = _STRATEGY_PRIORITY.get(candidate.strategy, 0)
    tension_score = tension_marker_strength(candidate.text)
    length_penalty = max(0, len(candidate.text) - 40) * 0.02
    return strategy_score + tension_score - length_penalty


class HookJudge(Protocol):
    """Judging stage. NEVER sees only a single candidate treated as a
    foregone winner -- always the full list, and must return an explicit
    per-candidate verdict plus at most one winner. Designed so a future
    external judge (e.g. Jev) can implement this same Protocol and be
    swapped in for RuleBasedHookJudge/AnthropicHookJudge with no change to
    generate_and_judge or its callers -- mirrors entertainment_qa.
    SemanticJudge's identical pattern. Not wired to any real Jev integration
    or API key in this change."""
    def judge(self, candidates: list[HookCandidate], brief: TopicBrief) -> HookJudgeResult: ...


class RuleBasedHookJudge:
    """Default, deterministic, offline judge. Filters every candidate
    through reject_hook_candidate first, then scores ONLY the survivors and
    picks the highest score -- ties broken by strategy priority, then by
    HOOK_STRATEGIES' own declared order, never by candidate-list position,
    so a generator cannot game the winner by simply listing its preferred
    candidate first (requirement 6: no single-pass self-declared winner)."""
    def judge(self, candidates: list[HookCandidate], brief: TopicBrief) -> HookJudgeResult:
        verdicts: list[CandidateVerdict] = []
        ranked: list[tuple[float, int, HookCandidate]] = []
        for c in candidates:
            reason = reject_hook_candidate(c, brief)
            if reason:
                verdicts.append(CandidateVerdict(candidate=c, status="REJECTED", reason=reason))
            else:
                score = _score_candidate(c)
                verdicts.append(CandidateVerdict(candidate=c, status="SURVIVED", score=score))
                ranked.append((score, HOOK_STRATEGIES.index(c.strategy), c))
        winner = None
        if ranked:
            ranked.sort(key=lambda t: (-t[0], t[1]))
            winner = ranked[0][2]
        return HookJudgeResult(verdicts=verdicts, winner=winner, judge_name="rule_based")


_HOOK_JUDGE_SYSTEM_PROMPT = (
    "You are choosing the single strongest opening hook line for a short "
    "video from a list of candidates that already passed structural "
    "screening. Pick the one most likely to make a viewer scrolling past "
    "think 'wait, what? then why/how?' within one second, without giving "
    "away the ending. Respond with ONLY a JSON object: "
    "{\"winner_index\": <int>, \"reason\": \"<one short sentence>\"}. "
    "winner_index is the 0-based index into the given candidate list. Never "
    "invent a candidate; choose only among the ones given."
)


class AnthropicHookJudge:
    """A genuinely separate model call for the judging stage (requirement
    6), reusing entertainment_qa's own lazy Anthropic client loader exactly
    -- no API key is configured or invented by this change. With zero or one
    surviving candidate there's nothing to rank, so it defers to
    RuleBasedHookJudge without a network call. When no client is available
    (package missing / no ANTHROPIC_API_KEY, the common case in this
    environment) or the call fails/returns something unusable, it falls
    back to RuleBasedHookJudge's own winner -- it can only re-rank
    candidates that already survived the deterministic rejection rules; it
    can never override a structural rejection or resurrect a rejected
    candidate."""
    def __init__(self, client=None):
        self._client = client

    def _client_or_none(self):
        if self._client is not None:
            return self._client
        return _eqa._load_anthropic_client()

    def judge(self, candidates: list[HookCandidate], brief: TopicBrief) -> HookJudgeResult:
        base = RuleBasedHookJudge().judge(candidates, brief)
        survivors = base.survivors
        if len(survivors) <= 1:
            return HookJudgeResult(verdicts=base.verdicts, winner=base.winner, judge_name="anthropic_trivial_fallback_rule_based")
        client = self._client_or_none()
        if client is None:
            return HookJudgeResult(verdicts=base.verdicts, winner=base.winner, judge_name="anthropic_unavailable_fallback_rule_based")
        options = "\n".join(f"[{i}] ({v.candidate.strategy}) {v.candidate.text}" for i, v in enumerate(survivors))
        try:
            raw = _eqa._call_anthropic_messages(client, _HOOK_JUDGE_SYSTEM_PROMPT, options)
            import json
            data = json.loads(raw)
            idx = int(data["winner_index"])
            if 0 <= idx < len(survivors):
                return HookJudgeResult(verdicts=base.verdicts, winner=survivors[idx].candidate, judge_name="anthropic")
        except Exception:
            pass
        return HookJudgeResult(verdicts=base.verdicts, winner=base.winner, judge_name="anthropic_call_failed_fallback_rule_based")


def generate_and_judge(brief: TopicBrief, generator: HookGenerator | None = None,
                        judge: HookJudge | None = None) -> HookJudgeResult:
    """The Prompt V2 orchestrator: ALWAYS two separate stages, generation
    then judging (requirement 6) -- no code path lets a generator's first
    output become the winner without passing through a judge. Raises
    ValueError if the brief doesn't supply enough distinct strategy facts to
    produce genuinely different candidates (requirement 4): a topic with
    only one real angle cannot be forced into several paraphrases of it."""
    available = brief.available_strategies()
    if len(available) < MIN_STRATEGY_FACTS:
        raise ValueError(
            f"TopicBrief {brief.topic_id!r} declares only {len(available)} strategy fact(s) "
            f"{available} -- need >= {MIN_STRATEGY_FACTS} distinct strategies to generate "
            "genuinely different hook candidates, not paraphrases of one angle"
        )
    generator = generator or TemplateHookGenerator()
    judge = judge or RuleBasedHookJudge()
    candidates = generator.generate(brief)
    if len({c.strategy for c in candidates}) < MIN_STRATEGY_FACTS:
        raise ValueError("generator produced fewer than MIN_STRATEGY_FACTS distinct strategies")
    return judge.judge(candidates, brief)


# ---------------------------------------------------------------------------
# Story Prompt V2 (requirement 7): maintain curiosity instead of immediately
# dumping the explanation. Builds on the EXISTING role-tagged narration_plan
# infrastructure (models.NarrationPhrase.role, final_video_qa.
# verify_story_progression / verify_ending_payoff_role) rather than
# inventing a parallel scheme. Strictly ADDITIONAL: every existing gate
# keeps exactly the behavior it had before this module existed.
# ---------------------------------------------------------------------------

_EXPLANATION_ROLES = ("EXPLANATION", "REVEAL", "PAYOFF")


def verify_curiosity_maintained(project) -> dict:
    """FAIL if the SECOND distinct narrative role in the video is already an
    explanation/reveal/payoff role -- i.e. the script jumps straight from
    HOOK to giving the answer away, with no intervening evidence/clue beat
    for the viewer to sit with the question.

    final_video_qa.verify_story_progression does NOT catch this: HOOK ->
    EXPLANATION -> CRISIS -> PAYOFF already satisfies its own '>=4 distinct
    roles, HOOK first, no stagnant scene' rule despite dumping the
    explanation in the second beat. This function checks the specific shape
    requirement 7 describes (HOOK -> evidence/clue -> partial explanation ->
    new implication/re-hook -> strongest explanatory/payoff moment ->
    ending) without forcing a rigid fixed-length template: only the 'HOOK
    first' and 'not explained in the very next beat' transitions are
    checked, plus that a genuine explanation/reveal/payoff role appears
    somewhere before the end. Does not replace verify_ending_payoff_role's
    own PAYOFF/REVEAL-last check -- callers should run both."""
    roles: list[str] = []
    for scene in project.scenes:
        for phrase in getattr(scene, "narration_plan", None) or []:
            if not roles or roles[-1] != phrase.role:
                roles.append(phrase.role)
    if not roles:
        return {"status": "FAIL", "reason": "no narration_plan roles declared"}
    if roles[0] != "HOOK":
        return {"status": "FAIL", "reason": f"first role is '{roles[0]}', must be HOOK", "evidence": {"role_sequence": roles}}
    if len(roles) < 2:
        return {"status": "FAIL", "reason": "only one distinct role used -- no story progression at all", "evidence": {"role_sequence": roles}}
    if roles[1] in _EXPLANATION_ROLES:
        return {
            "status": "FAIL",
            "reason": f"second role is '{roles[1]}' -- the explanation/reveal/payoff is dumped immediately "
                       "after the hook, with no evidence/clue beat maintaining curiosity",
            "evidence": {"role_sequence": roles},
        }
    if not any(r in _EXPLANATION_ROLES for r in roles):
        return {"status": "FAIL", "reason": "no EXPLANATION/REVEAL/PAYOFF role ever appears -- the video never actually explains anything",
                "evidence": {"role_sequence": roles}}
    return {"status": "PASS", "evidence": {"role_sequence": roles}}
