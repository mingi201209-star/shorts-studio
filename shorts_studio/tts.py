from __future__ import annotations
import json, re
from pathlib import Path
from .timing import WordTiming

DEFAULT_KO_VOICE = "ko-KR-HyunsuMultilingualNeural"
DEFAULT_KO_RATE = "+24%"
DEFAULT_KO_PITCH = "-2Hz"
DEFAULT_KO_VOLUME = "+0%"

def _prepare_korean_speech(text: str) -> str:
    """Conservative speech cleanup: preserve wording while giving Edge clearer
    Korean phrase boundaries and avoiding the rushed +35% delivery."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*([,.;!?])\s*", r"\1 ", text).strip()
    return text

def _tokenize(text:str)->list[str]:
    return re.findall(r"[^\s]+",text)

def _map_boundaries_to_script(text:str, boundaries:list[WordTiming])->list[WordTiming]:
    tokens=_tokenize(text)
    if not tokens or not boundaries: return []
    if len(tokens)==len(boundaries):
        return [WordTiming(t,b.start,b.end) for t,b in zip(tokens,boundaries)]
    # Edge may emit sentence/phrase boundary events for Korean rather than whitespace words.
    start=boundaries[0].start; end=boundaries[-1].end
    weights=[max(1,len(re.sub(r"\W","",t))) for t in tokens]; total=sum(weights)
    cursor=start; out=[]
    for i,(t,w) in enumerate(zip(tokens,weights)):
        nxt=end if i==len(tokens)-1 else cursor+(end-start)*w/total
        out.append(WordTiming(t,cursor,nxt)); cursor=nxt
    return out

async def edge_tts_with_boundaries(text: str, audio_path: Path, timing_path: Path, voice: str=DEFAULT_KO_VOICE, rate: str=DEFAULT_KO_RATE, pitch: str=DEFAULT_KO_PITCH, volume: str=DEFAULT_KO_VOLUME) -> list[WordTiming]:
    import edge_tts
    audio_path.parent.mkdir(parents=True,exist_ok=True)
    speech_text=_prepare_korean_speech(text)\n    communicate=edge_tts.Communicate(speech_text,voice,rate=rate,pitch=pitch,volume=volume,boundary="SentenceBoundary")
    boundaries=[]; audio=bytearray()
    async for chunk in communicate.stream():
        if chunk["type"]=="audio": audio.extend(chunk["data"])
        elif chunk["type"] in {"WordBoundary","SentenceBoundary"}:
            start=chunk["offset"]/10_000_000
            dur=chunk["duration"]/10_000_000
            boundaries.append(WordTiming(chunk.get("text",""),start,start+dur))
    audio_path.write_bytes(audio)
    words=_map_boundaries_to_script(text,boundaries)
    timing_path.write_text(json.dumps({"source":"edge-boundary","voice":voice,"rate":rate,"pitch":pitch,"volume":volume,"speech_text":speech_text,"raw":[w.__dict__ for w in boundaries],"words":[w.__dict__ for w in words]},ensure_ascii=False,indent=2),encoding="utf-8")
    if not words:
        raise RuntimeError("TTS returned no timing boundary events; do not guess from scene duration")
    return words
