from __future__ import annotations
import json
from pathlib import Path
from .timing import WordTiming

async def edge_tts_with_boundaries(text: str, audio_path: Path, timing_path: Path, voice: str="ko-KR-HyunsuMultilingualNeural", rate: str="+20%") -> list[WordTiming]:
    import edge_tts
    audio_path.parent.mkdir(parents=True,exist_ok=True)
    communicate=edge_tts.Communicate(text,voice,rate=rate)
    words=[]; audio=bytearray()
    async for chunk in communicate.stream():
        if chunk["type"]=="audio": audio.extend(chunk["data"])
        elif chunk["type"]=="WordBoundary":
            start=chunk["offset"]/10_000_000
            dur=chunk["duration"]/10_000_000
            words.append(WordTiming(chunk["text"],start,start+dur))
    audio_path.write_bytes(audio)
    timing_path.write_text(json.dumps([w.__dict__ for w in words],ensure_ascii=False,indent=2),encoding="utf-8")
    if not words: raise RuntimeError("TTS returned no WordBoundary events; do not guess caption timing")
    return words
