"""Korean Speech Planner V3.

V3 adds a conservative linguistic layer above the V2 boundary planner.
It does NOT rewrite orthography into pronunciation spellings: Edge already
handles many Korean phonological processes, and blind phonetic rewriting can
make good synthesis worse.  Instead this module annotates synthesis units
with explainable Korean prosodic features and derives small, bounded local
rate adjustments.

The planner deliberately uses signals we can realize with the current Edge
backend (unit grouping, rate and silence). F0 contour remains explicit
metadata until the backend can control it without forcing extra TTS calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .prosody import PhraseSpec

_RATE_RE = re.compile(r"^([+-]?)(\d+)%$")


@dataclass(frozen=True)
class SpeechFeatures:
    syllables: int
    eojeol: int
    focus: bool
    phrase_final_lengthening: float
    rate_delta_pct: int
    f0_intent: str


def _hangul_syllables(text: str) -> int:
    return sum("\uac00" <= ch <= "\ud7a3" for ch in text)


def analyze_unit(unit: list[PhraseSpec]) -> SpeechFeatures:
    text = " ".join(p.text for p in unit).strip()
    syllables = _hangul_syllables(text)
    eojeol = len(text.split())
    focus = any(p.focus for p in unit)

    # Long Korean phrases become rushed at a flat global rate. Ease them
    # slightly; focus payloads get a stronger ease-off so the information
    # peak is intelligible. Bounds are intentionally small.
    rate_delta = 0
    if syllables >= 28:
        rate_delta -= 2
    elif syllables >= 18:
        rate_delta -= 1
    if focus:
        rate_delta -= 2

    # Phrase-final lengthening is represented as intent metadata for now.
    # A separate TTS call solely to stretch the final syllable would reset
    # pitch/energy and recreate the robotic stitching V2 removed.
    pfl = 1.10 if focus else (1.06 if syllables >= 12 else 1.04)
    f0_intent = "focus_prominence" if focus else "continuation_or_terminal"

    return SpeechFeatures(
        syllables=syllables,
        eojeol=eojeol,
        focus=focus,
        phrase_final_lengthening=pfl,
        rate_delta_pct=rate_delta,
        f0_intent=f0_intent,
    )


def adjust_rate(rate: str, features: SpeechFeatures) -> str:
    m = _RATE_RE.match(rate.strip())
    if not m:
        return rate
    sign, value = m.groups()
    pct = int(value) * (-1 if sign == "-" else 1)
    pct += features.rate_delta_pct
    # Shorts should stay energetic, but never let this layer create an
    # extreme speed from an otherwise sane authored/base rate.
    pct = max(-5, min(12, pct))
    return f"{pct:+d}%"
