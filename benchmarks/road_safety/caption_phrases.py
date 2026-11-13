"""Phrase-aware caption grouping for one episode at a time.

The shared caption_groups() cuts every sentence into balanced runs of at most
three words, which can split a phrase ("a wall of / plastic barrels at").
phrase_groups() cuts at commas, semicolons and clause words instead, keeps
each cue within the caption builder's 31-character limit, never crosses a
sentence end and never leaves a one-word cue. curious_mechanics_audio.build()
still defaults to caption_groups(); an episode opts in with grouper=.
"""
from __future__ import annotations

MAX_CHARS = 31
SINGLE_LINE = 24   # longer cues wrap to two lines and rise into the picture's safe margin
CLAUSE_WORDS = {"and", "so", "but", "because", "that", "while", "which"}


def _length(tokens: list[str]) -> int:
    return len(" ".join(tokens))


#: Hand-cut phrases for narration that is locked in an episode's speech plan.
#: Each phrase is a run of whole words within the 31-character cue limit and
#: the phrases of a sentence concatenate back to exactly that sentence.
CURATED: dict[str, tuple[str, ...]] = {
    "This car hits a wall of plastic barrels at highway speed, and every single one bursts into flying sand.": (
        "This car hits a wall", "of plastic barrels", "at highway speed,", "and every single one",
        "bursts into flying sand."),
    "Each barrel is nothing but a thin plastic shell packed full of sand.": (
        "Each barrel is nothing", "but a thin plastic shell", "packed full of sand."),
    "Each pile of sand it hits must be sped up, and that speed comes out of the car.": (
        "Each pile of sand", "it hits must be sped up,", "and that speed", "comes out of the car."),
    "The barrels toward the back hold more sand, so the car slows lightly at first and harder deeper in.": (
        "The barrels toward", "the back hold more sand,", "so the car slows lightly",
        "at first and harder", "deeper in."),
    "A concrete wall would stop this car in about one meter; these barrels stretch that stop to six.": (
        "A concrete wall would", "stop this car in about", "one meter;", "these barrels stretch",
        "that stop to six."),
    "So at highway exits, barrels like these stand guard in front of hard concrete, ready for the next car.": (
        "So at highway exits,", "barrels like these", "stand guard in front", "of hard concrete,",
        "ready for the next car."),
    "Two cars hit the same steel sign post at the same speed but only one of them stops.": (
        "Two cars hit the same", "steel sign post", "at the same speed", "but only one", "of them stops."),
    "The second post was built to let go because its base slips apart the instant the bumper hits.": (
        "The second post", "was built to let go", "because its base", "slips apart the instant", "the bumper hits."),
    "Its two plates are held by bolts in open notches that resist the wind but not a moving car.": (
        "Its two plates", "are held by bolts", "in open notches", "that resist the wind", "but not a moving car."),
    "Hit low, the freed post spins up and over the roof and lands on the road behind the car.": (
        "Hit low,", "the freed post spins up", "and over the roof", "and lands on the road", "behind the car."),
    "The fixed post took all of the car's speed in under a meter while the breakaway post took almost none.": (
        "The fixed post took all", "of the car's speed", "in under a meter", "while the breakaway post", "took almost none."),
    "So the signs along fast roads stand on bases like this, waiting to let go.": (
        "So the signs along", "fast roads stand", "on bases like this,", "waiting to let go."),
    "Why are some road signs designed to break the moment a car hits them?": (
        "Why are some road", "signs designed to break", "the moment a car", "hits them?"),
    "Two cars hit the same post at the same speed but only one of them stops.": (
        "Two cars hit the same", "post at the same speed", "but only one", "of them stops."),
    "Two identical cars hit the same kind of post at the same speed but only one of them stops.": (
        "Two identical cars", "hit the same kind of", "post at the same speed", "but only one", "of them stops."),
    "So the signs along fast roads and highways stand on bases like this, quietly waiting to let go.": (
        "So the signs along", "fast roads and highways", "stand on bases", "like this, quietly", "waiting to let go."),
    "The second post was built to let go because its base simply slips apart the very instant the bumper hits.": (
        "The second post", "was built to let go", "because its base", "simply slips apart", "the very instant", "the bumper hits."),
    "Its two plates are held together by bolts in open notches that resist the wind but not a moving car.": (
        "Its two plates", "are held together", "by bolts in open notches", "that resist the wind", "but not a moving car."),
}


def phrase_groups(text: str) -> list[tuple[int, int]]:
    tokens = text.split()
    curated = CURATED.get(text)
    if curated is not None:
        groups, cursor = [], 0
        for phrase in curated:
            count = len(phrase.split())
            groups.append((cursor, cursor + count))
            cursor += count
        if cursor != len(tokens) or " ".join(curated) != text or any(len(x) > SINGLE_LINE for x in curated):
            raise ValueError(f"curated caption phrases do not match the sentence: {text!r}")
        return groups
    groups: list[tuple[int, int]] = []
    sentence_start = 0
    for index, token in enumerate(tokens):
        if not (token[-1] in ".!?" or index == len(tokens) - 1):
            continue
        sentence = list(range(sentence_start, index + 1))
        sentence_start = index + 1
        spans: list[list[int]] = []
        current: list[int] = []
        for i in sentence:
            word = tokens[i]
            starts_clause = word.lower().strip(",;:") in CLAUSE_WORDS and len(current) >= 3
            too_long = current and _length([tokens[k] for k in current] + [word]) > MAX_CHARS
            if starts_clause or too_long:
                spans.append(current)
                current = []
            current.append(i)
            if word[-1] in ",;:":
                spans.append(current)
                current = []
        if current:
            spans.append(current)
        # no one-word or very short cues: fold into a neighbour that still fits
        merged: list[list[int]] = []
        for span in spans:
            short = len(span) < 2 or _length([tokens[k] for k in span]) < 9
            if merged and short and _length([tokens[k] for k in merged[-1] + span]) <= MAX_CHARS:
                merged[-1] = merged[-1] + span
            else:
                merged.append(span)
        if len(merged) > 1 and (len(merged[0]) < 2 or _length([tokens[k] for k in merged[0]]) < 9) \
                and _length([tokens[k] for k in merged[0] + merged[1]]) <= MAX_CHARS:
            merged[1] = merged[0] + merged[1]
            merged.pop(0)
        groups.extend((span[0], span[-1] + 1) for span in merged)
    return groups
