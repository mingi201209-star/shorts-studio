from dataclasses import dataclass
import math
import re

@dataclass(frozen=True)
class WordTiming:
    text: str
    start: float
    end: float

def validate_timings(words: list[WordTiming], duration: float) -> None:
    prev=0.0
    for w in words:
        if w.start < 0 or w.end < w.start or w.start < prev or w.end > duration + 1e-3:
            raise ValueError(f"invalid timing: {w}")
        prev=w.start

def map_measured_words(text: str, boundaries: list[WordTiming]) -> list[WordTiming]:
    """Bind provider events to authored words without inventing timestamps.

    Multiple measured events within one word may be grouped. An event that
    spans two authored words cannot provide their separate timings and fails
    closed. Punctuation/case differences are harmless; lexical drift is not.
    """
    tokens = re.findall(r"[^\s]+", text)
    def normal(value: str) -> str:
        return re.sub(r"[^\w]", "", value).casefold()
    normalized = [normal(token) for token in tokens]
    if not tokens or any(not token for token in normalized):
        raise ValueError("measured word mapping requires lexical script tokens")
    script = "".join(normalized)
    token_ends, cursor = [], 0
    for token in normalized:
        cursor += len(token)
        token_ends.append(cursor)
    groups: list[list[WordTiming]] = [[] for _ in tokens]
    cursor, token_index, previous_start = 0, 0, 0.0
    for boundary in boundaries:
        lexical = normal(boundary.text)
        if not lexical:
            continue
        if (not math.isfinite(boundary.start) or not math.isfinite(boundary.end)
                or boundary.start < 0 or boundary.end <= boundary.start
                or boundary.start < previous_start):
            raise ValueError(f"invalid measured boundary timing: {boundary}")
        previous_start = boundary.start
        while token_index < len(tokens) and cursor == token_ends[token_index]:
            token_index += 1
        end = cursor + len(lexical)
        if token_index >= len(tokens) or script[cursor:end] != lexical:
            raise ValueError("provider boundary text does not match the spoken script")
        if end > token_ends[token_index]:
            raise ValueError("provider boundary spans multiple script words; word timing is unavailable")
        groups[token_index].append(boundary)
        cursor = end
    if cursor != len(script) or any(not group for group in groups):
        raise ValueError("provider boundaries do not cover every script word")
    return [
        WordTiming(token, group[0].start, max(boundary.end for boundary in group))
        for token, group in zip(tokens, groups)
    ]
