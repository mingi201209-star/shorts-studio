"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.04 narration, same convention as speed_bump.captions."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED = {
    "Cars are designed to crush.": ("Cars are designed", "to crush."),
    "Watch the hood buckle, and the front wheels get shoved back.": ("Watch the hood buckle,", "and the front wheels", "get shoved back."),
    "Hidden rails inside fold like an accordion, stretching the stop over a longer distance and time.": (
        "Hidden rails inside", "fold like an accordion,", "stretching the stop", "over a longer distance", "and time."),
    "Meanwhile, the passenger compartment keeps its shape. Pillars and doors stay where they were.": (
        "Meanwhile, the passenger", "compartment keeps", "its shape.", "Pillars and doors", "stay where they were."),
    "Now the same speed, the same wall, but a rigid front. It stops almost instantly, and the car bounces back.": (
        "Now the same speed,", "the same wall,", "but a rigid front.", "It stops almost", "instantly, and the car", "bounces back."),
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
