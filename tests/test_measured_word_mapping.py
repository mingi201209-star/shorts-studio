import asyncio

import pytest

from shorts_studio.prosody import PhraseSpec, STRONG_BOUNDARY
from shorts_studio.timing import WordTiming, map_measured_words
from shorts_studio import tts


def test_measured_mapping_preserves_real_pauses_and_script_punctuation():
    events = [WordTiming("물이", .2, .5), WordTiming("쌓입니다", 1.1, 1.6)]
    assert map_measured_words("물이 쌓입니다.", events) == [
        WordTiming("물이", .2, .5), WordTiming("쌓입니다.", 1.1, 1.6),
    ]


def test_subword_events_group_without_interpolating_timing():
    assert map_measured_words("타이어가 뜹니다.", [
        WordTiming("타이어", .1, .4), WordTiming("가", .45, .6),
        WordTiming("뜹니다", 1.2, 1.8),
    ]) == [WordTiming("타이어가", .1, .6), WordTiming("뜹니다.", 1.2, 1.8)]


@pytest.mark.parametrize("events,reason", [
    ([WordTiming("물이 쌓입니다.", .1, 1.8)], "spans multiple"),
    ([WordTiming("고무가", .1, .5), WordTiming("움직입니다.", .8, 1.8)], "does not match"),
    ([WordTiming("물이", .1, .5)], "cover every"),
    ([WordTiming("물이", .1, .5), WordTiming("쌓입니다", .8, 1.8),
      WordTiming("다시", 1.9, 2.3)], "does not match"),
    ([], "cover every"),
])
def test_measured_mapping_rejects_unverifiable_word_timing(events, reason):
    with pytest.raises(ValueError, match=reason):
        map_measured_words("물이 쌓입니다.", events)


@pytest.mark.parametrize("start,end", [
    (float("nan"), .5), (.1, float("nan")),
    (float("inf"), .5), (.1, float("inf")),
    (-.1, .5), (.5, .5), (.6, .5),
])
def test_measured_mapping_rejects_invalid_timestamp(start, end):
    with pytest.raises(ValueError, match="invalid measured boundary"):
        map_measured_words("물이", [WordTiming("물이", start, end)])


def test_measured_mapping_rejects_backward_events():
    with pytest.raises(ValueError, match="invalid measured boundary"):
        map_measured_words("물이 쌓입니다.", [
            WordTiming("물이", .4, .6), WordTiming("쌓입니다", .2, .8),
        ])


def test_continuous_narration_rejects_sentence_timing_before_overwriting_audio(monkeypatch, tmp_path):
    audio, timing = tmp_path / "scene.mp3", tmp_path / "scene.timing.json"
    audio.write_bytes(b"previous valid audio")
    timing.write_text("previous valid timing")
    async def provider(*args):
        return b"new audio", [WordTiming("물이 쌓입니다.", .1, 1.8)]
    def refuse_trim(*args):
        pytest.fail("unverified timings must be rejected before processing audio")
    monkeypatch.setattr(tts, "_trim_tts_edge_silence", refuse_trim)
    with pytest.raises(ValueError, match="spans multiple"):
        asyncio.run(tts.synthesize_continuous_plan(
            [PhraseSpec("HOOK", "물이 쌓입니다.", STRONG_BOUNDARY)],
            audio, timing, synthesize=provider,
        ))
    assert audio.read_bytes() == b"previous valid audio"
    assert timing.read_text() == "previous valid timing"
    assert not (tmp_path / "scene_provider_raw.mp3").exists()
