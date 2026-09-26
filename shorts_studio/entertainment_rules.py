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
