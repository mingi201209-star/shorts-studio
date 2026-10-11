import pytest

from shorts_studio.timing import WordTiming
from shorts_studio.tts import _map_boundaries_to_script


def test_unitized_groups_real_subword_events_without_interpolation():
    measured = [
        WordTiming("빗", 0.12, 0.26),
        WordTiming("길에", 0.30, 0.66),
        WordTiming("물이", 0.85, 1.31),
    ]
    assert _map_boundaries_to_script("빗길에 물이", measured) == [
        WordTiming("빗길에", 0.12, 0.66),
        WordTiming("물이", 0.85, 1.31),
    ]


def test_unitized_refuses_mismatched_same_count_events():
    with pytest.raises(ValueError, match="does not match"):
        _map_boundaries_to_script(
            "빗길에 물이",
            [WordTiming("바다에", 0.1, 0.4), WordTiming("물이", 0.5, 0.8)],
        )


def test_unitized_refuses_coarse_phrase_boundary():
    with pytest.raises(ValueError, match="spans multiple"):
        _map_boundaries_to_script(
            "빗길에 물이",
            [WordTiming("빗길에 물이", 0.1, 1.4)],
        )


def test_unitized_refuses_missing_provider_events():
    with pytest.raises(ValueError, match="do not cover every"):
        _map_boundaries_to_script(
            "빗길에 물이", [WordTiming("빗길에", 0.1, 0.4)]
        )


def test_unitized_preserves_punctuation_in_display_tokens():
    assert _map_boundaries_to_script(
        "맞다. 하지만?",
        [WordTiming("맞다", 0.0, 0.28), WordTiming("하지만", 0.52, 0.91)],
    ) == [
        WordTiming("맞다.", 0.0, 0.28),
        WordTiming("하지만?", 0.52, 0.91),
    ]
