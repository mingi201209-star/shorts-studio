from __future__ import annotations

import asyncio
import base64
import json
import shutil
import subprocess

import pytest

from shorts_studio import narration
from shorts_studio.models import Project
from shorts_studio.prosody import PhraseSpec, STRONG_BOUNDARY
import shorts_studio.tts as tts

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg required")


def _phrases():
    return [
        PhraseSpec("HOOK", "빗길에선 타이어가 돌고 있어도,", STRONG_BOUNDARY),
        PhraseSpec("CRISIS", "문제는 물입니다.", STRONG_BOUNDARY),
    ]


def _words(offset=0.0):
    tokens = ["빗길에선", "타이어가", "돌고", "있어도,", "문제는", "물입니다."]
    return [{"text": t, "start": offset + i * 0.3, "end": offset + i * 0.3 + 0.25} for i, t in enumerate(tokens)]


def _project(**extra):
    data = {"title": "x", "scenes": [{"id": "s1", "narration": "문장입니다.", "visual_description": "x", "asset": "x.png"}]}
    data.update(extra)
    return Project.model_validate(data)


def test_default_provider_is_edge_so_existing_manifests_are_unchanged(monkeypatch):
    for k in ("SHORTS_NARRATION_PROVIDER", "SHORTS_NARRATION_DIR", "SHORTS_NARRATION_VOICE"):
        monkeypatch.delenv(k, raising=False)
    p = _project()
    assert p.narration_provider == "edge"
    assert narration.resolve_config(p) == narration.NarrationConfig("edge", None, None)


def test_env_override_and_fail_closed_config(monkeypatch, tmp_path):
    monkeypatch.setenv("SHORTS_NARRATION_PROVIDER", "prerendered")
    monkeypatch.delenv("SHORTS_NARRATION_DIR", raising=False)
    with pytest.raises(ValueError, match="requires narration_dir"):
        narration.resolve_config(_project())
    monkeypatch.setenv("SHORTS_NARRATION_DIR", str(tmp_path))
    assert narration.resolve_config(_project()).directory == str(tmp_path)
    monkeypatch.setenv("SHORTS_NARRATION_PROVIDER", "made-up")
    with pytest.raises(ValueError, match="unknown narration provider"):
        narration.resolve_config(_project())


def test_external_words_must_match_script_and_be_monotonic():
    good = narration.validate_external_words(_phrases(), _words(), audio_seconds=3.0)
    assert [w.text for w in good][-1] == "물입니다."
    bad = _words(); bad[1]["text"] = "자동차가"
    with pytest.raises(ValueError, match="does not match script"):
        narration.validate_external_words(_phrases(), bad, 3.0)
    with pytest.raises(ValueError, match="words, script has"):
        narration.validate_external_words(_phrases(), _words()[:-1], 3.0)
    back = _words(); back[3]["start"] = 0.1
    with pytest.raises(ValueError, match="non-monotonic"):
        narration.validate_external_words(_phrases(), back, 3.0)
    with pytest.raises(ValueError, match="after the audio"):
        narration.validate_external_words(_phrases(), _words(offset=2.0), 3.0)


def test_punctuation_differences_do_not_break_matching():
    w = _words(); w[3]["text"] = "있어도"; w[5]["text"] = "물입니다"
    out = narration.validate_external_words(_phrases(), w, 3.0)
    # captions keep the script's own spelling/punctuation
    assert out[3].text == "있어도," and out[5].text == "물입니다."


def test_role_units_come_from_real_word_timing():
    words = narration.validate_external_words(_phrases(), _words(), 3.0)
    units = narration.words_to_units(_phrases(), words)
    assert [u["role"] for u in units] == ["HOOK", "CRISIS"]
    assert units[0]["start"] == 0.0 and units[1]["start"] == pytest.approx(1.2)


def _tone(path, seconds=2.4):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
                    str(path)], check=True)
    return path


@needs_ffmpeg
def test_prerendered_scene_writes_standard_timing_json(tmp_path):
    d = tmp_path / "voice"; d.mkdir()
    _tone(d / "s_hook.wav")
    (d / "s_hook.words.json").write_text(json.dumps(_words(), ensure_ascii=False), encoding="utf-8")
    audio, timing = tmp_path / "s_hook.mp3", tmp_path / "s_hook.timing.json"
    words = narration.load_prerendered_scene(_phrases(), "s_hook", d, audio, timing)
    assert audio.is_file() and len(words) == 6
    data = json.loads(timing.read_text(encoding="utf-8"))
    assert data["source"] == "prerendered"
    assert [u["role"] for u in data["units"]] == ["HOOK", "CRISIS"]


@needs_ffmpeg
def test_prerendered_scene_missing_files_fail_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        narration.load_prerendered_scene(_phrases(), "s_hook", tmp_path, tmp_path / "a.mp3", tmp_path / "t.json")


def test_alignment_to_words_and_rejects_mismatched_alignment():
    text = "물이 쌓입니다."
    chars = list(text)
    starts = [i * 0.1 for i in range(len(chars))]
    ends = [s + 0.08 for s in starts]
    words = narration.alignment_to_words(text, chars, starts, ends)
    assert [w.text for w in words] == ["물이", "쌓입니다."]
    assert words[1].start == pytest.approx(0.3)
    with pytest.raises(ValueError):
        narration.alignment_to_words(text, chars[:-1], starts[:-1], ends[:-1])


def test_elevenlabs_requires_key_and_never_falls_back(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        narration.elevenlabs_synthesizer("voice")


@needs_ffmpeg
def test_elevenlabs_adapter_feeds_the_same_continuous_pipeline(tmp_path):
    mp3 = tmp_path / "tone.mp3"
    _tone(mp3, 3.0)
    calls = []

    class FakeTTS:
        def convert_with_timestamps(self, voice_id, text, model_id):
            calls.append((voice_id, text, model_id))
            chars = list(text)
            starts = [i * 0.08 for i in range(len(chars))]
            return {"audio_base_64": base64.b64encode(mp3.read_bytes()).decode(),
                    "alignment": {"characters": chars, "character_start_times_seconds": starts,
                                  "character_end_times_seconds": [s + 0.07 for s in starts]}}

    class FakeClient:
        text_to_speech = FakeTTS()

    synth = narration.elevenlabs_synthesizer("v1", client=FakeClient())
    timing = tmp_path / "t.json"
    words = asyncio.run(tts.synthesize_continuous_plan(_phrases(), tmp_path / "out.mp3", timing,
                                                       voice="v1", synthesize=synth, source="elevenlabs-continuous"))
    assert len(calls) == 1 and calls[0][0] == "v1"
    assert [w.text for w in words][0] == "빗길에선"
    data = json.loads(timing.read_text(encoding="utf-8"))
    assert data["source"] == "elevenlabs-continuous"
    assert [u["role"] for u in data["units"]] == ["HOOK", "CRISIS"]
