"""Real published-video bug: a numeral-determiner ('네') and its counter
word ('개') got split across two separate caption cards. Word-level TTS
boundary timing has no concept of this pairing, so segment() must protect
it explicitly, regardless of which break rule (gap/duration/word-count)
would otherwise land between them."""
from shorts_studio.timing import WordTiming
from shorts_studio.subtitles import segment, speech_gap_violations


def test_numeral_counter_pair_is_never_split_by_a_gap_right_after_the_numeral():
    """Reproduces the exact real failure: a real inter-unit pause landed
    right between '네' and '개', which without protection exceeds max_gap
    and forces a new caption group boundary there."""
    words = [
        WordTiming("타이타닉에는", 0.0, 0.6),
        WordTiming("거대한", 0.65, 1.0),
        WordTiming("굴뚝이", 1.05, 1.4),
        WordTiming("네", 1.45, 1.6),
        # A gap here (> the default max_gap=0.6) would normally force a break.
        WordTiming("개", 2.4, 2.6),
        WordTiming("있었습니다.", 2.65, 3.2),
    ]
    caps = segment(words, audio_duration=3.4, max_gap=0.6)
    joined_texts = [c.text for c in caps]
    assert not any(c.text.strip() == "네" for c in caps), joined_texts
    # "네" and "개" must land in the SAME caption card.
    ne_caption = next(c for c in caps if "네" in c.text.split())
    gae_caption = next(c for c in caps if c.text.split() and c.text.split()[-2:][0] == "개" or "개" in c.text.split())
    assert ne_caption is gae_caption, joined_texts


def test_numeral_counter_pair_is_never_split_by_max_words():
    words = [WordTiming(f"단어{i}", i * 0.3, i * 0.3 + 0.25) for i in range(7)]
    words += [WordTiming("두", 2.2, 2.35), WordTiming("명이", 2.4, 2.6)]
    caps = segment(words, audio_duration=3.0, max_words=8)
    assert not any(c.text.strip() == "두" for c in caps)


def test_numeral_counter_protection_does_not_break_speech_gap_coverage():
    words = [
        WordTiming("타이타닉에는", 0.0, 0.6),
        WordTiming("거대한", 0.65, 1.0),
        WordTiming("굴뚝이", 1.05, 1.4),
        WordTiming("네", 1.45, 1.6),
        WordTiming("개", 2.4, 2.6),
        WordTiming("있었습니다.", 2.65, 3.2),
    ]
    caps = segment(words, audio_duration=3.4)
    assert speech_gap_violations(caps, words) == []


def test_non_counter_words_are_unaffected_and_can_still_split_normally():
    """'네' meaning 'yes'/'your' followed by an unrelated word (not a real
    counter) must not be force-merged -- only real numeral+counter pairs are
    protected."""
    words = [
        WordTiming("네,", 0.0, 0.3),
        WordTiming("알겠습니다.", 1.5, 2.0),  # big gap, ordinary break expected
    ]
    caps = segment(words, audio_duration=2.2, max_gap=0.6)
    assert len(caps) == 2
