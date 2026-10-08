"""Narration provider abstraction + pre-rendered narration override.

Edge TTS (``shorts_studio.tts``) is the dev/fallback baseline, not the final
voice target. This module lets a production swap the voice WITHOUT touching
captions, visual-cue binding or any QA gate, because every provider must
deliver the same thing the Edge path already delivers:

  * one audio file per scene, and
  * real per-word timings for the scene's own script tokens,

written to ``<scene>.timing.json`` in the exact format render/QA already
consume (``units`` with per-role start/end, ``words``).

Providers
---------
``edge``        existing Edge path (unitized or scene-continuous); default.
``prerendered`` an external, already-produced narration: a human recording
                or an HD/generative TTS render done elsewhere. Per scene the
                directory holds ``<scene_id>.wav|.mp3|.m4a|.flac`` plus
                ``<scene_id>.words.json`` (``[{"text","start","end"}, ...]``)
                -- e.g. ElevenLabs/Azure word timestamps, or a forced
                alignment from a maintained aligner such as WhisperX or
                stable-ts. Fail-closed validation: the words must match the
                scene script token-for-token, be monotonic and fit the audio.
``elevenlabs``  ElevenLabs' official Python SDK (``pip install elevenlabs``,
                MIT) ``text_to_speech.convert_with_timestamps``; its
                character alignment is mapped to script words and fed through
                the same continuous-scene pipeline Edge uses. Needs
                ELEVENLABS_API_KEY and a voice id; never committed, never
                silently replaced by Edge if missing.
``azure_hd``    Microsoft's official Azure Speech SDK using Dragon HD.
                Korean defaults to ``ko-KR-Hyunsu:DragonHDLatestNeural``.
                Native WordBoundary events are aggregated to the script tokens;
                missing credentials/timings fail closed and never fall back.

Environment overrides (so CI/operators can inject a voice without editing a
manifest): SHORTS_NARRATION_PROVIDER, SHORTS_NARRATION_DIR,
SHORTS_NARRATION_VOICE.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .prosody import PhraseSpec
from .timing import WordTiming

PROVIDERS = ("edge", "prerendered", "elevenlabs", "azure_hd")
_AUDIO_SUFFIXES = (".wav", ".mp3", ".m4a", ".flac")
ELEVENLABS_DEFAULT_MODEL = "eleven_multilingual_v2"
AZURE_HD_DEFAULT_VOICE = "ko-KR-Hyunsu:DragonHDLatestNeural"


@dataclass(frozen=True)
class NarrationConfig:
    provider: str = "edge"
    directory: str | None = None
    voice: str | None = None


def resolve_config(project) -> NarrationConfig:
    provider = os.environ.get("SHORTS_NARRATION_PROVIDER") or getattr(project, "narration_provider", "edge") or "edge"
    directory = os.environ.get("SHORTS_NARRATION_DIR") or getattr(project, "narration_dir", None)
    voice = os.environ.get("SHORTS_NARRATION_VOICE") or getattr(project, "narration_voice", None)
    if provider not in PROVIDERS:
        raise ValueError(f"unknown narration provider {provider!r}; expected one of {PROVIDERS}")
    if provider == "prerendered" and not directory:
        raise ValueError("prerendered narration requires narration_dir / SHORTS_NARRATION_DIR")
    if provider == "azure_hd" and not voice:
        voice = AZURE_HD_DEFAULT_VOICE
    return NarrationConfig(provider, directory, voice)


def _norm_token(token: str) -> str:
    return re.sub(r"[^\w]", "", token).lower()


def _script_tokens(phrases: list[PhraseSpec]) -> list[list[str]]:
    return [re.findall(r"[^\s]+", p.text) for p in phrases]


def _audio_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True, timeout=60,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def words_to_units(phrases: list[PhraseSpec], words: list[WordTiming], rate: str = "external") -> list[dict]:
    """Per-phrase role timing from real word timings (token counts, no guessing)."""
    units, cursor = [], 0
    for phrase, tokens in zip(phrases, _script_tokens(phrases)):
        chunk = words[cursor:cursor + len(tokens)]
        if len(chunk) != len(tokens):
            raise RuntimeError("narration word/phrase mapping drifted; refusing to invent role timing")
        cursor += len(tokens)
        units.append({
            "role": phrase.role, "text": phrase.text, "rate": rate, "base_unit_rate": rate,
            "boundary": phrase.boundary, "focus": phrase.focus,
            "start": chunk[0].start, "end": chunk[-1].end,
        })
    if cursor != len(words):
        raise RuntimeError("narration left unmapped words; refusing approximate role timing")
    return units


def validate_external_words(phrases: list[PhraseSpec], raw_words: list[dict], audio_seconds: float) -> list[WordTiming]:
    """Fail-closed checks for an externally produced narration.

    Captions and narration-cued visual cuts are bound to these words, so a
    mismatched transcript or invented timing would silently break the
    caption/semantic gates; reject instead.
    """
    expected = [t for tokens in _script_tokens(phrases) for t in tokens]
    if len(raw_words) != len(expected):
        raise ValueError(f"pre-rendered narration has {len(raw_words)} words, script has {len(expected)}")
    words, prev_start = [], 0.0
    for i, (raw, token) in enumerate(zip(raw_words, expected)):
        text = str(raw.get("text", ""))
        if _norm_token(text) != _norm_token(token):
            raise ValueError(f"pre-rendered word {i} {text!r} does not match script token {token!r}")
        start, end = float(raw["start"]), float(raw["end"])
        if start < 0 or end < start or start < prev_start:
            raise ValueError(f"pre-rendered word {i} {text!r} has non-monotonic timing {start}-{end}")
        if end > audio_seconds + 0.05:
            raise ValueError(f"pre-rendered word {i} ends at {end:.2f}s after the audio ({audio_seconds:.2f}s)")
        words.append(WordTiming(token, start, end))  # display the script's own spelling
        prev_start = start
    return words


def load_prerendered_scene(phrases: list[PhraseSpec], scene_id: str, directory: str | Path,
                           audio_path: Path, timing_path: Path) -> list[WordTiming]:
    directory = Path(directory)
    src = next((directory / f"{scene_id}{s}" for s in _AUDIO_SUFFIXES if (directory / f"{scene_id}{s}").is_file()), None)
    words_file = directory / f"{scene_id}.words.json"
    if src is None or not words_file.is_file():
        raise FileNotFoundError(f"pre-rendered narration for {scene_id!r} needs audio + {words_file.name} in {directory}")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    # Re-encode once with FFmpeg so the rest of the pipeline sees the same
    # container it gets from Edge; no trimming -- the timings refer to src.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "44100",
                    "-c:a", "libmp3lame", "-q:a", "2", str(audio_path)], check=True, capture_output=True, timeout=180)
    seconds = _audio_duration(src)
    words = validate_external_words(phrases, json.loads(words_file.read_text(encoding="utf-8")), seconds)
    timing_path.write_text(json.dumps({
        "source": "prerendered", "provider_audio": str(src), "voice": None,
        "units": words_to_units(phrases, words), "gaps_seconds": [], "raw": [],
        "words": [w.__dict__ for w in words], "breaths": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return words


def alignment_to_words(text: str, characters: list[str], starts: list[float], ends: list[float]) -> list[WordTiming]:
    """Map a provider's per-character alignment onto whitespace tokens of `text`."""
    if "".join(characters) != text:
        raise ValueError("provider alignment characters do not reproduce the requested text")
    words, current, w_start, w_end = [], "", None, None
    for ch, s, e in zip(characters, starts, ends):
        if ch.isspace():
            if current:
                words.append(WordTiming(current, w_start, w_end))
            current, w_start, w_end = "", None, None
            continue
        if not current:
            w_start = float(s)
        current += ch
        w_end = float(e)
    if current:
        words.append(WordTiming(current, w_start, w_end))
    return words


