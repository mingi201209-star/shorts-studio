"""Korean TTS timing must stay anchored to real provider boundary events -- never
fall back to guessing durations from character counts.
"""
import asyncio, sys, types
import pytest
from shorts_studio.timing import WordTiming
from shorts_studio.tts import _map_boundaries_to_script, edge_tts_with_boundaries

def test_word_count_match_uses_boundaries_directly():
    text = "안녕 세상"
    boundaries = [WordTiming("안녕", 0.10, 0.40), WordTiming("세상", 0.42, 0.90)]
    words = _map_boundaries_to_script(text, boundaries)
    assert [w.start for w in words] == [0.10, 0.42]
    assert [w.end for w in words] == [0.40, 0.90]

def test_korean_sentence_boundary_interpolation_stays_within_real_measured_span():
    text = "안녕하세요 오늘은 날씨가 정말 좋습니다"
    boundaries = [WordTiming(text, 0.5, 2.5)]  # a single sentence-boundary event
    words = _map_boundaries_to_script(text, boundaries)
    assert words, "must produce timings from the real boundary, not skip it"
    assert words[0].start == pytest.approx(0.5)
    assert words[-1].end == pytest.approx(2.5)
    for a, b in zip(words, words[1:]):
        assert a.end <= b.start + 1e-9
    assert all(0.5 - 1e-9 <= w.start <= 2.5 + 1e-9 for w in words)
    assert all(0.5 - 1e-9 <= w.end <= 2.5 + 1e-9 for w in words)

def test_empty_boundaries_produce_no_words_never_guessed():
    assert _map_boundaries_to_script("안녕하세요", []) == []

def test_tts_raises_without_any_boundary_events_no_char_count_fallback(tmp_path, monkeypatch):
    fake_edge_tts = types.ModuleType("edge_tts")
    class FakeCommunicate:
        def __init__(self, *a, **k): pass
        async def stream(self):
            return
            yield {}  # pragma: no cover - makes this an async generator with zero items
    fake_edge_tts.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge_tts)
    with pytest.raises(RuntimeError):
        asyncio.run(edge_tts_with_boundaries("안녕하세요", tmp_path / "a.mp3", tmp_path / "a.json"))

def test_tts_uses_real_boundary_timing_not_character_count(tmp_path, monkeypatch):
    fake_edge_tts = types.ModuleType("edge_tts")
    class FakeCommunicate:
        def __init__(self, *a, **k): pass
        async def stream(self):
            yield {"type": "audio", "data": b"\x00\x01"}
            # Real provider boundary: 0.3s start, 0.7s duration -- deliberately NOT
            # proportional to character count, to prove we trust the provider.
            yield {"type": "SentenceBoundary", "text": "안녕하세요", "offset": 3_000_000, "duration": 7_000_000}
    fake_edge_tts.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge_tts)
    words = asyncio.run(edge_tts_with_boundaries("안녕하세요", tmp_path / "a.mp3", tmp_path / "a.json"))
    assert words[0].start == pytest.approx(0.3)
    assert words[-1].end == pytest.approx(1.0)
