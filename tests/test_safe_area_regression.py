"""Real, pixel-level regression for the bottom subtitle safe-area fix: a
full-bleed source image (content touching its own bottom edge, the worst
case -- no natural letterboxing to save it) must never have its SHARP
foreground copy extend into the caption zone. This is a generic composition
invariant enforced for every scene via the fg band's height cap
(SAFE_TOP_Y/SAFE_BOTTOM_Y in render.py), not a per-scene crop hack, so this
test renders an arbitrary synthetic asset through the real production
compositing function -- not scene_07 specifically.

A pure color-presence check would be fooled by the always-present blurred
full-frame backdrop (which legitimately paints the marker color, blurred,
across the whole canvas by design). What actually distinguishes "the crisp
foreground bled through" from "only the black surround is visible" is the
row at which the marker's color first appears with a HARD (few-pixel-wide)
transition -- the crisp fg layer draws inside the fixed centered picture box, so it
produces an abrupt edge; a bug that removes the safe-area cap makes that
abrupt edge appear far lower on screen than the safe boundary allows.
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import shorts_studio.render as R

requires_ffmpeg = __import__("shutil").which("ffmpeg") is not None
pytestmark = pytest.mark.skipif(not requires_ffmpeg, reason="requires a real ffmpeg binary")


def _make_full_bleed_marker_asset(path: Path, marker_frac_from_bottom: float = 0.05) -> Path:
    """A source photo where a distinct marker color touches the image's own
    bottom edge -- simulating a subject/detail with no letterboxing margin,
    the case where naive 'contain over blurred background' compositing still
    lets content reach the very bottom of the frame."""
    w, h = 1200, 2000
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    img[int(h * (1 - marker_frac_from_bottom)):, :] = [255, 0, 255]  # magenta marker strip
    Image.fromarray(img).save(path)
    return path


def _topmost_marker_row(frame_path: Path, col: int = 540) -> int:
    import cv2
    img = cv2.imread(str(frame_path))
    b, g, r = img[:, col, 0].astype(int), img[:, col, 1].astype(int), img[:, col, 2].astype(int)
    score = r + b - 2 * g  # high for magenta, low for white/black/gray
    half = score.max() / 2
    rows_above = np.where(score > half)[0]
    assert len(rows_above), "marker color not found at all in the rendered frame"
    return int(rows_above.min())


def _render_scene_clip(tmp_path: Path, asset: Path) -> Path:
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,500 --> 00:00:02,000\n자막\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="safearea", motion=SimpleNamespace(type="push_in"))
    return R._composite_scene_clip(scene, asset, audio, srt, 3.0, 30, build, 0)


def test_full_bleed_foreground_never_crosses_the_safe_boundary(tmp_path):
    asset = _make_full_bleed_marker_asset(tmp_path / "asset.png")
    clip = _render_scene_clip(tmp_path, asset)
    frame = tmp_path / "frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.2", "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
    top_row = _topmost_marker_row(frame)
    assert top_row <= R.SAFE_BOTTOM_Y, (
        f"foreground marker's sharp edge at row {top_row} crosses into the bottom "
        f"caption safe area (must stay <= SAFE_BOTTOM_Y={R.SAFE_BOTTOM_Y})"
    )


def test_pre_fix_composition_would_have_failed_this_regression(tmp_path):
    """Sanity check on the test itself: reproduce the OLD (buggy) full-height
    fg composition directly and confirm this detector actually catches it --
    otherwise the test above could be vacuously true."""
    asset = _make_full_bleed_marker_asset(tmp_path / "asset.png")
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,500 --> 00:00:02,000\n자막\n\n", encoding="utf-8")
    old_vf = (
        "split=2[bgsrc][fgsrc];[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:8[bg];"
        "[fgsrc]scale=1000:1720:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
        "zoompan=z='min(zoom+0.0007,1.12)':d=1:s=1080x1920:fps=30,"
        f"subtitles={srt.as_posix()}:force_style='Alignment=2,MarginV=48,FontSize=18,Outline=2,Shadow=0,Bold=1'"
    )
    old_clip = build / "old.mp4"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(asset), "-i", str(audio), "-t", "3",
                     "-vf", old_vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(old_clip)],
                    check=True, capture_output=True)
    frame = tmp_path / "old_frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.2", "-i", str(old_clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
    top_row = _topmost_marker_row(frame)
    assert top_row > R.SAFE_BOTTOM_Y, "expected the old unbounded composition to violate the safe area"


@requires_ffmpeg
def test_picture_is_centered_static_black_surrounded_and_caption_cannot_overlap(tmp_path):
    import cv2
    import numpy as np
    asset = tmp_path / "solid.png"
    Image.fromarray(np.full((1000, 1000, 3), [255, 0, 255], dtype=np.uint8)).save(asset)
    clip = _render_scene_clip(tmp_path, asset)
    frames=[]
    for index,ts in enumerate((0.2,1.0)):
        frame=tmp_path/f"layout_{index}.png"
        subprocess.run(["ffmpeg","-y","-ss",str(ts),"-i",str(clip),"-frames:v","1",str(frame)],check=True,capture_output=True)
        frames.append(cv2.imread(str(frame)))
    assert all(frame is not None for frame in frames)
    # Solid marker pixels must be centered within the fixed image box.
    b,g,r=[channel.astype(int) for channel in cv2.split(frames[0])]
    mask=(r>180)&(b>180)&(g<60)
    ys,xs=np.where(mask)
    assert len(xs)>10000
    assert abs(float(xs.mean())-540)<10
    assert R.IMAGE_TOP_Y <= int(ys.min()) and int(ys.max()) < R.SAFE_BOTTOM_Y
    # The still does not move while the same visual beat is on screen.
    box=(slice(R.IMAGE_TOP_Y,R.SAFE_BOTTOM_Y),slice(0,1080))
    assert np.abs(frames[0][box].astype(int)-frames[1][box].astype(int)).mean()<2.0
    # Subtitle glyphs (white) are absent from the picture box.
    fb,fg,fr=[channel.astype(int) for channel in cv2.split(frames[1])]
    white=(fb>230)&(fg>230)&(fr>230)
    assert not white[R.IMAGE_TOP_Y:R.SAFE_BOTTOM_Y,:].any()
    # Surround and the dedicated gutter remain black.
    assert np.max(cv2.cvtColor(frames[1][R.IMAGE_TOP_Y:R.SAFE_BOTTOM_Y,:50],cv2.COLOR_BGR2GRAY))<12
    assert np.max(cv2.cvtColor(frames[1][R.SAFE_BOTTOM_Y+8:1308,:],cv2.COLOR_BGR2GRAY))<12
