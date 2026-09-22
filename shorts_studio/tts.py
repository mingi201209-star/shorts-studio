from __future__ import annotations
import json, re, subprocess
from dataclasses import replace
from pathlib import Path
from .timing import WordTiming
from .prosody import PhraseSpec, build_auto_plan, group_into_units, pause_after, rate_for_unit, spell_out_numbers

DEFAULT_KO_VOICE = "ko-KR-HyunsuMultilingualNeural"
# A flat rate/pitch is only a fallback for scenes with no authored
# narration_plan. The real naturalness fix is the Korean Prosody Planner
# (shorts_studio/prosody.py): real per-word timestamps (WordBoundary) from
# grouped, role-aware synthesis units, each followed by a pause that VARIES
# by (narrative role, boundary strength) instead of one fixed silence
# everywhere. See synthesize_plan below.
DEFAULT_KO_RATE = "+8%"
DEFAULT_KO_PITCH = "+0Hz"
DEFAULT_KO_VOLUME = "+0%"

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

def _prepare_korean_speech(text: str) -> str:
    """Collapse stray whitespace and give Edge clear punctuation-boundary
    spacing -- but never touch a comma sitting between two digits (a
    thousands separator like "1,830"). The old unconditional
    r"\\s*([,.;!?])\\s*" -> r"\\1 " substitution split "1,830" into "1, 830",
    which changes how the number is read aloud and would misrepresent the
    factual "1,830 additional water-tank cycles" figure."""
    text = re.sub(r"\s+", " ", text).strip()
    out = []; i = 0
    for m in re.finditer(r"\s*([,.;!?])\s*", text):
        start, end = m.span()
        out.append(text[i:start])
        ch = m.group(1)
        prev_char = text[start - 1] if start > 0 else ""
        next_char = text[end:end + 1]
        if ch == "," and prev_char.isdigit() and next_char.isdigit():
            out.append(",")
        else:
            out.append(ch + " ")
        i = end
    out.append(text[i:])
    return "".join(out).strip()

def _split_sentences(text: str) -> list[str]:
    """Split into sentences on real sentence-ending punctuation, keeping the
    punctuation attached. Synthesizing each sentence as its own TTS call
    (see edge_tts_with_boundaries) resets the timing origin per sentence, so
    a long multi-sentence scene never relies on cross-sentence
    character-count interpolation for its middle words."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]
    return parts or [text]

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

async def _synthesize_sentence(text: str, voice: str, rate: str, pitch: str, volume: str) -> tuple[bytes, list[WordTiming]]:
    """One real Edge TTS call per sentence, requesting WordBoundary events --
    the engine's own real per-word timestamps, not a client-side guess. This
    is what actually fixes caption/speech sync: the old SentenceBoundary-only
    mode gave a single timestamp per whole sentence, so every caption chunk
    *within* a multi-word sentence was positioned by linear character-count
    interpolation, which drifts from the real audio -- the root cause of
    captions lingering noticeably after the voice has moved on."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume=volume, boundary="WordBoundary")
    audio = bytearray(); boundaries = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] in {"WordBoundary", "SentenceBoundary"}:
            start = chunk["offset"] / 10_000_000
            dur = chunk["duration"] / 10_000_000
            boundaries.append(WordTiming(chunk.get("text", ""), start, start + dur))
    return bytes(audio), boundaries

def _ffmpeg_duration_seconds(path: Path) -> float:
    """Probe real audio duration from ffmpeg's own stderr banner -- avoids a
    hard dependency on a separate ffprobe binary for this step. render()
    already requires ffprobe later for the final video; this keeps TTS
    synthesis itself consistent with the ffmpeg-only tooling every other
    real-render test in this repo relies on."""
    out = subprocess.run(["ffmpeg", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out.stderr)
    if not m:
        raise RuntimeError(f"could not determine audio duration for {path}: {out.stderr[-500:]}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)

def _silence_clip(path: Path, seconds: float) -> Path:
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(seconds), "-q:a", "9", str(path)], check=True, capture_output=True)
    return path

def _concat_audio(parts: list[Path], out_path: Path) -> Path:
    list_file = out_path.with_suffix(".concat.txt")
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)], check=True, capture_output=True)
    return out_path

