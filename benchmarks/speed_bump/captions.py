"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.03 narration, same convention as caption_phrases.CURATED."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED = {
    "Same car, same speed. Watch closely what these two different bumps do to it.": (
        "Same car, same speed.", "Watch closely what", "these two different", "bumps do to it."),
    "The short bump jolts the wheels in a flash, while the long one lifts the whole car slowly and tilts it.": (
        "The short bump jolts", "the wheels in a flash,", "while the long one", "lifts the whole car", "slowly and tilts it."),
    "At thirty kilometers per hour, the short bump still hits the car about twice as hard as the long one.": (
        "At thirty kilometers", "per hour, the short bump", "still hits the car", "about twice as hard", "as the long one."),
    "At ten, the long hump turns very gentle, but the short bump still jolts the car noticeably.": (
        "At ten, the long hump", "turns very gentle,", "but the short bump", "still jolts the", "car noticeably."),
    "In this simulation the short bump is about two to six times harsher at every speed we tried.": (
        "In this simulation", "the short bump is", "about two to six times", "harsher at every speed", "we tried."),
    "So it is not just the height of the bump. It is how quickly the road lifts your car.": (
        "So it is not just the", "height of the bump.", "It is how quickly", "the road lifts your car."),
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
