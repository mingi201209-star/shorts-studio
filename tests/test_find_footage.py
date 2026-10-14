"""Footage finder: which Commons rendition a topic spec pins."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "find_footage", Path(__file__).resolve().parents[1] / "scripts" / "find_footage.py")
find_footage = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(find_footage)

BASE = "https://upload.wikimedia.org/wikipedia/commons/3/32/"


def test_a_large_photo_is_pinned_as_the_standard_1920px_thumbnail():
    chosen = find_footage.photo_rendition({"url": BASE + "Drill_Holes.jpg?x=1", "width": 3600, "height": 2700})
    assert chosen == {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Drill_Holes.jpg/1920px-Drill_Holes.jpg",
                      "width": 1920, "height": 1440}


def test_the_original_is_kept_when_a_thumbnail_would_be_too_small_or_re_encoded():
    small = {"url": BASE + "Small.jpg", "width": 1563, "height": 1143}
    panorama = {"url": BASE + "Pano.jpg", "width": 5475, "height": 2015}
    tiff = {"url": BASE + "Sunset.tif", "width": 4000, "height": 3000}
    for info in (small, panorama, tiff):
        assert find_footage.photo_rendition(info)["url"] == info["url"]
