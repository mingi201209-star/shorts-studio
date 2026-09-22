"""Korean TTS timing must stay anchored to real provider boundary events -- never
fall back to guessing durations from character counts.
"""
import asyncio, shutil, sys, types
import pytest
from shorts_studio.timing import WordTiming
from shorts_studio.tts import (
    DEFAULT_KO_RATE, SENTENCE_GAP_SECONDS,
    _map_boundaries_to_script, _prepare_korean_speech, _split_sentences,
    edge_tts_with_boundaries,
)

requires_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requires a real ffmpeg binary")

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

# --- number/punctuation preservation -----------------------------------
# Root cause of a real mispronunciation: the old unconditional
# r"\s*([,.;!?])\s*" -> r"\1 " substitution turned "1,830" into "1, 830",
# which Edge would read as two separate numbers instead of one.

def test_thousands_separator_comma_is_preserved():
    assert _prepare_korean_speech("물탱크에서 1,830번 더 반복하자") == "물탱크에서 1,830번 더 반복하자"

def test_thousands_separator_preserved_with_larger_number():
    assert "12,345" in _prepare_korean_speech("측정값은 12,345 였습니다")

def test_normal_sentence_comma_still_gets_spacing():
    out = _prepare_korean_speech("그런데,비행기가 부서졌습니다")
    assert out == "그런데, 비행기가 부서졌습니다"

def test_sentence_terminators_still_get_spacing():
    out = _prepare_korean_speech("정말입니다.놀랍죠?")
    assert out == "정말입니다. 놀랍죠 ?" or out == "정말입니다. 놀랍죠?"

# --- sentence splitting ---------------------------------------------------

def test_split_sentences_splits_on_terminal_punctuation():
    parts = _split_sentences("코멧이 등장했습니다. 얼마 뒤 사고가 났습니다.")
    assert parts == ["코멧이 등장했습니다.", "얼마 뒤 사고가 났습니다."]

def test_split_sentences_single_sentence_stays_one_part():
    assert _split_sentences("안녕하세요") == ["안녕하세요"]

def test_split_sentences_handles_question_and_exclamation():
    parts = _split_sentences("정말요? 대단하네요! 그렇습니다.")
    assert len(parts) == 3

# --- WordBoundary is actually requested (not the old SentenceBoundary-only) --

def test_synthesis_requests_word_boundary_not_sentence_boundary(tmp_path, monkeypatch):
    fake_edge_tts = types.ModuleType("edge_tts")
    captured = {}
    class FakeCommunicate:
        def __init__(self, text, voice, **k):
            captured["boundary"] = k.get("boundary")
        async def stream(self):
            yield {"type": "audio", "data": b"\x00"}
            yield {"type": "WordBoundary", "text": "안녕", "offset": 0, "duration": 4_000_000}
    fake_edge_tts.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge_tts)
    asyncio.run(edge_tts_with_boundaries("안녕", tmp_path / "a.mp3", tmp_path / "a.json"))
    assert captured["boundary"] == "WordBoundary"

# --- multi-sentence: real per-sentence synthesis + real inter-sentence gap --

@requires_ffmpeg
def test_multi_sentence_narration_concatenates_with_real_gap_and_offsets(tmp_path):
    import subprocess
    fake_edge_tts = types.ModuleType("edge_tts")
    sentence_specs = {
        "첫 문장입니다.": (0.6, "첫", "문장입니다."),
        "둘째 문장입니다.": (0.5, "둘째", "문장입니다."),
    }
    class FakeCommunicate:
        def __init__(self, text, voice, **k):
            self.text = text
        async def stream(self):
            duration, w1, w2 = sentence_specs[self.text]
            clip = tmp_path / f"_gen_{abs(hash(self.text))}.mp3"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(duration), "-q:a", "9", str(clip)], check=True, capture_output=True)
            yield {"type": "audio", "data": clip.read_bytes()}
            half = duration / 2
            yield {"type": "WordBoundary", "text": w1, "offset": 0, "duration": int(half * 10_000_000)}
            yield {"type": "WordBoundary", "text": w2, "offset": int(half * 10_000_000), "duration": int(half * 10_000_000)}
    fake_edge_tts.Communicate = FakeCommunicate
    import sys as _sys
    _sys.modules["edge_tts"] = fake_edge_tts

    words = asyncio.run(edge_tts_with_boundaries(
        "첫 문장입니다. 둘째 문장입니다.", tmp_path / "out.mp3", tmp_path / "out.json",
    ))
    del _sys.modules["edge_tts"]

    # Sentence 1's words start at/near 0; sentence 2's words must start AFTER
    # sentence 1's real audio duration (~0.6s) plus the real inter-sentence gap.
    assert words[0].start == pytest.approx(0.0, abs=1e-6)
    sentence2_start = words[2].start
    assert sentence2_start >= 0.6 + SENTENCE_GAP_SECONDS - 0.05, (
        f"sentence 2 must start after sentence 1's real duration + the gap, got {sentence2_start}"
    )
    # The written audio file must itself be as long as both parts + the gap.
    import re as _re
    probe = subprocess.run(["ffmpeg", "-i", str(tmp_path / "out.mp3")], capture_output=True, text=True)
    m = _re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", probe.stderr)
    total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    assert total >= 0.6 + 0.5 + SENTENCE_GAP_SECONDS - 0.1

@requires_ffmpeg
def test_multi_sentence_fails_closed_if_any_sentence_has_no_boundaries(tmp_path):
    import subprocess
    fake_edge_tts = types.ModuleType("edge_tts")
    class FakeCommunicate:
        def __init__(self, text, voice, **k):
            self.text = text
        async def stream(self):
            if self.text == "둘째 문장입니다.":
                return
                yield {}  # pragma: no cover
            clip = tmp_path / "ok.mp3"
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.5", "-q:a", "9", str(clip)], check=True, capture_output=True)
            yield {"type": "audio", "data": clip.read_bytes()}
            yield {"type": "WordBoundary", "text": self.text, "offset": 0, "duration": 5_000_000}
    fake_edge_tts.Communicate = FakeCommunicate
    import sys as _sys
    _sys.modules["edge_tts"] = fake_edge_tts
    try:
        with pytest.raises(RuntimeError):
            asyncio.run(edge_tts_with_boundaries("첫 문장입니다. 둘째 문장입니다.", tmp_path / "out.mp3", tmp_path / "out.json"))
    finally:
        del _sys.modules["edge_tts"]

def test_default_rate_is_conservative_not_rushed():
    # Not the whole fix (see the sentence-splitting/WordBoundary tests above),
    # but the old +24% rushed delivery should not silently creep back in.
    assert DEFAULT_KO_RATE in {"+0%", "+2%", "+4%", "+5%", "+6%", "+8%", "+10%", "+12%"}
