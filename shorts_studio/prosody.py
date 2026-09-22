"""Korean Prosody Planner V1.

The V1 TTS pipeline treated Korean delivery as voice + a single global rate/
pitch + splitting written sentences into synthesis units, each followed by
the SAME fixed silence. That reads as flat and mechanical regardless of what
is actually being said. This module adds a structured, narrative-role-aware
representation that the synthesis engine (see tts.synthesize_plan) consumes,
so pacing and pausing adapt to CONTEXT instead of being uniform.

This is engine-level, not Comet-specific: any manifest can declare a
Scene.narration_plan of PhraseSpec entries; a scene without one falls back to
build_auto_plan(), which reproduces the old whole-sentence behavior so
existing manifests/tests keep working unchanged.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

NARRATIVE_ROLES = ("HOOK", "SETUP", "CRISIS", "INVESTIGATION", "REVEAL", "EXPLANATION", "PAYOFF")
BOUNDARIES = ("continuation", "weak", "medium", "strong", "anticipatory", "terminal")

@dataclass(frozen=True)
class PhraseSpec:
    role: str
    text: str
    boundary: str = "terminal"     # what kind of break follows THIS phrase
    focus: bool = False            # the emphasis/result target (e.g. a REVEAL's payload)
    pace: str | None = None        # optional explicit rate override, e.g. "+2%"

# Pause AFTER a phrase, keyed by (role, boundary). Deliberately varied --
# never the same fixed silence for every phrase. Falls back to
# DEFAULT_PAUSE_BY_BOUNDARY when a role has no specific override.
PAUSE_SECONDS: dict[tuple[str, str], float] = {
    ("HOOK", "weak"): 0.10,
    ("HOOK", "medium"): 0.16,
    ("HOOK", "terminal"): 0.20,
    ("SETUP", "medium"): 0.22,
    ("SETUP", "terminal"): 0.26,
    ("CRISIS", "weak"): 0.10,
    ("CRISIS", "medium"): 0.16,
    ("CRISIS", "strong"): 0.32,       # right before the crisis's own result clause
    ("CRISIS", "terminal"): 0.26,
    ("INVESTIGATION", "continuation"): 0.0,
    ("INVESTIGATION", "weak"): 0.12,
    ("INVESTIGATION", "medium"): 0.18,
    ("INVESTIGATION", "terminal"): 0.24,
    ("REVEAL", "anticipatory"): 0.55,  # the deliberate pre-result beat
    ("REVEAL", "medium"): 0.20,
    ("REVEAL", "terminal"): 0.30,
    ("EXPLANATION", "medium"): 0.26,
    ("EXPLANATION", "terminal"): 0.30,
    ("PAYOFF", "medium"): 0.22,
    ("PAYOFF", "terminal"): 0.34,      # settle, don't clip like an ad button
}
DEFAULT_PAUSE_BY_BOUNDARY: dict[str, float] = {
    "continuation": 0.0, "weak": 0.12, "medium": 0.22, "strong": 0.32, "anticipatory": 0.5, "terminal": 0.28,
}

def pause_after(phrase: PhraseSpec) -> float:
    return PAUSE_SECONDS.get((phrase.role, phrase.boundary), DEFAULT_PAUSE_BY_BOUNDARY.get(phrase.boundary, 0.22))

# Base rate per role: real, modest rate-of-speech differences (never pitch or
# volume tricks) driven by narrative intent -- HOOK is brisk and confident,
# EXPLANATION eases off for intelligibility, PAYOFF settles rather than rushes.
ROLE_RATE: dict[str, str] = {
    "HOOK": "+10%", "SETUP": "+6%", "CRISIS": "+8%", "INVESTIGATION": "+6%",
    "REVEAL": "+6%", "EXPLANATION": "+4%", "PAYOFF": "+4%",
}
FOCUS_RATE = "+1%"  # a focus phrase (the delivered result) eases off further for clarity

def rate_for_unit(unit: list[PhraseSpec], base_rate: str) -> str:
    if any(p.focus for p in unit):
        return FOCUS_RATE
    if unit[0].pace:
        return unit[0].pace
    return ROLE_RATE.get(unit[0].role, base_rate)

def group_into_units(phrases: list[PhraseSpec]) -> list[list[PhraseSpec]]:
    """Consecutive phrases whose boundary is "continuation" are synthesized
    as ONE Edge TTS call (same pitch/energy contour, no stitch seam); a unit
    ends at (and includes) the first phrase whose boundary is anything else."""
    units: list[list[PhraseSpec]] = []
    current: list[PhraseSpec] = []
    for p in phrases:
        current.append(p)
        if p.boundary != "continuation":
            units.append(current)
            current = []
    if current:
        units.append(current)
    return units

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

def build_auto_plan(text: str, default_role: str = "SETUP") -> list[PhraseSpec]:
    """Fallback for scenes with no authored narration_plan: reproduces the
    previous per-sentence behavior (each sentence its own terminal-boundary
    unit) so manifests that don't opt into the planner are unaffected."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()] or [text]
    return [PhraseSpec(role=default_role, text=s, boundary="terminal") for s in sentences]

# --- Sino-Korean number spelling -------------------------------------------
# Edge's own number normalization for comma-grouped digits is not reliable
# enough to trust for a factual figure like "1,830" -- and simply protecting
# the comma from the punctuation-spacing regex (as V1 did) doesn't guarantee
# the TTS engine reads the digits as one number rather than digit-by-digit.
# Spelling the number out in Sino-Korean before synthesis removes the
# ambiguity entirely. This is general (any 0-9999 value), not hardcoded to
# the Comet script's two figures.
_SINO_UNITS = {1: "일", 2: "이", 3: "삼", 4: "사", 5: "오", 6: "육", 7: "칠", 8: "팔", 9: "구"}

def sino_korean_number(n: int) -> str:
    if n == 0:
        return "영"
    if not (0 <= n < 10_000):
        raise ValueError(f"sino_korean_number only supports 0-9999, got {n}")
    thousands, rem = divmod(n, 1000)
    hundreds, rem = divmod(rem, 100)
    tens, ones = divmod(rem, 10)
    parts = []
    if thousands:
        parts.append(("" if thousands == 1 else _SINO_UNITS[thousands]) + "천")
    if hundreds:
        parts.append(("" if hundreds == 1 else _SINO_UNITS[hundreds]) + "백")
    if tens:
        parts.append(("" if tens == 1 else _SINO_UNITS[tens]) + "십")
    if ones:
        parts.append(_SINO_UNITS[ones])
    return "".join(parts)

# Counters after which a large comma-grouped number should be read as one
# Sino-Korean numeral rather than left as digits for Edge to guess at.
_NUMBER_COUNTERS = ("회", "번", "개", "명", "차례", "건")
_COMMA_NUMBER_RE = re.compile(r"(\d{1,3}(?:,\d{3})+)\s*(" + "|".join(_NUMBER_COUNTERS) + ")")

def spell_out_numbers(text: str) -> str:
    def repl(m: re.Match) -> str:
        digits = int(m.group(1).replace(",", ""))
        if digits >= 10_000:
            return m.group(0)  # outside supported range; leave as-is rather than guess
        return sino_korean_number(digits) + m.group(2)
    return _COMMA_NUMBER_RE.sub(repl, text)
