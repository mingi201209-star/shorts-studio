"""Do not mistake a reused native film for fast fresh 3D rendering."""
import json
from pathlib import Path

import pytest

from shorts_studio.factory.cached_native_delivery import (
    CacheDeliveryError,
    verify_native_cached_delivery,
)


def fake_media(tmp_path: Path, monkeypatch, frames=900, size=(1080, 1920),
               fps="30/1", duration="30.032", aac=True):
    movie = tmp_path / "movie.mp4"
    movie.write_bytes(b"\x00" * 1_000_001)
    profile = {"format": {"duration": duration}, "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": size[0],
         "height": size[1], "r_frame_rate": fps, "nb_read_frames": str(frames)},
        {"codec_type": "audio", "codec_name": "aac" if aac else "mp3"},
    ]}

    class Result:
        stdout = json.dumps(profile)

    monkeypatch.setattr(
        "shorts_studio.factory.cached_native_delivery.subprocess.run",
        lambda *args, **kwargs: Result(),
    )
    return movie


def test_valid_cached_native_video_keeps_publish_blocked(tmp_path, monkeypatch):
    movie = fake_media(tmp_path, monkeypatch)
    verdict = verify_native_cached_delivery(movie, elapsed_seconds=139)
    assert verdict["under_five_minutes"]
    assert verdict["decoded_frames"] == 900
    assert verdict["independent_new_geometry_rendered"] is False
    assert verdict["editorial_upload_approved"] is False


@pytest.mark.parametrize("duration,frames,size,fps,aac", [
    ("30.0", 899, (1080, 1920), "30/1", True),
    ("30.0", 900, (720, 1280), "30/1", True),
    ("30.0", 900, (1080, 1920), "24/1", True),
    ("31.0", 900, (1080, 1920), "30/1", True),
    ("30.0", 900, (1080, 1920), "30/1", False),
])
def test_native_regressions_are_rejected(
    tmp_path, monkeypatch, duration, frames, size, fps, aac
):
    movie = fake_media(tmp_path, monkeypatch, frames, size, fps, duration, aac)
    with pytest.raises(CacheDeliveryError):
        verify_native_cached_delivery(movie, elapsed_seconds=150)


def test_over_budget_must_fail(tmp_path, monkeypatch):
    movie = fake_media(tmp_path, monkeypatch)
    with pytest.raises(CacheDeliveryError, match="over budget"):
        verify_native_cached_delivery(movie, elapsed_seconds=300.1)


def test_five_minute_limit_cannot_be_relaxed(tmp_path, monkeypatch):
    movie = fake_media(tmp_path, monkeypatch)
    with pytest.raises(CacheDeliveryError, match="SLA"):
        verify_native_cached_delivery(movie, deadline_seconds=360)
