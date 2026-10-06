from __future__ import annotations

import asyncio
import json
import shutil

import pytest

from shorts_studio.models import Project
from shorts_studio.prosody import PhraseSpec, STRONG_BOUNDARY
from shorts_studio.timing import WordTiming
import shorts_studio.tts as tts


def _minimal_project(**extra):
    data = {
        "title": "x",
        "scenes": [{
            "id": "s1",
            "narration": "문장입니다.",
            "visual_description": "x",
            "asset": "x.png",
        }],
    }
    data.update(extra)
    return Project.model_validate(data)


def test_tts_continuity_mode_defaults_to_unitized():
    assert _minimal_project().tts_continuity_mode == "unitized"


def test_scene_continuous_is_opt_in_and_incompatible_with_procedural_breaths():
    p = _minimal_project(tts_continuity_mode="scene_continuous")
    assert p.tts_continuity_mode == "scene_continuous"
    with pytest.raises(ValueError, match="cannot be combined"):
        _minimal_project(
            tts_continuity_mode="scene_continuous",
            enable_subtle_breaths=True,
        )


def test_continuous_plan_uses_one_provider_call_and_preserves_role_timing(monkeypatch, tmp_path):
    calls = []

    async def fake_synthesize(text, voice, rate, pitch, volume):
        calls.append({
            "text": text,
            "voice": voice,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
        })
        tokens = text.split()
        words = [
            WordTiming(token, i * 0.25, i * 0.25 + 0.18)
            for i, token in enumerate(tokens)
        ]
        return b"provider-audio", words

    def fake_trim(raw_path, out_path):
        shutil.copyfile(raw_path, out_path)
        return out_path, 0.0

    monkeypatch.setattr(tts, "_synthesize_sentence", fake_synthesize)
    monkeypatch.setattr(tts, "_trim_tts_edge_silence", fake_trim)
    monkeypatch.setattr(tts, "_ffmpeg_duration_seconds", lambda path: 10.0)

    phrases = [
        PhraseSpec(role="HOOK", text="실은 도로에 닿지 않습니다.", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="CRISIS", text="방금 전엔 멀쩡했어요.", boundary=STRONG_BOUNDARY),
        PhraseSpec(role="REVEAL", text="물이 쌓입니다.", boundary=STRONG_BOUNDARY),
    ]
    audio = tmp_path / "scene.mp3"
    timing = tmp_path / "scene.timing.json"

    words = asyncio.run(tts.synthesize_continuous_plan(phrases, audio, timing))

    assert len(calls) == 1
    assert calls[0]["text"] == " ".join(p.text for p in phrases)
    assert audio.read_bytes() == b"provider-audio"
    assert len(words) == len(calls[0]["text"].split())

    data = json.loads(timing.read_text(encoding="utf-8"))
    assert data["source"] == "korean-speech-planner-v3-continuous"
    assert data["gaps_seconds"] == []
    assert data["breaths"] == []
    assert [u["role"] for u in data["units"]] == ["HOOK", "CRISIS", "REVEAL"]
    assert data["units"][0]["start"] < data["units"][1]["start"] < data["units"][2]["start"]
    assert data["units"][0]["end"] <= data["units"][1]["start"]
    assert data["units"][1]["end"] <= data["units"][2]["start"]
