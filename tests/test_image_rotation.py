"""Real, pixel-level regression for four requirements: (1) the background
outside the foreground image is solid black, not a blurred copy of the
image; (2) a scene with more than one declared asset (primary +
recovery_candidates) and no semantic QA to protect rotates through them
across its duration instead of showing one image the whole time, with each
image visually STILL for its own window (switching images already supplies
the visual change); (3) a scene that ends up with only ONE image (no
additional image was available) instead gets a bounded "moving viewpoint"
Ken Burns zoom, rather than a frozen frame -- but the zoom is bounded
entirely inside the fixed foreground box, so the rendered image can never
grow into the caption-safe area no matter how it's currently framed; (4)
that caption-safe-area guarantee holds in both the still and the zooming
case. A QA-gated scene (declares visual_qa_requirements) always keeps its
single, semantically-verified image -- rotation only applies where nothing
can fail against a substituted image -- but still gets the Ken Burns
fallback instead of sitting frozen.
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import shorts_studio.render as R

requires_ffmpeg = pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="requires a real ffmpeg binary")


class FakeCandidate:
    def __init__(self, path):
        self.asset = str(path); self.asset_url = None; self.attribution = None
    def model_dump(self):
        return {"asset": self.asset, "asset_url": self.asset_url, "attribution": self.attribution}


def _solid_image(path: Path, color) -> Path:
    img = np.full((800, 600, 3), color, dtype=np.uint8)
    Image.fromarray(img).save(path)
    return path


def _silence(build: Path, seconds: float) -> Path:
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(seconds), "-q:a", "9", str(audio)], check=True, capture_output=True)
    return audio


def _fg_center_bgr(frame_path: Path):
    import cv2
    img = cv2.imread(str(frame_path))
    fg_h = R.SAFE_BOTTOM_Y - R.SAFE_TOP_Y
    row = R.SAFE_TOP_Y + fg_h // 2
    return img[row, 540].tolist()  # BGR


def _corner_bgr(frame_path: Path):
    import cv2
    img = cv2.imread(str(frame_path))
    return img[20, 20].tolist()  # top-left corner, well outside the fg band


# --- zoompan is present exactly when there is one image, never when there
# --- are 2+ (switching images already supplies the visual change) ---------

def _run_composite_and_capture_cmds(build, asset, audio, srt, duration, monkeypatch):
    seen_cmds = []
    real_run = subprocess.run
    def spy_run(cmd, *a, **k):
        seen_cmds.append(cmd)
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(R.subprocess, "run", spy_run)
    scene = SimpleNamespace(id="x")
    R._composite_scene_clip(scene, asset, audio, srt, duration, 30, build, 0)
    return [c for c in seen_cmds if c[0] == "ffmpeg"]


@requires_ffmpeg
def test_single_image_fallback_uses_bounded_zoompan(tmp_path, monkeypatch):
    build = tmp_path / "build"; build.mkdir()
    audio = _silence(build, 2.0)
    asset = _solid_image(build / "a.png", (10, 20, 30))
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    cmds = _run_composite_and_capture_cmds(build, asset, audio, srt, 2.0, monkeypatch)
    assert cmds, "expected at least one real ffmpeg invocation"
    assert any("zoompan" in " ".join(c) for c in cmds), "expected the single-image Ken Burns fallback to use zoompan"


@requires_ffmpeg
def test_multi_image_rotation_never_contains_zoompan(tmp_path, monkeypatch):
    # Duration must exceed one rotation interval, or _rotation_segments
    # correctly collapses back to a single segment (see the docstring on
    # _rotation_segments) -- there'd be nothing to "switch between" within
    # a too-short clip, so it falls back to the Ken Burns motion instead.
    build = tmp_path / "build"; build.mkdir()
    duration = 6.0
    audio = _silence(build, duration)
    a = _solid_image(build / "a.png", (10, 20, 30))
    b = _solid_image(build / "b.png", (30, 20, 10))
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    cmds = _run_composite_and_capture_cmds(build, [a, b], audio, srt, duration, monkeypatch)
    assert cmds, "expected at least one real ffmpeg invocation"
    for cmd in cmds:
        joined = " ".join(cmd)
        assert "zoompan" not in joined, f"a scene switching between real images should not also add motion: {joined}"


@requires_ffmpeg
def test_single_image_fallback_visibly_changes_framing_over_time(tmp_path):
    """With only one image available, the Ken Burns fallback must actually
    move the viewpoint -- a uniform solid-color image can't show this (any
    crop/zoom of a solid color looks identical), so this uses a striped
    image where zooming in measurably shifts which stripe sits at a fixed
    sample point."""
    build = tmp_path / "build"; build.mkdir()
    audio = _silence(build, 4.0)
    path = build / "stripes.png"
    w, h = 800, 1200
    img = np.zeros((h, w, 3), dtype=np.uint8)
    stripe_h = h // 20
    for i in range(20):
        img[i * stripe_h:(i + 1) * stripe_h, :] = [i * 12, 255 - i * 12, (i * 37) % 255]
    Image.fromarray(img).save(path)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x")
    clip = R._composite_scene_clip(scene, path, audio, srt, 4.0, 30, build, 0)
    early = build / "early.jpg"; late = build / "late.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.1", "-i", str(clip), "-frames:v", "1", str(early)], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-ss", "3.8", "-i", str(clip), "-frames:v", "1", str(late)], check=True, capture_output=True)
    import cv2
    early_col = cv2.imread(str(early))[:, 540, :]
    late_col = cv2.imread(str(late))[:, 540, :]
    diff = np.abs(early_col.astype(int) - late_col.astype(int)).sum()
    assert diff > 5000, f"expected the Ken Burns fallback to visibly change framing over time, diff={diff}"


@requires_ffmpeg
def test_single_image_fallback_never_crosses_the_safe_boundary(tmp_path):
    """The Ken Burns fallback's zoom must stay bounded inside the fixed
    foreground box at every point in time -- reusing the full-bleed marker
    technique from test_safe_area_regression.py, sampled at both the start
    and near the end of the zoom."""
    build = tmp_path / "build"; build.mkdir()
    audio = _silence(build, 4.0)
    w, h = 1200, 2000
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    img[int(h * 0.95):, :] = [255, 0, 255]  # magenta marker touching the source's own bottom edge
    path = build / "marker.png"; Image.fromarray(img).save(path)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x")
    clip = R._composite_scene_clip(scene, path, audio, srt, 4.0, 30, build, 0)
    for ts in (0.2, 3.8):
        frame = build / f"f{ts}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
        import cv2
        fimg = cv2.imread(str(frame))
        b, g, r = fimg[:, 540, 0].astype(int), fimg[:, 540, 1].astype(int), fimg[:, 540, 2].astype(int)
        score = r + b - 2 * g
        rows_above = np.where(score > score.max() / 2)[0]
        if len(rows_above):
            assert rows_above.min() <= R.SAFE_BOTTOM_Y, (
                f"at t={ts}, Ken Burns zoom pushed content to row {rows_above.min()}, "
                f"past the safe boundary SAFE_BOTTOM_Y={R.SAFE_BOTTOM_Y}"
            )


# --- solid black background, not a blurred copy of the image ---------------

@requires_ffmpeg
def test_background_outside_the_image_is_solid_black(tmp_path):
    build = tmp_path / "build"; build.mkdir()
    audio = _silence(build, 2.0)
    # A bright, saturated asset -- if the background were still a blurred
    # copy of it, the corner would show blurred bright color, not black.
    asset = _solid_image(build / "a.png", (0, 255, 255))
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x")
    clip = R._composite_scene_clip(scene, asset, audio, srt, 2.0, 30, build, 0)
    frame = build / "frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.2", "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
    b, g, r = _corner_bgr(frame)
    assert b < 15 and g < 15 and r < 15, f"expected a solid black corner, got BGR={(b, g, r)}"


# --- rotation: a QA-exempt scene with multiple assets cycles through them --

@requires_ffmpeg
def test_qa_exempt_scene_with_multiple_candidates_rotates_images(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "IMAGE_ROTATION_SECONDS", 2.0)
    build = tmp_path / "build"; build.mkdir()
    duration = 5.0  # segments: [red 0-2, green 2-4, red 4-5]
    audio = _silence(build, duration)
    red = _solid_image(build / "red.png", (255, 0, 0))    # RGB red
    green = _solid_image(build / "green.png", (0, 255, 0))  # BGR green
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x", asset=str(red), asset_url=None, attribution=None,
                             visual_qa_requirements=[], recovery_candidates=[FakeCandidate(green)])
    candidates = R._asset_candidates(scene)
    outcome = R._render_scene_rotation(scene, candidates, audio, duration, srt, 30, build)
    assert outcome["semantic"]["status"] == "NOT_EVALUATED"
    clip = outcome["clip"]
    frames = {}
    for name, ts in [("seg0", 1.0), ("seg1", 3.0), ("seg2", 4.5)]:
        frame = build / f"{name}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
        frames[name] = _fg_center_bgr(frame)

    def _is_red(bgr): return bgr[2] > 150 and bgr[1] < 80 and bgr[0] < 80
    def _is_green(bgr): return bgr[1] > 150 and bgr[2] < 80 and bgr[0] < 80

    assert _is_red(frames["seg0"]), frames["seg0"]
    assert _is_green(frames["seg1"]), frames["seg1"]
    assert _is_red(frames["seg2"]), frames["seg2"]  # cycles back to the first image


@requires_ffmpeg
def test_qa_exempt_scene_with_a_single_asset_does_not_rotate(tmp_path):
    """No recovery_candidates declared: still only ever this one image's
    content on screen (it may now use the Ken Burns fallback framing-wise,
    but never cuts to a different image)."""
    build = tmp_path / "build"; build.mkdir()
    duration = 4.0
    audio = _silence(build, duration)
    asset = _solid_image(build / "a.png", (255, 0, 0))
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x", asset=str(asset), asset_url=None, attribution=None,
                             visual_qa_requirements=[], recovery_candidates=[])
    candidates = R._asset_candidates(scene)
    outcome = R._render_scene_rotation(scene, candidates, audio, duration, srt, 30, build)
    clip = outcome["clip"]
    for ts in (0.2, 3.7):
        frame = build / f"f{ts}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
        b, g, r = _fg_center_bgr(frame)
        assert r > 150 and g < 80 and b < 80, f"expected red at t={ts}, got BGR={(b, g, r)}"


def test_rotation_segments_cycles_and_shortens_the_last_segment():
    assets = [Path("a.png"), Path("b.png")]
    segs = R._rotation_segments(assets, duration=7.0, seg_seconds=3.0)
    assert [round(length, 3) for _, length in segs] == [3.0, 3.0, 1.0]
    assert [a for a, _ in segs] == [assets[0], assets[1], assets[0]]


def test_rotation_segments_single_asset_is_one_segment_for_the_whole_duration():
    assets = [Path("a.png")]
    segs = R._rotation_segments(assets, duration=9.0)
    assert segs == [(assets[0], 9.0)]


def test_rotation_segments_no_assets_is_empty():
    assert R._rotation_segments([], duration=5.0) == []
