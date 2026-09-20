from dataclasses import dataclass
from .timing import WordTiming

@dataclass(frozen=True)
class Caption:
    text: str
    start: float
    end: float

def segment(words: list[WordTiming], audio_duration: float, lead: float=.12, target: float=1.5, max_duration: float=2.2, max_words: int=5, max_gap: float=.6) -> list[Caption]:
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
        if len(cur)>=max_words or span>=target:
            groups.append(cur); cur=[]
    if cur: groups.append(cur)
    out=[]
    for i,g in enumerate(groups):
        start=max(0.0,g[0].start-lead)
        end=min(audio_duration,g[-1].end)
        if i+1 < len(groups):
            next_start=max(0.0,groups[i+1][0].start-lead)
            if next_start <= g[-1].end + .08: end=max(end,next_start)
        if end-start > max_duration: end=min(end,start+max_duration)
        out.append(Caption(" ".join(x.text for x in g),start,end))
    return out

def speech_gap_violations(captions: list[Caption], words: list[WordTiming]) -> list[WordTiming]:
    return [w for w in words if not any(c.start <= (w.start+w.end)/2 <= c.end for c in captions)]
