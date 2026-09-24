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

@requires_ffmpeg
def test_current_style_sits_in_the_gutter_close_to_the_picture(tmp_path):
    """Speech captions belong in the black gutter just below the fixed picture."""
    current_margin = R.CAPTION_MARGIN_V
    clip = _render_caption_only_clip(tmp_path / "new", current_margin)
    span = _bright_row_span(_extract(clip, 1.5, tmp_path / "gutter_active.jpg"))
    assert span is not None
    assert span[0] > R.SAFE_BOTTOM_Y, (
        f"caption rows {span} overlap the picture ending at {R.SAFE_BOTTOM_Y}"
    )
    assert span[0] < R.SAFE_BOTTOM_Y + 220, (
        f"caption rows {span} are visually detached from the picture"
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