def _field(obj, *names):
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    raise KeyError(names[0])


def elevenlabs_synthesizer(voice_id: str, client=None, model_id: str = ELEVENLABS_DEFAULT_MODEL):
    """Return an async ``synthesize(text, voice, rate, pitch, volume)`` that
    tts.synthesize_continuous_plan can use in place of Edge.

    Uses the official SDK; the API key comes only from the environment.
    """
    if client is None:
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise RuntimeError("ELEVENLABS_API_KEY is not set; refusing to fall back silently to Edge")
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("install the official SDK: pip install 'shorts-studio[hd-tts]'") from exc
        client = ElevenLabs(api_key=key)

    async def synthesize(text, voice, rate, pitch, volume):
        resp = client.text_to_speech.convert_with_timestamps(voice_id=voice_id, text=text, model_id=model_id)
        audio = base64.b64decode(_field(resp, "audio_base_64", "audio_base64"))
        al = _field(resp, "alignment")
        words = alignment_to_words(
            text, list(_field(al, "characters")),
            list(_field(al, "character_start_times_seconds")),
            list(_field(al, "character_end_times_seconds")),
        )
        return audio, words

    return synthesize


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    """Whitespace-token spans used to aggregate Azure's finer word-boundary events."""
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[^\s]+", text)]


