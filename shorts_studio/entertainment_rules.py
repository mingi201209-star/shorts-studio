"""Shared constants and deterministic helpers for the Psychological
Entertainment Contract (Layer 2). Mirrors retention_rules.py's role: keep
every rule inspectable and testable, and keep a hard line between what is
deterministic (reference integrity, graph structure, presence/absence) and
what requires real reading comprehension (handed to a SemanticJudge, never
approximated here with more keyword/overlap heuristics).

Core invariant this whole layer exists to enforce (see entertainment_qa.py):
declared metadata alone can never prove entertainment success. A
CognitiveEvent that exists only in the manifest, with no corresponding
Observed Event Evidence from the real narration/render, counts for nothing.
"""
from __future__ import annotations

# The eight event types this layer's Declared Event Graph is built from.
# Deliberately smaller than early brainstorming lists (see the PEC design
# report): FAMILIARITY folded into CLAIM, VIEWER_HYPOTHESIS/HYPOTHESIS_
# REJECTION folded into VIOLATION/CLUE -- each of those splits was judged,
# on review, to force padding to fill a slot a real script doesn't need.
EVENT_TYPES = ("CLAIM", "VIOLATION", "GAP", "CLUE", "REVEAL", "RESOLUTION", "RELAY", "PAYOFF")

# Only these two event types make a factual claim about the world that a
# viewer could reasonably ask "says who?" about -- these are the ones that
# must trace to a GroundedClaim with a real source_ref. CLAIM itself is
# allowed to be ungrounded scene-setting ("familiar" context); it is
# VIOLATION/GAP -- the events that introduce tension -- that must be
# sourced, per the anti-clickbait invariant (a twist not grounded in
# declared facts must fail, not just an accepted CLAIM).
REQUIRES_GROUNDING = ("VIOLATION", "GAP")

# Event types whose real-world fulfillment must be confirmed by the
# evidence-quoting semantic judge before they can count toward closing a
# GAP -- never by lexical overlap alone (see JudgeVerdict / SemanticJudge
# in entertainment_qa.py). A CLUE/REVEAL/RESOLUTION that references a GAP
# but whose judge verdict is not PASS does not close that gap.
GAP_CLOSING_TYPES = ("CLUE", "REVEAL", "RESOLUTION")

# The only three verdicts a SemanticJudge may return. No numeric score --
# see JudgeVerdict's docstring for why. NOT_EVALUATED is not a pass: an
# event whose judge verdict is NOT_EVALUATED cannot close a GAP, exactly
# like ClipSemanticVisionProvider's existing "an inconclusive semantic
# check must not be promoted to PASS by anything else" pattern.
JUDGE_PASS = "PASS"
JUDGE_FAIL = "FAIL"
JUDGE_NOT_EVALUATED = "NOT_EVALUATED"
JUDGE_VERDICTS = (JUDGE_PASS, JUDGE_FAIL, JUDGE_NOT_EVALUATED)

# ---------------------------------------------------------------------------
# Phase 2: the six narrow, independent assertion types a SemanticJudge is
# ever asked about. Each is a yes/no question about ONE specific pair of
# real texts -- never "is this video fun/good/a 10". See
# entertainment_qa.SemanticJudge for the method each maps to.
# ---------------------------------------------------------------------------
ASSERTION_VIOLATION_INTEGRITY = "VIOLATION_INTEGRITY"    # A -- judge_violation
ASSERTION_CLUE_NOVELTY = "CLUE_NOVELTY"                  # B -- judge_clue_novelty
ASSERTION_GAP_FULFILLMENT = "GAP_FULFILLMENT"            # C -- judge_resolution
ASSERTION_PAYOFF_REFRAMING = "PAYOFF_REFRAMING"          # D -- judge_payoff_reframing
ASSERTION_OVERCLAIM = "OVERCLAIM"                        # E -- judge_overclaim
ASSERTION_GROUNDING_CONSISTENCY = "GROUNDING_CONSISTENCY"  # F -- judge_grounding_consistency
ASSERTION_TYPES = (
    ASSERTION_VIOLATION_INTEGRITY, ASSERTION_CLUE_NOVELTY, ASSERTION_GAP_FULFILLMENT,
    ASSERTION_PAYOFF_REFRAMING, ASSERTION_OVERCLAIM, ASSERTION_GROUNDING_CONSISTENCY,
)

# Wall-clock budget for a single judge method call, enforced by
# entertainment_qa._call_judge_safely regardless of which SemanticJudge
# implementation is plugged in. A judge that hangs (network stall, a stuck
# model call) must NOT_EVALUATED, never block the report or fail open.
JUDGE_CALL_TIMEOUT_SECONDS = 12.0

# Declared/Observed/Semantic mismatch codes (Phase 2 section 5). Each names
# ONE specific way a CognitiveEvent's declaration diverged from what the
# real render/judge actually showed. Never collapsed into a single PASS/FAIL
# string -- see ObservedEventEvidence.mismatches.
MISMATCH_TEXT_DIVERGES_FROM_NARRATION = "TEXT_DIVERGES_FROM_ACTUAL_NARRATION"
MISMATCH_VISUAL_BEAT_MISSING = "VISUAL_BEAT_MISSING"
MISMATCH_CLUE_NO_NEW_INFORMATION = "CLUE_NO_NEW_INFORMATION"
MISMATCH_RESOLUTION_DOES_NOT_FULFILL_GAP = "RESOLUTION_DOES_NOT_FULFILL_GAP"
MISMATCH_PAYOFF_MERE_REPETITION = "PAYOFF_MERE_REPETITION"
MISMATCH_VIOLATION_NO_CONTRADICTION = "VIOLATION_NO_CONTRADICTION"
MISMATCH_NO_TIMING_EVIDENCE = "NO_TIMING_EVIDENCE"

# A COARSE structural sanity floor only -- flags declared text so unlike the
# real synthesized narration that they are almost certainly not the same
# sentence (stale manifest, copy-paste error, wrong narration_unit_index).
# This is NEVER used to decide semantic fulfillment (see
# entertainment_qa.py's module docstring's repeated warning against
# reintroducing lexical overlap as a fulfillment gate) -- it only catches
# gross divergence a human proofreading the manifest against the real
# script would immediately notice.
TEXT_DIVERGENCE_OVERLAP_FLOOR = 0.15
