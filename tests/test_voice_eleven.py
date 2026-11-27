"""The ElevenLabs capture's word timings: one per whitespace token, taken from the measured character alignment."""
import pytest

from benchmarks.voice.eleven import words_from_alignment


def _alignment(text, step=0.05):
    return {"characters": list(text), "character_start_times_seconds": [i * step for i in range(len(text))],
            "character_end_times_seconds": [(i + 1) * step for i in range(len(text))]}


def test_one_timing_per_token_without_punctuation():
    text = "Subscribe for part two: what stops a giant ship."
    w = words_from_alignment(text, _alignment(text))
    assert [x["text"] for x in w] == ["Subscribe", "for", "part", "two", "what", "stops", "a", "giant", "ship"]
    assert len(w) == len(text.split())
    two = w[3]
    assert two["start"] == pytest.approx(text.index("two") * 0.05) and two["end"] == pytest.approx((text.index("two") + 3) * 0.05)
    assert all(b["start"] >= a["end"] - 1e-9 for a, b in zip(w, w[1:]))


def test_contractions_and_hyphens_stay_one_word():
    text = "They're built to stop a ninety-thousand-pound truck."
    w = words_from_alignment(text, _alignment(text))
    assert [x["text"] for x in w][0] == "They're" and "ninety-thousand-pound" in [x["text"] for x in w]


def test_alignment_must_spell_the_text():
    with pytest.raises(ValueError):
        words_from_alignment("Hello there.", _alignment("Hello there!"))


def test_first_word_starts_where_the_sound_does():
    import numpy as np
    from benchmarks.voice.eleven import onset_of, retime_first_word
    sr = 48000
    x = np.zeros(sr * 2)
    x[int(0.7 * sr):int(1.4 * sr)] = 0.3 * np.sin(np.arange(int(0.7 * sr)) * 0.05)
    on = onset_of(x, sr)
    assert 0.68 <= on <= 0.71
    w = retime_first_word([{"text": "How", "start": 0.0, "end": 0.95}, {"text": "do", "start": 1.0, "end": 1.1}], on)
    assert 0.64 <= w[0]["start"] <= 0.7 and w[1]["start"] == 1.0                  # only the first word moves
    assert retime_first_word([{"text": "a", "start": 0.2, "end": 0.3}], 0.05)[0]["start"] == 0.2   # never earlier
