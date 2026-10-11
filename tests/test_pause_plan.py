import numpy as np
import pytest

from shorts_studio import pause_plan as pp

librosa = pytest.importorskip("librosa")

SR = 16000
MARKED = ("빗길에선 [tight] 타이어가 돌고 있어도 [link] 도로에 안 닿을 수 있습니다. [turn] "
          "원인은 고무가 아닙니다. [contrast] 타이어 밑으로 파고드는 물입니다.")


def _tone(seconds, f=150.0):
    t = np.arange(int(seconds * SR)) / SR
    return (0.3 * np.sin(2 * np.pi * f * t)).astype(np.float32)


def _speech_with_gaps(gaps):
    parts = [_tone(0.5)]
    for g in gaps:
        parts += [np.zeros(int(g * SR), np.float32), _tone(0.5, 150 + 20 * len(parts))]
    return np.concatenate(parts)


def test_markup_keeps_natural_text_and_records_semantic_boundaries():
    plan = pp.parse_pause_markup(MARKED)
    assert "[" not in plan.text and "," not in plan.text
    assert plan.text.startswith("빗길에선 타이어가")
    assert plan.boundaries == {0: "tight", 3: "link", 8: "turn", 11: "contrast"}
    assert pp.chunk_texts(plan) == ["빗길에선", "타이어가 돌고 있어도", "도로에 안 닿을 수 있습니다.",
                                    "원인은 고무가 아닙니다.", "타이어 밑으로 파고드는 물입니다."]


@pytest.mark.parametrize("bad", ["[turn] 원인은", "원인은 [turn]", "원인은 [turn] [link] 고무가"])
def test_markup_rejects_misplaced_markers(bad):
    with pytest.raises(ValueError):
        pp.parse_pause_markup(bad)


def test_detects_the_real_gaps():
    y = _speech_with_gaps([0.5, 0.12])
    gaps = pp.detect_silences(y, SR)
    assert len(gaps) == 2
    assert abs((gaps[0][1] - gaps[0][0]) - 0.5) < 0.03
    assert abs((gaps[1][1] - gaps[1][0]) - 0.12) < 0.03


def test_retime_only_edits_silence_and_hits_targets():
    y = _speech_with_gaps([0.55, 0.30])
    gaps = pp.detect_silences(y, SR)
    edits = [(a, b, t) for (a, b), t in zip(gaps, [0.11, 0.34])]
    out, tmap = pp.retime_silences(y, SR, edits)
    new = pp.detect_silences(out, SR)
    assert abs((new[0][1] - new[0][0]) - 0.11) < 0.02     # shortened
    assert abs((new[1][1] - new[1][0]) - 0.34) < 0.02     # lengthened
    # Speech is copied verbatim: every tone sample survives, nothing stretched.
    voiced_in = np.abs(y) > 1e-3
    voiced_out = np.abs(out) > 1e-3
    assert abs(int(voiced_in.sum()) - int(voiced_out.sum())) < 0.02 * SR
    first = _tone(0.5)
    assert np.array_equal(out[: int(0.45 * SR)], first[: int(0.45 * SR)])
    # length changes by exactly the silence added/removed, nothing else
    assert abs((len(out) - len(y)) / SR - sum(t - (b - a) for a, b, t in edits)) < 2 / SR
    # word times after the first gap move by the removed silence
    assert pp.shift_time(0.2, tmap) == pytest.approx(0.2)
    removed = (gaps[0][1] - gaps[0][0]) - 0.11
    assert pp.shift_time(1.2, tmap) == pytest.approx(1.2 - removed, abs=1e-3)


def test_unmarked_joins_are_capped_and_marked_turn_gets_its_pause():
    plan = pp.parse_pause_markup("가 나 [turn] 다 라")
    silences = [(0.50, 0.95), (1.40, 1.90)]
    token_end = {1: 0.50, 2: 1.40}
    targets = pp.plan_gap_targets(plan, silences, token_end)
    assert targets[0][2] == pp.PAUSE_TARGETS["turn"]
    assert targets[1][2] == pp.UNMARKED_MAX


def test_word_mapping_survives_a_misrecognised_syllable():
    tokens = ["원인은", "고무가", "아닙니다.", "물입니다."]
    words = [("원인은", 0.0, 0.4), ("공우가", 0.4, 0.8), ("아닙니다", 0.8, 1.3), ("물입니다", 1.6, 2.1)]
    ends = pp.map_words_to_tokens(tokens, words)
    assert ends[0] == 0.4 and ends[2] == 1.3 and ends[3] == 2.1


def test_join_chunks_trims_tts_tail_silence_and_inserts_designed_pause():
    tail = np.zeros(int(0.3 * SR), np.float32)  # GPT-SoVITS pause_second
    a = np.concatenate([_tone(0.6), tail])
    b = np.concatenate([np.zeros(int(0.05 * SR), np.float32), _tone(0.6, 200), tail])
    out = pp.join_chunks([a, b], SR, [0.12])
    gaps = pp.detect_silences(out, SR)
    assert len(gaps) == 1 and abs((gaps[0][1] - gaps[0][0]) - 0.12) < 0.03
    with pytest.raises(ValueError):
        pp.join_chunks([a, b], SR, [])


def test_marked_boundary_claims_nearest_pause_despite_recogniser_drift():
    # recogniser says the token ends 0.25 s before the pause actually starts
    plan = pp.parse_pause_markup("가 나 [turn] 다 라")
    silences = [(0.30, 0.36), (1.20, 1.84)]
    targets = pp.plan_gap_targets(plan, silences, {1: 0.95})
    assert [t for *_, t in targets] == [0.06, pp.PAUSE_TARGETS["turn"]]


def test_missing_semantic_pause_fails_closed():
    plan = pp.parse_pause_markup("가 나 [turn] 다 라")
    with pytest.raises(ValueError, match="turn"):
        pp.plan_gap_targets(plan, [(3.0, 3.5)], {1: 0.9})
    with pytest.raises(ValueError, match="no timing"):
        pp.plan_gap_targets(plan, [(1.0, 1.5)], {})


def test_link_without_a_pause_stays_connected():
    plan = pp.parse_pause_markup("가 나 [link] 다 라 [turn] 마")
    silences = [(2.0, 2.6)]
    targets = pp.plan_gap_targets(plan, silences, {1: 0.9, 3: 2.0})
    assert targets == [(2.0, 2.6, pp.PAUSE_TARGETS["turn"])]  # nothing spliced at the link


def test_link_never_lengthens_a_stop_closure_and_turn_takes_the_long_pause():
    plan = pp.parse_pause_markup("가 나 [link] 다 라 [turn] 마")
    # 45 ms closure right at the link; a real 0.5 s pause plus a closure near the turn
    silences = [(0.90, 0.945), (2.00, 2.05), (2.15, 2.65)]
    targets = pp.plan_gap_targets(plan, silences, {1: 0.9, 3: 2.0})
    assert targets[0][2] == pytest.approx(0.045)          # not stretched to 0.11
    assert targets[1][2] == pytest.approx(0.05)           # closure near the turn untouched
    assert targets[2][2] == pp.PAUSE_TARGETS["turn"]      # the long pause is the turn
