"""Regression: a JPEG beat followed by a video beat must not wash out the video.

Real failure (hydroplaning quality-reset render): the photo beat was encoded
full-range (yuvj420p/pc), `concat -c copy` carried that flag over the whole
scene, and the next (limited-range) video beat decoded with the wrong range,
so the final MP4 no longer matched its pinned source.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image

from shorts_studio import render

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg required")


def _range(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=color_range,pix_fmt", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["streams"][0]


def _frame_mean(path, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
                          "-vf", f"crop=980:950:50:{render.IMAGE_TOP_Y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).astype(float).mean()


def test_photo_then_video_beats_join_without_range_shift(tmp_path):
    photo = tmp_path / "p.jpg"
    Image.new("RGB", (980, 950), (200, 60, 60)).save(photo, "JPEG", quality=95)
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x305070:s=980x950:r=30:d=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
    a = render._render_beat_clip(photo, 30, 30, tmp_path / "a.mp4")
    b = render._render_beat_clip(video, 30, 30, tmp_path / "b.mp4")
    for clip in (a, b):
        # untagged decodes as limited range; full range ("pc") must never appear
        assert _range(clip).get("color_range", "unknown") in ("tv", "unknown")
        assert _range(clip)["pix_fmt"] == "yuv420p"
    lst = tmp_path / "l.txt"
    lst.write_text(f"file '{a}'\nfile '{b}'\n")
    joined = tmp_path / "j.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], check=True)
    # The video beat must look the same inside the joined scene as on its own.
    assert abs(_frame_mean(joined, 1.5) - _frame_mean(b, 0.5)) < 2.0
    assert abs(_frame_mean(joined, 0.5) - _frame_mean(a, 0.5)) < 2.0


def test_bt2020_beat_after_bt709_beat_keeps_its_colours(tmp_path):
    """HLG/BT.2020-tagged footage joined after a BT.709 beat must decode the same."""
    first = tmp_path / "709.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x406080:s=980x950:r=30:d=2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                    "-color_trc", "bt709", str(first)], check=True)
    second = tmp_path / "2020.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0xC07030:s=980x950:r=30:d=2",
                    "-vf", "scale=out_color_matrix=bt2020", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-colorspace", "bt2020nc", "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                    str(second)], check=True)
    a = render._render_beat_clip(first, 30, 30, tmp_path / "a.mp4")
    b = render._render_beat_clip(second, 30, 30, tmp_path / "b.mp4")
    lst = tmp_path / "l.txt"
    lst.write_text(f"file '{a}'\nfile '{b}'\n")
    joined = tmp_path / "j.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)], check=True)
    assert abs(_frame_mean(joined, 1.5) - _frame_mean(b, 0.5)) < 2.0


def test_beat_boundaries_do_not_accumulate_frame_rounding():
    starts = [0.0, 1.84, 5.0005, 6.557, 7.01]
    counts = render._beat_frame_counts(starts, 9.172, 30)
    assert sum(counts) == round(9.172 * 30)
    edge = 0
    for start, n in zip(starts, counts):
        assert abs(edge / 30 - start) <= 0.5 / 30 + 1e-9
        edge += n


def _route_beats(tmp_path, monkeypatch, names):
    """Run _composite_visual_beats with stubbed ffmpeg steps; return which
    renderer handled each beat."""
    from types import SimpleNamespace
    assets = [tmp_path / n for n in names]
    beats = [SimpleNamespace(start=float(i), asset=str(a), asset_url=None, attribution=None)
             for i, a in enumerate(assets)]
    scene = SimpleNamespace(id="s", visual_beats=beats, overlay_title_seconds=None)
    calls = []
    monkeypatch.setattr(render, "_resolve_cached_asset", lambda cand, *a, **k: render.Path(cand["asset"]))
    monkeypatch.setattr(render, "_log_asset_diagnostics", lambda *a, **k: None)
    monkeypatch.setattr(render, "_render_beat_clip", lambda asset, frames, fps, out: calls.append(("normalised", asset.name)) or out)
    monkeypatch.setattr(render, "_render_legacy_still_beat_clip", lambda asset, secs, fps, out: calls.append(("legacy", asset.name)) or out)
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(render, "_media_duration_seconds", lambda p: 1.0)
    render._composite_visual_beats(scene, tmp_path / "a.mp3", tmp_path / "a.srt", float(len(names)), 30, tmp_path, 0)
    return calls


def test_all_still_scene_keeps_the_verified_legacy_still_render(tmp_path, monkeypatch):
    # Comet-style scenes: the BT.709 normalisation shifted CLIP margins of
    # already-verified stills, so all-still scenes must stay on the legacy path.
    calls = _route_beats(tmp_path, monkeypatch, ["a.jpg", "b.png", "c.jpg"])
    assert calls == [("legacy", "a.jpg"), ("legacy", "b.png"), ("legacy", "c.jpg")]


def test_scene_mixing_stills_and_video_normalises_every_beat(tmp_path, monkeypatch):
    # One video beat means concat must join uniform colour tags: every beat,
    # including the stills, goes through the normalised renderer.
    calls = _route_beats(tmp_path, monkeypatch, ["a.jpg", "b.mp4", "c.png"])
    assert calls == [("normalised", "a.jpg"), ("normalised", "b.mp4"), ("normalised", "c.png")]
