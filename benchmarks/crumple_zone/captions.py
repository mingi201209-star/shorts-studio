"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.04 narration, same convention as speed_bump.captions."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED = {
    "Cars are designed to crush.": (
        "Cars are designed", "to crush."),
    "The real crash lasts a tenth of a second so we slow it way down. Watch the hood buckle and the whole front fold back.": (
        "The real crash lasts", "a tenth of a second", "so we slow it way down.", "Watch the hood buckle", "and the whole front", "fold back."),
    "Hidden rails inside fold like an accordion absorbing the crash energy and stretch the stop over a longer distance and time.": (
        "Hidden rails inside", "fold like an accordion", "absorbing the crash", "energy and stretch", "the stop over a longer", "distance and time."),
    "The cabin keeps its shape. Pillars, doors and roof stay put.": (
        "The cabin keeps", "its shape.", "Pillars, doors and roof", "stay put."),
    "Now a rigid front at the same speed. It has almost nothing to crush so it stops almost instantly and bounces back.": (
        "Now a rigid front at", "the same speed. It has", "almost nothing to crush", "so it stops almost", "instantly and bounces", "back."),
    "The front is meant to deform and absorb the crash. The cabin isn't.": (
        "The front is meant", "to deform and absorb", "the crash.", "The cabin isn't."),
}


def single_line_groups(text: str) -> list[tuple[int, int]]:
    phrases = CURATED.get(text)
    if phrases is None:
        return phrase_groups(text)
    tokens = text.split()
    groups, cursor = [], 0
    for phrase in phrases:
        n = len(phrase.split())
        groups.append((cursor, cursor + n))
        cursor += n
    if cursor != len(tokens) or " ".join(phrases) != text or any(len(p) > SINGLE_LINE for p in phrases):
        raise ValueError(f"curated caption phrases do not match the sentence: {text!r}")
    return groups
