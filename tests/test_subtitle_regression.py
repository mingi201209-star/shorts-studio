"""Korean caption/subtitle regressions: zero gap during active speech, no
negative/reversed/out-of-bounds timestamps, short Shorts-style caption spans,
and captions never perceptibly lagging the voice (lead policy)."""
import pytest
from shorts_studio.timing import WordTiming
from shorts_studio.subtitles import Caption, excessive_tail_violations, segment, speech_gap_violations
from shorts_studio.qa import subtitle_qa

def _korean_words(n, step=0.35, span=0.28):
    return [WordTiming(f"단어{i}", i*step, i*step+span) for i in range(n)]

def test_zero_speech_gap_across_many_segment_boundaries():
    words = _korean_words(23)
    duration = words[-1].end + .25
    caps = segment(words, duration)
    assert len(caps) >= 3
    assert speech_gap_violations(caps, words) == []

def test_caption_spans_stay_in_shorts_range():
    words = _korean_words(30)
    duration = words[-1].end + .25
    caps = segment(words, duration)
    for c in caps:
        assert 0 < (c.end - c.start) <= 2.2 + 1e-6

def test_no_negative_no_reversed_no_overrun_timestamps():
    words = _korean_words(15)
    duration = words[-1].end + .25
    caps = segment(words, duration)
    q = subtitle_qa(caps, words, duration)
    assert q["status"] == "PASS"
    assert q["invalid"] == 0
    for c in caps:
        assert c.start >= 0
        assert c.end >= c.start
        assert c.end <= duration + 1e-3

def test_caption_leads_speech_never_lags():
    w = [WordTiming("안녕하세요", 1.0, 1.6)]
    caps = segment(w, 2.0, lead=.12)
    assert caps[0].start == pytest.approx(0.88)   # starts before the voice, never after
    assert caps[0].start < w[0].start

def test_isolated_pause_between_sentences_is_not_a_violation():
    # A real silence between sentences: captions need not cover silence, only speech.
    early = [WordTiming("첫문장", 0.2, 0.6)]
    late = [WordTiming("다음문장", 3.0, 3.4)]
    words = early + late
    caps = segment(words, 4.0)
    assert speech_gap_violations(caps, words) == []

def test_subtitle_qa_fails_closed_on_injected_gap():
    words = [WordTiming("첫", 0.0, 0.4), WordTiming("둘", 0.5, 0.9), WordTiming("셋", 1.0, 1.4)]
    duration = 1.6
    # A caption pipeline regression: the middle word's speech window is left uncovered.
    broken = [Caption("첫", 0.0, 0.4), Caption("셋", 1.0, 1.4)]
    q = subtitle_qa(broken, words, duration)
    assert q["status"] == "FAIL"
    assert q["speech_gaps"] > 0

def test_caption_disappears_promptly_no_excessive_tail():
    # This is what would have caught "captions remain visible noticeably
    # after the phrase ended": the old SentenceBoundary-only interpolation
    # could position a caption's end far past the real end of its last word.
    words = [WordTiming("안녕", 0.0, 0.4), WordTiming("하세요", 0.42, 0.9)]
    good = [Caption("안녕 하세요", 0.0, 0.95)]  # ends just after real speech
    assert excessive_tail_violations(good, words) == []

def test_excessive_tail_is_flagged():
    words = [WordTiming("안녕", 0.0, 0.4), WordTiming("하세요", 0.42, 0.9)]
    # Caption lingers 1.5s past the real end of the words it covers.
    lingering = [Caption("안녕 하세요", 0.0, 2.4)]
    violations = excessive_tail_violations(lingering, words)
    assert len(violations) == 1

def test_subtitle_qa_fails_closed_on_excessive_tail():
    words = [WordTiming("첫", 0.0, 0.4), WordTiming("둘", 0.5, 0.9)]
    lingering = [Caption("첫 둘", 0.0, 2.5)]
    q = subtitle_qa(lingering, words, 3.0)
    assert q["status"] == "FAIL"
    assert q["excessive_tail"] > 0

def test_real_segment_output_never_produces_excessive_tail_across_many_words():
    words = _korean_words(23)
    duration = words[-1].end + .25
    caps = segment(words, duration)
    assert excessive_tail_violations(caps, words) == []
