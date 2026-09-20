from dataclasses import dataclass

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
