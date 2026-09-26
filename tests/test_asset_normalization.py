"""A real production render hung for 17+ minutes with a live ffmpeg process
on one scene's asset -- confirmed (via a bounded ffmpeg timeout plus an
ffprobe header read) not a size problem: a modest 2.4MB, 1399x1795 RGBA PNG.
Every other scene's plain baseline JPEG composited fine in ~5-6s. Rather
than depend on fully understanding ffmpeg's own internal decode path for
that exact file, every freshly-downloaded raster asset is now normalized
through Pillow -- a fully independent decoder -- into a flat, alpha-free
baseline JPEG before ffmpeg ever sees it.
"""
from pathlib import Path

import pytest
from PIL import Image

import shorts_studio.render as R


def _write_rgba_png(path: Path, size=(40, 30)) -> Path:
    img = Image.new("RGBA", size, (10, 20, 30, 128))
    img.save(path, "PNG")
    return path


def test_downloaded_rgba_png_is_flattened_to_alpha_free_jpeg(tmp_path, monkeypatch):
    def fake_download(url, path):
        _write_rgba_png(path)
        return path
    monkeypatch.setattr(R, "_download", fake_download)
    result = R._resolve_asset({"asset": None, "asset_url": "https://example.com/a.png"}, tmp_path, "s1", 0)
    assert result.suffix == ".jpg"
    with Image.open(result) as out:
        assert out.mode == "RGB"
        assert "A" not in out.getbands()


def test_downloaded_plain_jpeg_still_normalized_to_rgb(tmp_path, monkeypatch):
    def fake_download(url, path):
        Image.new("RGB", (20, 20), (5, 5, 5)).save(path, "JPEG")
        return path
    monkeypatch.setattr(R, "_download", fake_download)
    result = R._resolve_asset({"asset": None, "asset_url": "https://example.com/a.jpg"}, tmp_path, "s1", 0)
    with Image.open(result) as out:
        assert out.mode == "RGB"


def test_local_asset_path_is_left_untouched(tmp_path):
    """A scene author's own local `asset` file (not downloaded) keeps its
    existing pass-through contract -- only freshly-downloaded assets are
    normalized, since a local file is whatever the author explicitly
    provided, not something scraped off the open web."""
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"not-a-real-image")
    result = R._resolve_asset({"asset": str(img), "asset_url": None}, tmp_path, "s1", 0)
    assert result == img
    assert result.read_bytes() == b"not-a-real-image"
