"""A real production render hung for 17+ minutes with a live ffmpeg process
and zero error output, stopped only by the CI job's own 20-minute timeout --
none of render.py's ffmpeg/rsvg-convert/ffprobe subprocess.run calls had a
timeout of their own, so a single stuck encode could run forever (or until
some much larger, unrelated ceiling) with the recovery loop -- which exists
precisely to move past one bad asset -- never getting a chance to run.
Every such call must be bounded and turn a stuck subprocess into a clear,
prompt RuntimeError instead of hanging.
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import shorts_studio.render as R


def _fake_timeout(cmd, **kwargs):
    raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))


def test_composite_scene_clip_raises_clean_error_on_ffmpeg_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(R.subprocess, "run", _fake_timeout)
    asset = tmp_path / "a.jpg"; asset.write_bytes(b"x")
    audio = tmp_path / "a.mp3"; audio.write_bytes(b"x")
    srt = tmp_path / "a.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="s1", motion=SimpleNamespace(type="push_in"))
    with pytest.raises(RuntimeError, match="timed out"):
        R._composite_scene_clip(scene, asset, audio, srt, 1.0, 30, tmp_path, 0)


def test_composite_visual_beats_raises_clean_error_on_ffmpeg_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(R.subprocess, "run", _fake_timeout)
    asset_path = tmp_path / "a.jpg"; asset_path.write_bytes(b"x")
    monkeypatch.setattr(R, "_resolve_cached_asset", lambda *a, **k: asset_path)
    audio = tmp_path / "a.mp3"; audio.write_bytes(b"x")
    srt = tmp_path / "a.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n\n", encoding="utf-8")
    beat = SimpleNamespace(start=0.0, asset=None, asset_url="https://example.com/a.jpg", attribution="x", motion=SimpleNamespace(type="static"))
    scene = SimpleNamespace(id="s1", visual_beats=[beat])
    with pytest.raises(RuntimeError, match="timed out"):
        R._composite_visual_beats(scene, audio, srt, 1.0, 30, tmp_path, 0)


def test_ffmpeg_calls_are_bounded_by_a_real_timeout(tmp_path, monkeypatch):
    """Every ffmpeg/ffprobe/rsvg-convert subprocess.run call in render.py
    must pass a timeout -- the exact production bug was one call site
    (among several) with none at all, and only the job's own external
    20-minute CI timeout ever stopped it."""
    captured = []
    def recording_run(cmd, **kwargs):
        captured.append(kwargs.get("timeout"))
        class Result:
            stdout = '{"format": {"duration": "1.0"}}'
        return Result()
    monkeypatch.setattr(R.subprocess, "run", recording_run)
    asset = tmp_path / "a.jpg"; asset.write_bytes(b"x")
    audio = tmp_path / "a.mp3"; audio.write_bytes(b"x")
    srt = tmp_path / "a.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="s1", motion=SimpleNamespace(type="push_in"))
    R._composite_scene_clip(scene, asset, audio, srt, 1.0, 30, tmp_path, 0)
    R._media_duration_seconds(tmp_path / "s1.mp4")
    assert captured, "no subprocess.run calls were made"
    assert all(t is not None for t in captured), f"an ffmpeg/ffprobe call was made with no timeout: {captured}"
