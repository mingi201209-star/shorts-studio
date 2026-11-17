"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.04 narration, same convention as speed_bump.captions."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED = {
    "Cars are designed to crush.": ("Cars are designed", "to crush."),
    "Inside, hidden structures fold and slow the car down over a longer distance and time.": (
        "Inside, hidden", "structures fold and", "slow the car down", "over a longer distance", "and time."),
    "Watch the front keep folding as the car slows all the way to a stop.": (
        "Watch the front", "keep folding", "as the car slows", "all the way to a stop."),
    "The rigid front stops in a tiny distance. The car bounces back almost immediately.": (
        "The rigid front stops", "in a tiny distance.", "The car bounces back", "almost immediately."),
    "The passenger compartment keeps its shape. While the front folds inward, the cabin stays intact.": (
        "The passenger", "compartment keeps", "its shape.", "While the front", "folds inward,", "the cabin stays intact."),
    "The front is meant to deform. The cabin isn't.": ("The front is meant", "to deform.", "The cabin isn't."),
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
