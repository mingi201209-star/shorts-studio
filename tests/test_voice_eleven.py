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
