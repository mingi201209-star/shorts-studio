"""Reject frame drift and file-count shortcuts when comparing render profiles."""
from pathlib import Path

import pytest
from PIL import Image

from benchmarks.factory_perf.benchmark import compare_frames


def put(root: Path, frames: list[tuple[int,int,int]]):
    root.mkdir()
    for i,c in enumerate(frames,1):
        Image.new("RGB",(9,13),c).save(root/f"frame_{i:04d}.png")


def test_pixel_identical_even_when_binary_compression_differs(tmp_path):
    a=tmp_path/"a"; b=tmp_path/"b"
    put(a,[(0,0,0),(255,0,100)])
    put(b,[(0,0,0),(255,0,100)])
    assert compare_frames(a,b)=={"frames_compared":2,"different_frames":0,"max_channel_difference":0,"pixel_exact":True}


def test_visible_change_rejected(tmp_path):
    a=tmp_path/"a"; b=tmp_path/"b"
    put(a,[(1,2,3),(20,30,40)])
    put(b,[(1,2,4),(20,30,40)])
    result=compare_frames(a,b)
    assert not result["pixel_exact"]
    assert result["max_channel_difference"]==1


def test_missing_frame_rejected(tmp_path):
    a=tmp_path/"a"; b=tmp_path/"b"
    put(a,[(1,2,3)])
    put(b,[(1,2,3),(4,5,6)])
    with pytest.raises(ValueError,match="unequal"):
        compare_frames(a,b)
