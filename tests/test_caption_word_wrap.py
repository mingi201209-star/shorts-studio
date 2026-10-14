"""Burned-in captions must break lines only between words and must never share
the screen with a neighbouring cue.

Both failures were seen in a real hydroplaning render: libass wrapped
"문제는 고무가 아니라 타이어 아래로" as "문제는 고무가 아" / "니라 타이어 아래로",
and cues that overlapped by 60-120 ms pushed the later cue down a row.
"""
import shutil
import subprocess

import pytest

from shorts_studio.render import (
    CAPTION_MAX_LINE_UNITS,
    CAPTION_STYLE,
    _caption_units,
    _wrap_caption_safe,
    _write_burn_in_srt,
)
from shorts_studio.subtitles import segment, speech_gap_violations
from shorts_studio.timing import WordTiming

REAL_CAPTIONS = [
    "빗길에선 타이어가 돌고 있어도 실은",
    "문제는 고무가 아니라 타이어 아래로",
    "그런데 속도가 빨라지면 홈이 빼내는",
    "도로에 닿아 있던 면이 점점 줄어들다가",
    "이게 바로 하이드로플레이닝입니다.",
    "타이어 앞쪽으로 물이 쐐기처럼 파고들고 도로에 닿아 있던 면이 점점",
    "1986년 4월 26일 새벽 1시 23분, 체르노빌 4호기가 폭발했습니다.",
]


@pytest.mark.parametrize("text", REAL_CAPTIONS)
def test_wrap_breaks_only_between_words(text):
    wrapped = _wrap_caption_safe(text)
    lines = wrapped.split("\n")
    assert " ".join(lines).split() == text.split()
    assert all(line == line.strip() and line for line in lines)
    assert all(_caption_units(line) <= CAPTION_MAX_LINE_UNITS for line in lines)


def test_reported_mid_word_breaks_are_gone():
    assert _wrap_caption_safe("문제는 고무가 아니라 타이어 아래로") == "문제는 고무가 아니라\n타이어 아래로"
    assert "빨\n라지면" not in _wrap_caption_safe("그런데 속도가 빨라지면 홈이 빼내는")


def test_short_caption_stays_on_one_line():
    assert _wrap_caption_safe("들어오는 물입니다.") == "들어오는 물입니다."


def test_single_overlong_word_is_never_cut():
    word = "하" * 30
    assert _wrap_caption_safe(word) == word
    assert word in _wrap_caption_safe(f"이게 {word} 입니다").split("\n")


def test_wrapped_lines_are_balanced_not_orphaned():
    lines = _wrap_caption_safe("도로에 닿아 있던 면이 점점 줄어들다가").split("\n")
    assert len(lines) == 2
    assert min(_caption_units(line) for line in lines) >= 0.5 * max(_caption_units(line) for line in lines)


def test_caption_style_forbids_libass_rewrapping():
    assert "WrapStyle=2" in CAPTION_STYLE


def test_burn_in_srt_keeps_timing_and_leaves_source_unwrapped(tmp_path):
    srt = tmp_path / "s_hook.srt"
    source = (
        "1\n00:00:00,000 --> 00:00:02,000\n문제는 고무가 아니라 타이어 아래로\n\n"
        "2\n00:00:02,000 --> 00:00:03,000\n들어오는 물입니다.\n"
    )
    srt.write_text(source, encoding="utf-8")
    burn = _write_burn_in_srt(srt)
    assert burn != srt and srt.read_text(encoding="utf-8") == source
    blocks = burn.read_text(encoding="utf-8").strip().split("\n\n")
    assert blocks[0].splitlines() == ["1", "00:00:00,000 --> 00:00:02,000", "문제는 고무가 아니라", "타이어 아래로"]
    assert blocks[1].splitlines() == ["2", "00:00:02,000 --> 00:00:03,000", "들어오는 물입니다."]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
@pytest.mark.parametrize("text", REAL_CAPTIONS)
def test_real_libass_render_keeps_every_line_inside_the_frame(tmp_path, text):
    """WrapStyle=2 means an over-long line would run off the frame instead of
    wrapping, so the width estimate is checked against a real render: no ink in
    the outer 24px columns, and one ink band per wrapped line."""
    cv2 = pytest.importorskip("cv2")
    srt = tmp_path / "c.srt"
    wrapped = _wrap_caption_safe(text)
    srt.write_text(f"1\n00:00:00,000 --> 00:00:02,000\n{wrapped}\n", encoding="utf-8")
    png = tmp_path / "c.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=1080x1920:d=1",
         "-vf", f"subtitles={srt.as_posix()}:force_style='{CAPTION_STYLE}'", "-frames:v", "1", str(png)],
        check=True, timeout=120,
    )
    ink = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE) > 40
    assert ink.any(), "caption did not render"
    assert not ink[:, :24].any() and not ink[:, -24:].any(), "caption ink reaches the frame edge"
    rows = ink.any(axis=1)
    bands = sum(1 for i in range(len(rows)) if rows[i] and (i == 0 or not rows[i - 1]))
    # A glyph row can split into more than one band (e.g. a detached final
    # consonant), never into fewer bands than there are lines.
    assert bands >= len(wrapped.split("\n"))


def _words(spec):
    return [WordTiming(text, start, end) for text, start, end in spec]


def test_cues_never_overlap_and_still_cover_every_word():
    # Real word timings from the hydroplaning hook: the second group's first
    # word starts 60 ms after the first group's last word ends, so a 120 ms
    # lead-in used to start cue 2 before cue 1 had ended.
    words = _words([
        ("빗길에선", 0.12, 0.70), ("타이어가", 0.72, 1.20), ("돌고", 1.22, 1.50), ("있어도", 1.52, 1.95),
        ("실은", 1.97, 2.284), ("도로에", 2.344, 2.80), ("닿지", 2.82, 3.20), ("않을", 3.22, 3.50),
        ("수", 3.52, 3.60), ("있습니다.", 3.62, 4.306), ("문제는", 4.947, 5.40), ("고무가", 5.42, 5.90),
    ])
    captions = segment(words, 6.0)
    assert len(captions) >= 3
    for previous, current in zip(captions, captions[1:]):
        assert current.start >= previous.end
    assert not speech_gap_violations(captions, words)
    assert all(c.end > c.start for c in captions)


def test_overlapping_words_hand_the_boundary_to_the_later_cue():
    words = _words([("하나.", 0.0, 1.00), ("둘", 0.95, 1.60)])
    captions = segment(words, 2.0)
    assert [c.text for c in captions] == ["하나.", "둘"]
    assert captions[0].end == captions[1].start == pytest.approx(0.95)
    assert not speech_gap_violations(captions, words)


def test_missing_scene_srt_is_passed_through(tmp_path):
    missing = tmp_path / "absent.srt"
    assert _write_burn_in_srt(missing) == missing
    assert not (tmp_path / "absent.burn.srt").exists()
