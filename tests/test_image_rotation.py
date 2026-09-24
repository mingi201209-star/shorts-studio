"""Real, pixel-level regression for three requirements: (1) a scene's
picture is shown FIXED and centered -- no pan/zoom motion is ever applied
to it; (2) the background outside the foreground image is solid black, not
a blurred copy of the image; (3) a scene with more than one declared asset
(primary + recovery_candidates) and no semantic QA to protect rotates
through them across its duration instead of showing one image the whole
time. A QA-gated scene (declares visual_qa_requirements) always keeps the
single fixed image it had before -- rotation only applies where nothing
can fail against it.
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


# --- no motion: the ffmpeg command itself never contains a pan/zoom node ---

@requires_ffmpeg
def test_composite_command_never_contains_zoompan(tmp_path, monkeypatch):
    build = tmp_path / "build"; build.mkdir()
    seen_cmds = []
    real_run = subprocess.run
    def spy_run(cmd, *a, **k):
        seen_cmds.append(cmd)
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(R.subprocess, "run", spy_run)
    audio = _silence(build, 2.0)
    asset = _solid_image(build / "a.png", (10, 20, 30))
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x")
    R._composite_scene_clip(scene, asset, audio, srt, 2.0, 30, build, 0)
    ffmpeg_cmds = [c for c in seen_cmds if c[0] == "ffmpeg"]
    assert ffmpeg_cmds, "expected at least one real ffmpeg invocation"
    for cmd in ffmpeg_cmds:
        joined = " ".join(cmd)
        assert "zoompan" not in joined, f"found a pan/zoom filter in a supposedly fixed-image composite: {joined}"


@requires_ffmpeg
def test_single_image_position_is_identical_at_two_different_times(tmp_path):
    """If the old zoompan motion were still applied, the foreground's scale
    (and therefore the exact pixel color at a fixed sample point near its
    edge) would drift slightly between two well-separated timestamps. A
    truly fixed image must sample IDENTICALLY."""
    build = tmp_path / "build"; build.mkdir()
    audio = _silence(build, 4.0)
    asset = _solid_image(build / "a.png", (200, 60, 10))
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x")
    clip = R._composite_scene_clip(scene, asset, audio, srt, 4.0, 30, build, 0)
    early = build / "early.jpg"; late = build / "late.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.2", "-i", str(clip), "-frames:v", "1", str(early)], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-ss", "3.7", "-i", str(clip), "-frames:v", "1", str(late)], check=True, capture_output=True)
    assert _fg_center_bgr(early) == _fg_center_bgr(late)


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
    """No recovery_candidates declared: the historical single-image-for-the-
    whole-clip behavior is unchanged."""
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
