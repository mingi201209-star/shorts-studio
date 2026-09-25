from dataclasses import dataclass
from .timing import WordTiming

@dataclass(frozen=True)
class Caption:
    text: str
    start: float
    end: float

_KO_BREAK_AFTER = ("지만", "는데", "면서", "했고", "넣고", "했습니다.", "됐습니다.", "겁니다.", "였습니다.", "이었습니다.")

def _semantic_break(word: str) -> bool:
    token = word.strip()
    return token.endswith(_KO_BREAK_AFTER) or token.endswith((".", "?", "!"))

# target/max_duration/max_words widened per direct user feedback that
# captions felt like they were "moving" -- with the old short groups
# (target=1.35, max_duration=2.0, max_words=5) a top-anchored, horizontally
# centered caption changes text (and therefore its centered width) every
# ~1.3s, which reads as constant side-to-side jumping even though the
# anchor point never moves. Fewer, longer-held groups cut that change
# frequency without altering the fixed top-anchored position itself.
def segment(words: list[WordTiming], audio_duration: float, lead: float=.12, target: float=2.2, max_duration: float=3.2, max_words: int=9, max_gap: float=.6) -> list[Caption]:
    if not words: return []
    groups=[]; cur=[]
    for w in words:
        # A real pause (e.g. between sentences) must start a new group; otherwise a
        # long merged span gets clipped by max_duration below and silently drops
        # coverage of the words after the pause -- a speech-gap regression.
        if cur and (w.start-cur[-1].end) > max_gap:
            groups.append(cur); cur=[]
        cur.append(w)
        span=cur[-1].end-cur[0].start
        if _semantic_break(w.text):
            groups.append(cur); cur=[]
        elif len(cur)>=max_words or span>=target:
            groups.append(cur); cur=[]
    if cur: groups.append(cur)
    out=[]
    for i,g in enumerate(groups):
        start=max(0.0,g[0].start-lead)
        end=min(audio_duration,g[-1].end)
        if i+1 < len(groups):
            next_start=max(0.0,groups[i+1][0].start-lead)
            if next_start <= g[-1].end + .08: end=max(end,next_start)
        # The max_duration cap must only trim excess BRIDGED overlap into the
        # next caption's territory -- it must never cut below this group's
        # own last real word's end, or a legitimately spoken word silently
        # loses caption coverage (a real speech-gap regression). This is
        # what let a small (sub-max_gap) pause between two prosody-planner
        # units -- e.g. a deliberately short HOOK->SETUP transition -- merge
        # words from both sides into one group whose natural span exceeded
        # max_duration, then get clamped below its own last word's end.
        if end-start > max_duration: end=max(g[-1].end,min(end,start+max_duration))
        out.append(Caption(" ".join(x.text for x in g),start,end))
    return out

def speech_gap_violations(captions: list[Caption], words: list[WordTiming]) -> list[WordTiming]:
    return [w for w in words if not any(c.start <= (w.start+w.end)/2 <= c.end for c in captions)]

def excessive_tail_violations(captions: list[Caption], words: list[WordTiming], max_tail: float=0.35) -> list[Caption]:
    """A caption must disappear promptly once the words it covers finish
    being spoken. Flag any caption whose end sits more than max_tail seconds
    past the real end of the last word it covers -- this is what actually
    catches "captions remain visible noticeably after the phrase ended",
    not a cosmetic global offset tweak."""
    violations = []
    for c in captions:
        covered = [w for w in words if w.start < c.end and w.end > c.start]
        if not covered:
            continue
        real_end = max(w.end for w in covered)
        if c.end - real_end > max_tail:
            violations.append(c)
    return violations
