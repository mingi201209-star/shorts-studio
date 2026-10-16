"""One take for a whole Short: meaning-ranked pauses and per-scene cuts."""
from __future__ import annotations

import asyncio
import io
import json
import shutil

import numpy as np
import pytest

from shorts_studio import pause_plan as pp
from shorts_studio.models import Project
from shorts_studio.prosody import PhraseSpec, STRONG_BOUNDARY
from shorts_studio.timing import WordTiming

librosa = pytest.importorskip("librosa")
sf = pytest.importorskip("soundfile")

SR = 16000


def _tone(seconds, f=150.0):
    t = np.arange(int(seconds * SR)) / SR
    return (0.3 * np.sin(2 * np.pi * f * t)).astype(np.float32)


def _take(tokens, gaps_after):
    """Audio of 0.4 s per word; `gaps_after[i]` seconds of silence follow word i.

    Words are timed like Edge: a sentence-final end runs 0.3 s into the pause
    and every start sits 0.1 s before the audible onset."""
    parts, words, t = [], [], 0.0
    for i, tok in enumerate(tokens):
        parts.append(_tone(0.4, 140 + 7 * i))
        gap = gaps_after.get(i, 0.0)
        start = max(0.0, t - 0.1) if i else 0.0
        end = t + 0.4 + (min(0.3, gap) if pp.is_sentence_end(tok) else 0.0)
        words.append((tok, start, end))
        t += 0.4
        if gap:
            parts.append(np.zeros(int(gap * SR), np.float32))
            t += gap
    return np.concatenate(parts), words


TOKENS = ["빙하는", "파랗습니다.", "눈은", "하얗습니다.", "비밀은", "빛입니다,", "얼음은", "붉은빛을", "먹습니다."]
GAPS = {1: 0.78, 3: 0.74, 5: 0.48, 6: 0.20}
SCENE_ENDS = [3]


def test_sentence_ends_scene_turns_and_clauses_get_ranked_targets():
    y, words = _take(TOKENS, GAPS)
    silences = pp.detect_silences(y, SR, min_gap=0.12)
    assert len(silences) == 4
    targets = [t for _a, _b, t in pp.plan_take_gaps(silences, words, SCENE_ENDS)]
    assert targets[0] == pp.TAKE_PAUSES["sentence"]
    assert targets[1] == pp.TAKE_PAUSES["scene"]
    assert targets[2] == pp.TAKE_CLAUSE_MAX            # a comma pause is capped
    assert abs(targets[3] - 0.20) < 0.03               # a short clause pause is left alone
    assert pp.TAKE_PAUSES["scene"] > pp.TAKE_PAUSES["sentence"] > pp.TAKE_CLAUSE_MAX


def test_scene_turn_without_a_pause_fails_closed():
    y, words = _take(TOKENS, {1: 0.78, 5: 0.48})       # no pause after the scene end
    silences = pp.detect_silences(y, SR, min_gap=0.12)
    with pytest.raises(ValueError, match="scene turn"):
        pp.plan_take_gaps(silences, words, SCENE_ENDS)


@pytest.mark.parametrize("ends", [[8], [-1], [9]])
def test_scene_end_must_leave_a_following_scene(ends):
    y, words = _take(TOKENS, GAPS)
    with pytest.raises(ValueError):
        pp.plan_take_gaps(pp.detect_silences(y, SR, min_gap=0.12), words, ends)


def test_split_take_cuts_scenes_like_render_and_keeps_speech_verbatim():
    y, words = _take(TOKENS, GAPS)
    gaps = pp.plan_take_gaps(pp.detect_silences(y, SR, min_gap=0.12), words, SCENE_ENDS)
    out, scenes = pp.split_take(y, SR, words, SCENE_ENDS, gaps)
    assert [len(s.words) for s in scenes] == [4, 5]
    assert [w[0] for s in scenes for w in s.words] == TOKENS
    # A scene lasts exactly to its last word end + 0.08 s -- render's own rule.
    assert abs((scenes[0].end - scenes[0].start) - (scenes[0].words[-1][2] + 0.08)) < 1.5 / SR
    assert scenes[0].end == scenes[1].start and scenes[1].end == len(out) / SR
    # The rest of the turn pause opens the next scene.
    assert scenes[1].words[0][1] > 0.1
    # Word times stay monotonic and inside their scene.
    for s in scenes:
        for (_, a0, e0), (_, a1, _e1) in zip(s.words, s.words[1:]):
            assert a0 < e0 <= a1
        assert s.words[-1][2] <= s.end - s.start
    # Only silence was edited: voiced sample count is unchanged.
    assert abs(int((np.abs(y) > 1e-3).sum()) - int((np.abs(out) > 1e-3).sum())) < 0.02 * SR
    joined = pp.detect_silences(out, SR, min_gap=0.12)
    measured = [round(b - a, 2) for a, b in joined]
    assert abs(measured[0] - 0.50) < 0.03 and abs(measured[1] - 0.65) < 0.03 and abs(measured[2] - 0.30) < 0.03


