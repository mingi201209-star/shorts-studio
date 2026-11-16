"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.04 narration, same convention as speed_bump.captions."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED = {
    "Cars are designed to crush.": ("Cars are designed", "to crush."),
    "Inside, hidden structures fold and slow the car down over a longer distance and time.": (
        "Inside, hidden", "structures fold and", "slow the car down", "over a longer distance", "and time."),
    "For the same change in momentum, more stopping time can mean less average force.": (
        "For the same change", "in momentum, more", "stopping time can mean", "less average force."),
    "The rigid front stops in a tiny distance, so its average force is far higher.": (
        "The rigid front stops", "in a tiny distance,", "so its average force", "is far higher."),
    "The passenger compartment is built to stay protective, while seat belts and airbags help protect the people inside.": (
        "The passenger", "compartment is built", "to stay protective,", "while seat belts and", "airbags help protect", "the people inside."),
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
