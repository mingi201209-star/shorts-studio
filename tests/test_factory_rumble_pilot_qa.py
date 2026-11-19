"""Technical integrity does not imply the draft 3D pilot is uploadable."""
import json
from pathlib import Path

import pytest
from PIL import Image

from shorts_studio.factory.rumble_pilot_qa import verify

SRC_SHA = "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877"


def fixture(tmp_path: Path, frames=3):
    for k in range(frames):
        Image.new("RGB", (450,800), (35+20*k, 55, 76)).save(
            tmp_path / f"frame_{k+1:04d}.png")
    proof={
        "frames": frames, "preview_only":True, "resolution":[450,800],
        "cycles_samples":7, "car_mesh_parts":72,
        "rotating_wheel_pivots":4, "physically_calibrated":False,
        "upload_ready":False, "source_sha256":SRC_SHA, "view":"hero",
        "render_seconds":[3.1]*frames,
    }
    (tmp_path / "preview-proof.json").write_text(json.dumps(proof))
    return proof


def test_valid_motion_proof_never_grants_upload(tmp_path):
    fixture(tmp_path)
    result=verify(tmp_path,3,preview=True)
    assert result["frame_count"]==result["unique_frames"]==3
    assert not result["upload_authorized"]


@pytest.mark.parametrize("field,value", [
    ("cycles_samples",3),("resolution",[360,640]),
    ("rotating_wheel_pivots",0),("car_mesh_parts",1),
    ("physically_calibrated",True),("upload_ready",True),
    ("source_sha256","a"*64),("view","other"),("render_seconds",[]),
])
def test_forbidden_proof_metadata_rejected(tmp_path,field,value):
    proof=fixture(tmp_path)
    proof[field]=value
    (tmp_path/"preview-proof.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError):
        verify(tmp_path,3,preview=True)


def test_identical_frames_rejected(tmp_path):
    fixture(tmp_path)
    (tmp_path/"frame_0003.png").write_bytes((tmp_path/"frame_0002.png").read_bytes())
    with pytest.raises(ValueError,match="identical|duplicated"):
        verify(tmp_path,3,preview=True)


def test_missing_frame_rejected(tmp_path):
    fixture(tmp_path)
    (tmp_path/"frame_0002.png").unlink()
    with pytest.raises(ValueError,match="missing"):
        verify(tmp_path,3,preview=True)


def test_black_frame_rejected(tmp_path):
    fixture(tmp_path)
    Image.new("RGB",(450,800),(0,0,0)).save(tmp_path/"frame_0001.png")
    with pytest.raises(ValueError,match="black"):
        verify(tmp_path,3,preview=True)


def test_downgraded_to_preview_cannot_claim_native(tmp_path):
    fixture(tmp_path)
    with pytest.raises(ValueError):
        verify(tmp_path,3,preview=False)
