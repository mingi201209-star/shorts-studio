"""Hand-cut single-line caption phrases (<= 24 characters) for the EP.03 narration, same convention as caption_phrases.CURATED."""
from __future__ import annotations

from benchmarks.road_safety.caption_phrases import SINGLE_LINE, phrase_groups

CURATED_XRAY = {
    'Same car and same speed with a long hump on the left and a short bump on the right.': (
        'Same car and same speed', 'with a long hump on', 'the left and a short', 'bump on the right.'),
    'Now look inside where every wheel hangs on a spring and a damper that work together to soak up the bump.': (
        'Now look inside where', 'every wheel hangs on', 'a spring and a damper', 'that work together', 'to soak up the bump.'),
    'The wheel has to follow the road so the short bump throws it up in a split second but the long hump lifts it gently.': (
        'The wheel has to', 'follow the road so the', 'short bump throws it up', 'in a split second but', 'the long hump lifts', 'it gently.'),
    'That jolt travels up into the car and at thirty kilometers per hour the short bump hits about twice as hard as the long one.': (
        'That jolt travels up', 'into the car and at', 'thirty kilometers per', 'hour the short bump hits', 'about twice as hard', 'as the long one.'),
    'Both are the same height and what matters is how quickly the road lifts the car. This is a computer simulation with assumed values.': (
        'Both are the same height', 'and what matters is how', 'quickly the road lifts', 'the car. This is a', 'computer simulation', 'with assumed values.'),
    "Now look inside. Every wheel hangs on a spring and a damper that work together to soak up the bump.": (
        "Now look inside.", "Every wheel hangs on", "a spring and a damper", "that work together", "to soak up the bump."),
    "The short bump squeezes the spring in a flash while the long hump squeezes it slowly and gently.": (
        "The short bump squeezes", "the spring in a flash", "while the long hump", "squeezes it slowly", "and gently."),
    "At thirty kilometers per hour the short bump hits about twice as hard as the long one.": (
        "At thirty kilometers", "per hour the short bump", "hits about twice as hard", "as the long one."),
    "At ten the long hump turns gentle but the short bump still jolts the car noticeably.": (
        "At ten the long hump", "turns gentle but the", "short bump still jolts", "the car noticeably."),
    "The wheel has to follow the road. The short bump throws it up in a split second but the long hump lifts it gently.": (
        "The wheel has to", "follow the road.", "The short bump throws", "it up in a split second", "but the long hump", "lifts it gently."),
    "That jolt travels up into the car. At thirty kilometers per hour the short bump hits about twice as hard as the long one.": (
        "That jolt travels", "up into the car.", "At thirty kilometers", "per hour the short bump", "hits about twice as hard", "as the long one."),
    "Both are the same height. What matters is how quickly the road lifts the car. This is a computer simulation with assumed values.": (
        "Both are the same", "height. What matters", "is how quickly the", "road lifts the car.", "This is a computer", "simulation with", "assumed values."),
    "It is how quickly the road lifts the car. This is a computer simulation with assumed values.": (
        "It is how quickly", "the road lifts the car.", "This is a computer", "simulation with", "assumed values."),
}

CURATED = {
    "Same car, same speed. A long hump on the left, a short bump on the right.": (
        "Same car, same speed.", "A long hump on", "the left, a short bump", "on the right."),
    "The short bump jolts the wheels in a flash while the long hump lifts the whole car slowly.": (
        "The short bump jolts", "the wheels in a flash", "while the long hump", "lifts the whole", "car slowly."),
    "Now at thirty kilometers per hour the short bump hits about twice as hard as the long one.": (
        "Now at thirty", "kilometers per hour", "the short bump hits", "about twice as hard", "as the long one."),
    "Slow down to ten and the long hump turns gentle but the short bump still jolts the car.": (
        "Slow down to ten", "and the long hump", "turns gentle but the", "short bump still", "jolts the car."),
    "This is a computer simulation with assumed values and the short bump is about two to six times harsher.": (
        "This is a computer", "simulation with", "assumed values and", "the short bump is", "about two to six", "times harsher."),
    "So it is not just the height of the bump. It is how quickly the road lifts your car and that changes the ride.": (
        "So it is not just", "the height of the bump.", "It is how quickly", "the road lifts your car", "and that changes", "the ride."),
}


def single_line_groups(text: str) -> list[tuple[int, int]]:
    phrases = CURATED.get(text) or CURATED_XRAY.get(text)
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
