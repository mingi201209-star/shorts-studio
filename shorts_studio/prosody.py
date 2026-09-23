"""Korean Prosody Planner V2.

V1 required each scene's narration_plan to be hand-authored, phrase by
phrase, with a manually-picked boundary strength -- which does not
generalize (every future script would need the same manual tuning, and
manual tuning is exactly what produced the reported failure: an unnatural
pause after "1950년대" in a hand-picked "boundary" field).

V2 delegates all boundary decisions to shorts_studio.korean_boundary, a
deterministic Korean grammar layer that classifies CONTINUE / WEAK_BOUNDARY /
PHRASE_BOUNDARY / STRONG_BOUNDARY between every pair of adjacent Korean
tokens from lexical/morphological structure, not punctuation or hardcoded
phrase lists. This module's job is what remains genuinely narrative rather
than linguistic: given the boundary-classified chunks korean_boundary
produces, pick a synthesis rate per narrative role and a real inserted
silence for the (much rarer) STRONG_BOUNDARY/anticipatory transitions that
actually end a synthesis unit. Everything at CONTINUE/WEAK_BOUNDARY/
PHRASE_BOUNDARY stays inside ONE Edge TTS call (see korean_boundary's
reconstruct_chunks) -- only a real sentence/discourse transition gets its
own call and its own silence, which is what avoids a pitch/energy reset on
every written clause.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

from .korean_boundary import (
    PHRASE_BOUNDARY, STRONG_BOUNDARY, boundary_max, classify_pair,
    is_sentence_final, tokenize,
)

NARRATIVE_ROLES = ("HOOK", "SETUP", "CRISIS", "INVESTIGATION", "REVEAL", "EXPLANATION", "PAYOFF")
ANTICIPATORY = "anticipatory"
# Only these two boundary values ever end a synthesis unit (see
# group_into_units); CONTINUE/WEAK_BOUNDARY/PHRASE_BOUNDARY are always
# absorbed into a chunk's own text by korean_boundary before a PhraseSpec is
# ever built, but the check is kept generic here so an explicitly-authored
# manual override (still supported) behaves consistently.
_UNIT_ENDING_BOUNDARIES = (STRONG_BOUNDARY, ANTICIPATORY)

@dataclass(frozen=True)
class PhraseSpec:
    role: str
    text: str
    boundary: str = STRONG_BOUNDARY  # what kind of break follows THIS phrase
    focus: bool = False              # the emphasis/result target (e.g. a REVEAL's payload)
    pace: str | None = None          # optional explicit rate override, e.g. "+2%"

# Real inserted silence for a synthesis-unit-ending transition, keyed by
# (role, boundary). Only strong_boundary/anticipatory are ever looked up in
# practice (see _UNIT_ENDING_BOUNDARIES), but the table is not restricted to
# that so an explicit manual override on a weaker boundary still resolves to
# something sane. Deliberately varied per role -- never one fixed silence.
PAUSE_SECONDS: dict[tuple[str, str], float] = {
    ("HOOK", STRONG_BOUNDARY): 0.20,
    ("SETUP", STRONG_BOUNDARY): 0.26,
    ("CRISIS", STRONG_BOUNDARY): 0.28,
    ("INVESTIGATION", STRONG_BOUNDARY): 0.24,
    ("REVEAL", ANTICIPATORY): 0.55,   # the deliberate pre-result beat
    ("REVEAL", STRONG_BOUNDARY): 0.30,
    ("EXPLANATION", STRONG_BOUNDARY): 0.30,
    ("PAYOFF", STRONG_BOUNDARY): 0.34,  # settle, don't clip like an ad button
}
DEFAULT_PAUSE_BY_BOUNDARY: dict[str, float] = {
    "continue": 0.0, "weak_boundary": 0.0, PHRASE_BOUNDARY: 0.0,
    STRONG_BOUNDARY: 0.28, ANTICIPATORY: 0.5,
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
    """A unit ends at (and includes) the first phrase whose boundary is
    STRONG_BOUNDARY or ANTICIPATORY. Phrases produced by plan_narration are
    already one full unit's worth of text each (korean_boundary folds
    CONTINUE/WEAK_BOUNDARY/PHRASE_BOUNDARY into a single chunk's text before
    a PhraseSpec is built), so in practice every plan_narration phrase ends
    its own unit here; this stays generic so an explicitly-authored manual
    override still groups correctly."""
    units: list[list[PhraseSpec]] = []
    current: list[PhraseSpec] = []
    for p in phrases:
        current.append(p)
        if p.boundary in _UNIT_ENDING_BOUNDARIES:
            units.append(current)
            current = []
    if current:
        units.append(current)
    return units

def plan_narration(segments: list[tuple[str, str, bool]]) -> list[PhraseSpec]:
    """segments: [(role, text, focus), ...] in authored order. Runs the
    Korean boundary classifier across the ENTIRE concatenated token stream,
    including at segment/role junctions -- so a narrative-role change on its
    own never forces a boundary the language itself doesn't justify (role is
    metadata carried on the resulting chunks, not a segmentation rule by
    itself).

    The one narrative signal that DOES force a real break, regardless of
    what the linguistic classifier alone would say at that exact junction,
    is `focus`: the transition INTO an authored focus=True segment (the
    delivered emphasis/result of any role, not just REVEAL) is floored at
    STRONG_BOUNDARY, and gets upgraded to ANTICIPATORY. This is not the
    classifier being overridden by role in general -- it is honoring one
    narrow, explicit authorial marker that a writer set deliberately (this
    text is the payload), the same way a paragraph break is real discourse
    structure a writer chose, not something a grammar-only pass could infer
    from wording alone. It generalizes to any future script that marks a
    focus segment; nothing here reads specific text or a specific role."""
    all_tokens = []  # (Token, role, focus)
    for role, text, focus in segments:
        for tok in tokenize(text):
            all_tokens.append((tok, role, focus))
    if not all_tokens:
        return []
    n = len(all_tokens)
    raw_chunks: list[dict] = []
    cur_parts: list[str] = []
    cur_role = all_tokens[0][1]
    cur_focus = False
    for i, (tok, role, focus) in enumerate(all_tokens):
        nxt = all_tokens[i + 1] if i + 1 < n else None
        if nxt is None:
            level = STRONG_BOUNDARY
        else:
            level = classify_pair(tok, nxt[0])
            if nxt[2] and not focus:  # entering a focus segment from a non-focus one
                level = boundary_max(level, STRONG_BOUNDARY)
        if level == PHRASE_BOUNDARY:
            suffix = ","
        elif level == STRONG_BOUNDARY and is_sentence_final(tok):
            suffix = "."
        else:
            suffix = ""
        cur_parts.append(tok.base + suffix)
        cur_focus = cur_focus or focus
        if level == STRONG_BOUNDARY:
            raw_chunks.append({"role": cur_role, "text": " ".join(cur_parts), "focus": cur_focus})
            cur_parts = []
            cur_focus = False
            if i + 1 < n:
                cur_role = all_tokens[i + 1][1]
    if cur_parts:
        raw_chunks.append({"role": cur_role, "text": " ".join(cur_parts), "focus": cur_focus})

    specs = []
    for idx, c in enumerate(raw_chunks):
        boundary = STRONG_BOUNDARY
        if idx + 1 < len(raw_chunks) and raw_chunks[idx + 1]["focus"] and not c["focus"]:
            boundary = ANTICIPATORY
        specs.append(PhraseSpec(role=c["role"], text=c["text"], boundary=boundary, focus=c["focus"]))
    return specs

def build_auto_plan(text: str, default_role: str = "SETUP") -> list[PhraseSpec]:
    """Fallback for scenes with no authored role/text segments at all: runs
    the same general Korean boundary planner over the whole flat narration
    string as a single role segment. This is what makes any future script
    that just supplies a plain `narration` string benefit from the same
    linguistic segmentation, with no per-script configuration."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return plan_narration([(default_role, text, False)])

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
