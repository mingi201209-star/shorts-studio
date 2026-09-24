"""Real, pixel-level regression confirming a two-line caption stacks in
natural reading order: the FIRST line of authored text renders as the
physically TOP row band, the second line renders BELOW it -- never
reversed. Captions stay at their existing fixed bottom position (no
animation); this only verifies the stacking order within that fixed spot.
"""
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

requires_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="requires a real ffmpeg binary")

_STYLE = "Alignment=2,MarginV=48,FontSize=18,Outline=2,Shadow=0,Bold=1"


def _render_two_line_caption(build: Path, first_line: str, second_line: str) -> Path:
    build.mkdir(parents=True, exist_ok=True)
    audio = build / "silence.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "2", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"
    srt.write_text(f"1\n00:00:00,200 --> 00:00:01,800\n{first_line}\n{second_line}\n\n", encoding="utf-8")
    vf = f"subtitles={srt.as_posix()}:force_style='{_STYLE}'"
    clip = build / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=2", "-i", str(audio), "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)], check=True, capture_output=True)
    return clip


def _row_bands(frame_path: Path, threshold: int = 200, gap: int = 5):
    """Groups bright rows into contiguous bands (a real 2-line caption
    produces two bands separated by the inter-line gap)."""
    gray = cv2.cvtColor(cv2.imread(str(frame_path)), cv2.COLOR_BGR2GRAY)
    bright_rows = np.where((gray > threshold).any(axis=1))[0]
    assert len(bright_rows), "no bright caption pixels found at all"
    bands = []
    band_start = bright_rows[0]
    prev = bright_rows[0]
    for row in bright_rows[1:]:
        if row - prev > gap:
            bands.append((band_start, prev))
            band_start = row
        prev = row
    bands.append((band_start, prev))
    return bands, gray


def _band_bright_width(gray, band) -> int:
    top, bottom = band
    region = gray[top:bottom + 1, :]
    cols = np.where((region > 200).any(axis=0))[0]
    return int(cols.max() - cols.min()) if len(cols) else 0


@requires_ffmpeg
def test_two_line_caption_stacks_top_line_first(tmp_path):
    # A much longer first line than second line -- if stacking were reversed,
    # the WIDER bright band would appear on the BOTTOM instead of the top.
    long_line = "가나다라마바사아자차카타파하가나다라마바사아자차카타파하"
    short_line = "가"
    clip = _render_two_line_caption(tmp_path / "build", long_line, short_line)
    frame = tmp_path / "frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "1.0", "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
    bands, gray = _row_bands(frame)
    assert len(bands) == 2, f"expected exactly 2 caption line bands, found {len(bands)}: {bands}"
    top_band, bottom_band = sorted(bands, key=lambda b: b[0])
    top_width = _band_bright_width(gray, top_band)
    bottom_width = _band_bright_width(gray, bottom_band)
    assert top_width > bottom_width, (
        f"expected the long first line on top (wider) and the short second line below (narrower), "
        f"got top_width={top_width} bottom_width={bottom_width}"
    )
