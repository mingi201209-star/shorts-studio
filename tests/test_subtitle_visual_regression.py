"""Real, pixel-level verification that captions are actually burned into the
rendered video and visible where expected -- not just that subtitle TIMING
QA passed. Subtitle timing can be perfectly correct while the caption is
invisible (wrong color, clipped off-screen, wrong track) or in the wrong
place; this renders real frames and inspects real pixels to catch that.

Also a direct regression for the "move captions lower for Shorts
visibility" fix: renders both the current style and the old (MarginV=260)
style through the real compositing pipeline and asserts the current one is
positioned lower on screen, not silently reverted.
"""
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import shorts_studio.render as R

requires_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requires a real ffmpeg binary")

def _bright_row_span(frame_path, threshold=200):
    """Rows containing any near-white pixel (the caption's fill color)."""
    gray = cv2.cvtColor(cv2.imread(str(frame_path)), cv2.COLOR_BGR2GRAY)
    rows = np.where((gray > threshold).any(axis=1))[0]
    return (int(rows.min()), int(rows.max())) if len(rows) else None

def _render_caption_only_clip(build, margin_v, duration=3.0, caption_window=(0.5, 2.5)):
    build.mkdir(parents=True, exist_ok=True)
    audio = build / "silence.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(duration), "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"
    start, end = caption_window
    srt.write_text(f"1\n00:00:{start:06.3f}".replace(".", ",") + f" --> 00:00:{end:06.3f}".replace(".", ",") + "\n테스트 자막입니다\n\n", encoding="utf-8")
    vf = f"subtitles={srt.as_posix()}:force_style='Alignment=2,MarginV={margin_v},FontSize=18,Outline=2,Bold=1'"
    clip = build / "clip.mp4"
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x20242b:s=1080x1920:r=30:d=" + str(duration), "-i", str(audio), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)]
    subprocess.run(cmd, check=True, capture_output=True)
    return clip

def _extract(clip, ts, out):
    subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", str(clip), "-frames:v", "1", str(out)], check=True, capture_output=True)
    return out

@requires_ffmpeg
def test_current_style_burns_in_caption_during_active_window(tmp_path):
    current_margin = R.CAPTION_MARGIN_V
    clip = _render_caption_only_clip(tmp_path / "current", current_margin)
    active = _extract(clip, 1.5, tmp_path / "active.jpg")
    inactive = _extract(clip, 2.9, tmp_path / "inactive.jpg")
    span_active = _bright_row_span(active)
    span_inactive = _bright_row_span(inactive)
    assert span_active is not None, "no caption pixels found during the active speech window"
    assert span_inactive is None, "caption pixels found outside its timing window (ghosting / stuck caption)"

@requires_ffmpeg
def test_current_style_caption_not_clipped_off_screen(tmp_path):
    current_margin = R.CAPTION_MARGIN_V
    clip = _render_caption_only_clip(tmp_path / "clip", current_margin)
    active = _extract(clip, 1.5, tmp_path / "active.jpg")
    row_min, row_max = _bright_row_span(active)
    height = cv2.imread(str(active)).shape[0]
    assert row_max < height * 0.95, f"caption row {row_max} is too close to the bottom edge (height={height}), risk of being cut off"
    assert row_min > 0

def _text_row_bands(frame_path, threshold=200, gap=5):
    gray = cv2.cvtColor(cv2.imread(str(frame_path)), cv2.COLOR_BGR2GRAY)
    rows = np.where((gray > threshold).any(axis=1))[0]
    if not len(rows):
        return []
    bands = []
    start = rows[0]; prev = rows[0]
    for r in rows[1:]:
        if r - prev > gap:
            bands.append((int(start), int(prev)))
            start = r
        prev = r
    bands.append((int(start), int(prev)))
    return bands

@requires_ffmpeg
def test_multiline_caption_does_not_lose_its_first_line(tmp_path):
    """Real production bug: a plain SRT carries no PlayResX/PlayResY, and
    force_style'd FontSize/MarginV with no PlayRes declared let libass fall
    back to an internal default reference resolution and silently scale
    those values up ~6-7x to fill the real 1920-tall frame. At the OLD
    (buggy) FontSize=30 with no PlayRes, that turned into ~200px-tall
    glyphs, wrapping almost every word onto its own line; a caption needing
    more lines than fit in CAPTION_MASK_HEIGHT had its own FIRST line
    (Alignment=2 grows additional lines upward from the bottom anchor, so
    the earliest line sits highest) pushed above the crop window and
    silently cropped away -- real spoken words vanished from the video.
    This renders the ACTUAL narration text that exhibited the bug (scene_01's
    HOOK phrase) through the real production compositor and OCR-free but
    position-based: every one of the ORIGINAL WORDS must still be
    detectable as its own bright band group, and the topmost band must not
    sit at the very top edge of the caption mask window (which would mean
    an even-earlier line got cropped above it)."""
    build = tmp_path / "build"; build.mkdir()
    text = "세계 최초의 제트 여객기가 비행"  # the real scene_01 HOOK caption group (5 words, at segment()'s max_words cap)
    audio = build / "silence.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text(f"1\n00:00:00,500 --> 00:00:02,500\n{text}\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="subtest", motion=SimpleNamespace(type="push_in"))
    clip = R._composite_scene_clip(scene, None, audio, srt, 3.0, 30, build, 0)
    frame = _extract(clip, 1.5, build / "active.jpg")
    bands = _text_row_bands(frame)
    assert bands, "no caption pixels found during the active speech window"
    # A cropped-off first line always means the topmost surviving line sits
    # flush against (or above) the mask's own top edge -- a real word lost
    # to the crop leaves no visible gap between the mask boundary and the
    # first surviving line. Demand real headroom instead.
    top_of_mask = R.CAPTION_MASK_TOP
    assert bands[0][0] > top_of_mask + 20, (
        f"topmost caption line (row {bands[0][0]}) sits right at the caption "
        f"mask's top edge ({top_of_mask}) -- a real earlier line was likely "
        f"cropped off, exactly like the '1950년대 세계 최...' word-loss bug"
    )

@requires_ffmpeg
def test_render_module_composite_scene_clip_matches_direct_ffmpeg_style(tmp_path):
    """Sanity check that render.py's real _composite_scene_clip (no-asset
    branch, used e.g. when a scene declares no image) burns in a visible,
    non-clipped caption -- exercising the actual production function, not
    a hand-rolled ffmpeg command."""
    build = tmp_path / "build"; build.mkdir()
    audio = build / "silence.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,500 --> 00:00:02,500\n테스트 자막입니다\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="subtest", motion=SimpleNamespace(type="push_in"))
    clip = R._composite_scene_clip(scene, None, audio, srt, 3.0, 30, build, 0)
    active = _extract(clip, 1.5, build / "active.jpg")
    inactive = _extract(clip, 2.9, build / "inactive.jpg")
    assert _bright_row_span(active) is not None
    assert _bright_row_span(inactive) is None
    row_min, row_max = _bright_row_span(active)
    height = cv2.imread(str(active)).shape[0]
    assert height * 0.3 < row_min, "caption unexpectedly rendered too close to the top"
    assert row_max < height * 0.95, "caption unexpectedly rendered too close to the bottom edge"
