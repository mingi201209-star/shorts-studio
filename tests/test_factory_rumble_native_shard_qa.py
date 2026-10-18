import json
from pathlib import Path

import pytest
from PIL import Image

from shorts_studio.factory.rumble_episode2 import travel_x
from shorts_studio.factory.rumble_native_shard_qa import digest, verify

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"examples/factory/rumble-episode2-30s.json"
SCRIPT=ROOT/"benchmarks/road_safety/render_rumble_episode2.py"


def make(tmp_path):
    records=[]
    for i in (1,2):
        p=tmp_path/f"frame_{i:04d}.png"
        Image.new("RGB",(1080,1920),(40+i,50,60)).save(p)
        records.append({"frame":i,"shot_id":"hook_warning",
                        "absolute_x_m":round(travel_x(i),7),
                        "sha256":digest(p)})
    proof={"episode_id":"rumble-strip-alerts","source_sha256":
        "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877",
        "renderer_source_sha256":digest(SCRIPT),"renderer":"CYCLES",
        "preview_only":False,"resolution":[1080,1920],
        "cycles_samples":32,"fps":30,"rotating_wheel_pivots":4,
        "car_mesh_parts":72,"physically_calibrated":False,"upload_ready":False,
        "original_frame_records":records,"frame_numbers":[1,2],"frames":2,
        "first_frame":1,"last_frame":2,
        "camera_by_shot":{"hook_warning":[[2,3,4],[0,0,0],9.2]}}
    (tmp_path/"episode-proof.json").write_text(json.dumps(proof))
    return proof


def test_valid_new_frames_never_authorize_upload(tmp_path):
    make(tmp_path)
    assert verify(tmp_path,MANIFEST,SCRIPT)["upload_authorized"] is False


@pytest.mark.parametrize("key,value", [
    ("preview_only",True),("resolution",[450,800]),
    ("cycles_samples",7),("renderer","BLENDER_EEVEE_NEXT"),
    ("source_sha256","a"*64),("renderer_source_sha256","b"*64),
    ("upload_ready",True),("rotating_wheel_pivots",0),
])
def test_cannot_downgrade(tmp_path,key,value):
    doc=make(tmp_path)
    doc[key]=value
    (tmp_path/"episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        verify(tmp_path,MANIFEST,SCRIPT)


def test_cannot_reset_global_motion(tmp_path):
    doc=make(tmp_path)
    doc["original_frame_records"][1]["absolute_x_m"]=0
    (tmp_path/"episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="global"):
        verify(tmp_path,MANIFEST,SCRIPT)


def test_cannot_duplicate_images(tmp_path):
    doc=make(tmp_path)
    q=tmp_path/"frame_0002.png"
    q.write_bytes((tmp_path/"frame_0001.png").read_bytes())
    doc["original_frame_records"][1]["sha256"]=digest(q)
    (tmp_path/"episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="cloning"):
        verify(tmp_path,MANIFEST,SCRIPT)