async def synthesize_plan(phrases: list[PhraseSpec], audio_path: Path, timing_path: Path, voice: str=DEFAULT_KO_VOICE, base_rate: str=DEFAULT_KO_RATE, base_pitch: str=DEFAULT_KO_PITCH, volume: str=DEFAULT_KO_VOLUME, use_role_rates: bool=True) -> list[WordTiming]:
    """Korean Prosody Planner V1 synthesis engine. Consecutive
    "continuation"-boundary phrases are merged into ONE Edge TTS call (one
    continuous pitch/energy contour -- no per-sentence reset, no robotic
    stitching); a new unit starts only at a real boundary (weak/medium/
    strong/anticipatory/terminal), each followed by a PAUSE THAT VARIES with
    (role, boundary) rather than one fixed silence everywhere. Numbers are
    spelled out in Sino-Korean before synthesis so "1,830" is read as one
    number, never split by punctuation handling. WordBoundary timing (real
    per-word timestamps) is kept throughout for caption sync -- prosody and
    timing accuracy are handled independently, as they measure different
    things."""
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    if not phrases:
        raise RuntimeError("no narration phrases to synthesize")
    prepared = [replace(p, text=_prepare_korean_speech(spell_out_numbers(p.text))) for p in phrases]
    units = group_into_units(prepared)

    unit_audio = []; unit_words = []; unit_raw = []; unit_meta = []
    for idx, unit in enumerate(units):
        unit_text = " ".join(p.text for p in unit)
        rate = rate_for_unit(unit, base_rate) if use_role_rates else base_rate
        audio_bytes, boundaries = await _synthesize_sentence(unit_text, voice, rate, base_pitch, volume)
        if not boundaries:
            raise RuntimeError(f"TTS returned no timing boundary events for unit {idx+1}/{len(units)} (role={unit[0].role!r}): {unit_text!r}; do not guess from scene duration")
        unit_audio.append(audio_bytes)
        unit_words.append(_map_boundaries_to_script(unit_text, boundaries))
        unit_raw.append([w.__dict__ for w in boundaries])
        unit_meta.append({"role": unit[0].role, "text": unit_text, "rate": rate, "boundary": unit[-1].boundary, "focus": any(p.focus for p in unit)})

    gaps = [pause_after(unit[-1]) for unit in units[:-1]]  # gap AFTER unit i (i < last)

    if len(units) == 1:
        audio_path.write_bytes(unit_audio[0])
        words = unit_words[0]
    else:
        tmp_dir = audio_path.parent
        part_paths = []
        for i, audio_bytes in enumerate(unit_audio):
            part = tmp_dir / f"{audio_path.stem}_part{i}.mp3"
            part.write_bytes(audio_bytes)
            part_paths.append(part)
        concat_parts = [part_paths[0]]
        for i in range(1, len(part_paths)):
            gap_seconds = gaps[i - 1]
            if gap_seconds > 0:
                gap_path = tmp_dir / f"{audio_path.stem}_gap{i}.mp3"
                _silence_clip(gap_path, gap_seconds)
                concat_parts.append(gap_path)
            concat_parts.append(part_paths[i])
        _concat_audio(concat_parts, audio_path)

        words = []; cursor = 0.0
        for i, uw in enumerate(unit_words):
            offset = cursor
            words.extend(WordTiming(w.text, w.start + offset, w.end + offset) for w in uw)
            real_duration = _ffmpeg_duration_seconds(part_paths[i])
            gap = gaps[i] if i < len(gaps) else 0.0
            cursor = offset + real_duration + gap

    timing_path.write_text(json.dumps({
        "source": "prosody-planner-v1", "voice": voice, "base_rate": base_rate, "base_pitch": base_pitch, "volume": volume,
        "units": unit_meta, "gaps_seconds": gaps, "raw": unit_raw, "words": [w.__dict__ for w in words],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not words:
        raise RuntimeError("TTS returned no timing boundary events; do not guess from scene duration")
    return words

async def edge_tts_with_boundaries(text: str, audio_path: Path, timing_path: Path, voice: str=DEFAULT_KO_VOICE, rate: str=DEFAULT_KO_RATE, pitch: str=DEFAULT_KO_PITCH, volume: str=DEFAULT_KO_VOLUME) -> list[WordTiming]:
    """Backward-compatible entry point: auto-splits `text` into per-sentence
    terminal-boundary phrases (the pre-planner behavior) and synthesizes
    them at the given flat rate/pitch -- used when a scene declares no
    narration_plan. See synthesize_plan for the role-aware engine."""
    plan = build_auto_plan(text)
    if not plan:
        raise RuntimeError("no narration text to synthesize")
    return await synthesize_plan(plan, audio_path, timing_path, voice, rate, pitch, volume, use_role_rates=False)
