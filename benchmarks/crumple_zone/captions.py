"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.04 narration, same convention as speed_bump.captions."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED = {
    "A car hits a wall and we slow that tenth of a second way down to watch it.": (
        "A car hits a wall", "and we slow that", "tenth of a second", "way down to watch it."),
    "The hood buckles and the front folds back as the hidden rails inside fold like an accordion.": (
        "The hood buckles", "and the front folds back", "as the hidden rails", "inside fold like", "an accordion."),
    "Rails absorb the crash energy over a longer stop while the cabin quietly keeps its whole shape.": (
        "Rails absorb the crash", "energy over a longer", "stop while the cabin", "quietly keeps its", "whole shape."),
    "Pillars doors and roof stay exactly put and now a rigid front hits the very same wall.": (
        "Pillars doors and roof", "stay exactly put", "and now a rigid front", "hits the very same wall."),
    "It has almost nothing to crush so it stops almost instantly and bounces back off the wall.": (
        "It has almost nothing", "to crush so it stops", "almost instantly", "and bounces back", "off the wall."),
    "The front is meant to deform and absorb the whole crash energy but the cabin is not.": (
        "The front is meant", "to deform and absorb", "the whole crash energy", "but the cabin is not."),
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