def azure_events_to_words(text: str, events: list[dict]) -> list[WordTiming]:
    """Aggregate Azure Speech word-boundary events onto the script's whitespace tokens.

    Azure may emit punctuation or multiple boundary events inside one Korean token.
    Captions are authored from whitespace tokens, so group provider events by their
    source-text offsets instead of guessing from total duration.
    """
    out = []
    for token, start_char, end_char in _token_spans(text):
        relevant = [
            e for e in events
            if start_char <= int(e["text_offset"]) < end_char
            and float(e["end"]) >= float(e["start"])
        ]
        if not relevant:
            raise RuntimeError(
                f"Azure Speech returned no boundary event for token {token!r} "
                f"at chars {start_char}:{end_char}; refusing approximate timing"
            )
        out.append(WordTiming(
            token,
            min(float(e["start"]) for e in relevant),
            max(float(e["end"]) for e in relevant),
        ))
    if not out:
        raise RuntimeError("Azure Speech returned no usable word boundaries")
    return out


def azure_speech_synthesizer(
    voice: str = AZURE_HD_DEFAULT_VOICE,
    *,
    speechsdk=None,
    subscription: str | None = None,
    region: str | None = None,
):
    """Return an async synthesizer backed by Microsoft's official Azure Speech SDK.

    The HD provider is fail-closed: missing credentials, SDK errors, canceled
    synthesis or incomplete word-boundary events raise. It never falls back to Edge.

    Credentials are read from AZURE_SPEECH_KEY/AZURE_SPEECH_REGION first, with
    SPEECH_KEY/SPEECH_REGION accepted for compatibility with Microsoft's examples.
    """
    subscription = subscription or os.environ.get("AZURE_SPEECH_KEY") or os.environ.get("SPEECH_KEY")
    region = region or os.environ.get("AZURE_SPEECH_REGION") or os.environ.get("SPEECH_REGION")
    if not subscription or not region:
        raise RuntimeError(
            "Azure HD narration requires AZURE_SPEECH_KEY and AZURE_SPEECH_REGION "
            "(or SPEECH_KEY/SPEECH_REGION); refusing to fall back silently to Edge"
        )
    if speechsdk is None:
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "install the official SDK: pip install 'shorts-studio[azure-tts]'"
            ) from exc

    async def synthesize(text, _voice, rate, pitch, volume):
        config = speechsdk.SpeechConfig(subscription=subscription, region=region)
        config.speech_synthesis_voice_name = voice
        output_enum = getattr(
            getattr(speechsdk, "SpeechSynthesisOutputFormat", object()),
            "Audio48Khz192KBitRateMonoMp3",
            None,
        )
        if output_enum is not None and hasattr(config, "set_speech_synthesis_output_format"):
            config.set_speech_synthesis_output_format(output_enum)

        synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
        raw_events: list[dict] = []

        def on_boundary(evt):
            # Azure reports 100-ns ticks for audio_offset and duration.
            start = float(evt.audio_offset) / 10_000_000.0
            duration = max(0.0, float(getattr(evt, "duration", 0))) / 10_000_000.0
            raw_events.append({
                "text": str(getattr(evt, "text", "")),
                "text_offset": int(getattr(evt, "text_offset", -1)),
                "word_length": int(getattr(evt, "word_length", 0)),
                "start": start,
                "end": start + duration,
            })

        synthesizer.synthesis_word_boundary.connect(on_boundary)
        result = synthesizer.speak_text_async(text).get()
        expected_reason = getattr(getattr(speechsdk, "ResultReason", object()), "SynthesizingAudioCompleted", None)
        if expected_reason is not None and getattr(result, "reason", None) != expected_reason:
            details = getattr(getattr(result, "cancellation_details", None), "error_details", None)
            raise RuntimeError(f"Azure Speech synthesis failed: {details or getattr(result, 'reason', 'unknown')}")
        audio = bytes(getattr(result, "audio_data", b""))
        if not audio:
            raise RuntimeError("Azure Speech returned empty audio")
        return audio, azure_events_to_words(text, raw_events)

    return synthesize
