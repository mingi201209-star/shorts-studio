"""Synthetic Blender render farm integrity contract tests. No production release."""
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.render_farm.verify_probe import verify_folder


def sample(tmp_path: Path, shard: int=0):
    digest="a"*64
    indices=list(range(1+shard*3,4+shard*3))
    rows=[]
    for i in indices:
        payload=b"\x89PNG\r\n\x1a\n"+bytes([i])*100
        f=tmp_path/f"frame_{i:04d}.png"
        f.write_bytes(payload)
        rows.append({"frame":i,"sha256":hashlib.sha256(payload).hexdigest()})
    doc={"schema_version":1,"shard":shard,"renderer_sha256":digest,
         "resolution":[320,576],"samples":6,"fps":30,
         "upload_ready":False,"native_unique_frames":True,"frames":rows}
    (tmp_path/"proof.json").write_text(json.dumps(doc))
    return digest,doc


def test_valid_shard_is_not_release_approved(tmp_path):
    digest,_=sample(tmp_path)
    result=verify_folder(tmp_path,0,digest)
    assert result["frame_count"]==3
    assert not result["production_approved"]


def test_missing_frames_fail(tmp_path):
    digest,_=sample(tmp_path)
    (tmp_path/"frame_0002.png").unlink()
    with pytest.raises(ValueError,match="missing"):
        verify_folder(tmp_path,0,digest)


def test_changed_pixels_fail(tmp_path):
    digest,_=sample(tmp_path)
    (tmp_path/"frame_0002.png").write_bytes(b"\x89PNG\r\n\x1a\n"+b"x"*100)
    with pytest.raises(ValueError,match="checksum"):
        verify_folder(tmp_path,0,digest)


def test_unpinned_script_fail(tmp_path):
    _digest,_=sample(tmp_path)
    with pytest.raises(ValueError,match="source"):
        verify_folder(tmp_path,0,"b"*64)


def test_profile_downgrade_fail(tmp_path):
    digest,doc=sample(tmp_path)
    doc["samples"]=3
    (tmp_path/"proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="quality"):
        verify_folder(tmp_path,0,digest)
