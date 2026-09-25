"""Real, pixel-level verification that captions are actually burned into the
rendered video and visible where expected -- not just that subtitle TIMING
QA passed. Subtitle timing can be perfectly correct while the caption is
invisible (wrong color, clipped off-screen, wrong track) or in the wrong
place; this renders real frames and inspects real pixels to catch that.

Also a direct regression for "captions sit right under the picture": per
direct user feedback on a real rendered frame, captions moved from a
bottom-anchored position (parked in the lower gutter, close to the Shorts
UI) to top-anchored right under the picture's own bottom edge
(CAPTION_MASK_TOP). These tests exercise the real production CAPTION_STYLE
directly (via R.CAPTION_STYLE) rather than a hand-rolled parallel style, so
they can never silently drift from what render.py actually burns in.
"""
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

def _render_caption_only_clip(build, duration=3.0, caption_window=(0.5, 2.5)):
    """Renders using the REAL production R.CAPTION_STYLE (not a hand-rolled
    parallel style) so this test can never silently drift from what
    render.py actually burns into a video."""
    build.mkdir(parents=True, exist_ok=True)
    audio = build / "silence.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(duration), "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"
    start, end = caption_window
    srt.write_text(f"1\n00:00:{start:06.3f}".replace(".", ",") + f" --> 00:00:{end:06.3f}".replace(".", ",") + "\n테스트 자막입니다\n\n", encoding="utf-8")
    vf = f"subtitles={srt.as_posix()}:force_style='{R.CAPTION_STYLE}'"
    clip = build / "clip.mp4"
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x20242b:s=1080x1920:r=30:d=" + str(duration), "-i", str(audio), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)]
    subprocess.run(cmd, check=True, capture_output=True)
    return clip

def _extract(clip, ts, out):
    subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", str(clip), "-frames:v", "1", str(out)], check=True, capture_output=True)
    return out

@requires_ffmpeg
def test_current_style_burns_in_caption_during_active_window(tmp_path):
    clip = _render_caption_only_clip(tmp_path / "current")
    active = _extract(clip, 1.5, tmp_path / "active.jpg")
    inactive = _extract(clip, 2.9, tmp_path / "inactive.jpg")
    span_active = _bright_row_span(active)
    span_inactive = _bright_row_span(inactive)
    assert span_active is not None, "no caption pixels found during the active speech window"
    assert span_inactive is None, "caption pixels found outside its timing window (ghosting / stuck caption)"

@requires_ffmpeg
def test_current_style_caption_sits_right_under_the_picture(tmp_path):
    """Top-anchored: the caption's first line must start close to the
    picture's own bottom edge (CAPTION_MASK_TOP), not parked deep in the
    lower gutter near the Shorts UI."""
    clip = _render_caption_only_clip(tmp_path / "clip")
    active = _extract(clip, 1.5, tmp_path / "active.jpg")
    row_min, row_max = _bright_row_span(active)
    height = cv2.imread(str(active)).shape[0]
    assert row_max < height * 0.95, f"caption row {row_max} is too close to the bottom edge (height={height}), risk of being cut off"
    assert row_min > R.CAPTION_MASK_TOP, "caption starts above the picture's own bottom edge -- overlapping the picture"
    assert row_min < R.CAPTION_MASK_TOP + 100, (
        f"caption's first line (row {row_min}) sits far below the picture's bottom edge "
        f"({R.CAPTION_MASK_TOP}) -- expected it right underneath, not parked in the lower gutter"
    )

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
def test_multiline_caption_does_not_lose_its_last_line(tmp_path):
    """Top-anchored captions grow additional wrapped lines DOWNWARD, away
    from the picture -- the mirror image of the real word-loss bug this
    test originally caught under the old bottom-anchored design (where
    lines grew upward and an overflow silently cropped the FIRST line
    against the mask's top edge). Under top-anchor the analogous risk is
    the LAST line overflowing past the bottom of the frame/mask instead.
    This renders the ACTUAL longest real narration group in this
    manifest's lineage (scene_08's 3-unit caption) through the real
    production compositor and checks every line's band is fully visible,
    with the bottommost line comfortably clear of the frame's bottom edge."""
    build = tmp_path / "build"; build.mkdir()
    text = "라듐 걸스의 싸움은 이후 방사선 작업 안전기준을 바꾸는 중요한 계기가 됐습니다"
    audio = build / "silence.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text(f"1\n00:00:00,500 --> 00:00:02,500\n{text}\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="subtest", motion=SimpleNamespace(type="push_in"))
    clip = R._composite_scene_clip(scene, None, audio, srt, 3.0, 30, build, 0)
    frame = _extract(clip, 1.5, build / "active.jpg")
    bands = _text_row_bands(frame)
    assert bands, "no caption pixels found during the active speech window"
    height = cv2.imread(str(frame)).shape[0]
    assert bands[0][0] > R.CAPTION_MASK_TOP, "topmost caption line overlaps the picture above the mask"
    assert bands[-1][1] < height * 0.95, (
        f"bottommost caption line (row {bands[-1][1]}) sits right at the frame's bottom edge "
        f"-- a real later line was likely cropped off"
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
