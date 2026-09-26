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
        assert 0 < (c.end - c.start) <= 3.2 + 1e-6

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

def test_small_cross_unit_pause_never_drops_word_coverage():
    """Real regression found via a full production render: the Korean
    Prosody Planner deliberately uses SMALL pauses between some phrase
    units (e.g. a 0.10s HOOK->SETUP transition) -- well under segment()'s
    max_gap(0.6) merge threshold. That lets words from both sides of the
    pause land in the SAME caption group. If that merged group's natural
    span (which includes the pause itself) exceeds max_duration(2.2), the
    old clamp (`end=min(end,start+max_duration)`) could cut the caption's
    end BELOW its own last word's real end -- silently dropping caption
    coverage for a word that was genuinely spoken. This is not a
    synthetic corner case: it fired on real scene_01 (HOOK->SETUP) output
    in CI. The fix must hold regardless of the exact pause value chosen by
    the planner, so this is parametrized across several sub-max_gap pauses."""
    for pause in (0.0, 0.10, 0.16, 0.22, 0.30, 0.45):
        words = [
            WordTiming("hook1", 0.00, 0.42),
            WordTiming("hook2", 0.47, 0.89),
            WordTiming("hook3", 0.94, 1.36),
            WordTiming("hook4", 1.41, 1.83),
        ]
        gap_start = words[-1].end + pause
        words += [
            WordTiming("setup1", gap_start, gap_start + 0.42),
            WordTiming("setup2", gap_start + 0.47, gap_start + 0.89),
        ]
        duration = words[-1].end + .25
        caps = segment(words, duration)
        violations = speech_gap_violations(caps, words)
        assert violations == [], f"pause={pause}: dropped coverage for {violations}"
        # The coverage guarantee must hold via each caption's own last word,
        # not by accident: every caption must reach at least its own last
        # covered word's real end.
        for c in caps:
            covered = [w for w in words if w.start < c.end and w.end > c.start]
            if covered:
                assert c.end >= max(w.end for w in covered) - 1e-9

def test_max_duration_clamp_still_trims_pure_bridge_overlap():
    """The coverage-safety fix must not disable max_duration entirely --
    it should still cap a caption that runs long purely because of the
    small flicker-avoidance bridge into the next caption's start, as long
    as doing so does not cut below this group's own last real word."""
    words = [WordTiming("only", 0.0, 0.3)]
    caps = segment(words, audio_duration=10.0, max_duration=2.2)
    assert caps[0].end - caps[0].start <= 2.2 + 1e-9
