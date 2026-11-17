"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.04 narration, same convention as speed_bump.captions."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED = {
    'A car hits a wall. In real life it takes a tenth of a second, so we slow it down.': (
        "A car hits", "a wall.", "In real life it takes", "a tenth of a second,", "so we slow it down."),
    "The hood buckles and the front folds back, then hidden rails fold like an accordion.": (
        "The hood buckles", "and the front", "folds back,", "then hidden rails", "fold like an accordion."),
    "The rails soak up the crash over a longer stop, and the cabin keeps its shape.": (
        "The rails soak up", "the crash over", "a longer stop,", "and the cabin keeps", "its shape."),
    "Pillars, doors and roof stay put. Now a rigid front hits the same wall.": (
        "Pillars, doors and roof", "stay put.", "Now a rigid front", "hits the same wall."),
    "It has almost nothing to crush, so it stops almost instantly and bounces back.": (
        "It has almost", "nothing to crush,", "so it stops almost", "instantly", "and bounces back."),
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