def test_short_continuous_is_opt_in_and_excludes_procedural_breaths():
    base = {"title": "x", "scenes": [{"id": "s1", "narration": "문장입니다.", "visual_description": "x", "asset": "x.png"}]}
    assert Project.model_validate(base).tts_continuity_mode == "unitized"
    assert Project.model_validate({**base, "tts_continuity_mode": "short_continuous"}).tts_continuity_mode == "short_continuous"
    with pytest.raises(ValueError, match="cannot be combined"):
        Project.model_validate({**base, "tts_continuity_mode": "short_continuous", "enable_subtle_breaths": True})


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_one_provider_call_feeds_the_prerendered_contract(monkeypatch, tmp_path):
    import shorts_studio.tts as tts
    from shorts_studio.narration import load_prerendered_scene

    y, words = _take(TOKENS, GAPS)
    calls = []

    async def fake_edge(text, voice, rate, pitch, volume):
        calls.append(text)
        buf = io.BytesIO()
        sf.write(buf, y, SR, format="WAV", subtype="PCM_16")
        return buf.getvalue(), [WordTiming(t, s, e) for t, s, e in words]

    def fake_trim(raw_path, out_path):
        shutil.copyfile(raw_path, out_path)
        return out_path, 0.0

    monkeypatch.setattr(tts, "_synthesize_sentence", fake_edge)
    monkeypatch.setattr(tts, "_trim_tts_edge_silence", fake_trim)
    scenes = [
        ("s_hook", [PhraseSpec(role="HOOK", text=" ".join(TOKENS[:2]), boundary=STRONG_BOUNDARY),
                    PhraseSpec(role="HOOK", text=" ".join(TOKENS[2:4]), boundary=STRONG_BOUNDARY)]),
        ("s_reveal", [PhraseSpec(role="REVEAL", text=" ".join(TOKENS[4:]), boundary=STRONG_BOUNDARY)]),
    ]
    take = tmp_path / "short_take"
    report = asyncio.run(tts.synthesize_short_take(scenes, take))
    assert len(calls) == 1 and calls[0] == " ".join(TOKENS)
    assert [p["now"] for p in report["pauses"]][:2] == [0.5, 0.65]
    for scene_id, plan in scenes:
        audio, timing = tmp_path / f"{scene_id}.mp3", tmp_path / f"{scene_id}.timing.json"
        got = load_prerendered_scene(plan, scene_id, take, audio, timing, source="edge-short-take", voice="v")
        record = json.loads(timing.read_text(encoding="utf-8"))
        assert record["source"] == "edge-short-take" and record["voice"] == "v"
        assert [w.text for w in got] == " ".join(p.text for p in plan).split()


def test_provider_times_inside_a_pause_follow_the_splice():
    """Edge starts a word ~0.1 s before its onset; after a pause is shortened
    the start must still lead the moved onset by the same 0.1 s."""
    y, words = _take(TOKENS, GAPS)
    gaps = pp.plan_take_gaps(pp.detect_silences(y, SR, min_gap=0.12), words, SCENE_ENDS)
    out, _ = pp.retime_silences(y, SR, gaps)
    to_new = pp.retime_map(SR, gaps)
    onsets = [b for _a, b in pp.detect_silences(out, SR, min_gap=0.12)]
    # word 2 follows the first (shortened) sentence pause, word 4 the scene turn
    assert abs((onsets[0] - to_new(words[2][1])) - 0.1) < 0.02
    assert abs((onsets[1] - to_new(words[4][1])) - 0.1) < 0.02
    # speech before any edit is untouched
    assert to_new(words[1][1]) == pytest.approx(words[1][1], abs=1 / SR)
