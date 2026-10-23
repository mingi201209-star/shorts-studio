import json
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from shorts_studio.factory.rumble_episode2 import travel_x
from shorts_studio.factory.rumble_native_shard_qa import digest, verify

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"examples/factory/rumble-episode2-30s.json"
SCRIPT=ROOT/"benchmarks/road_safety/render_rumble_episode2.py"


def make(tmp_path, frames=(1, 2)):
    records=[]
    for i in frames:
        p=tmp_path/f"frame_{i:04d}.png"
        Image.new("RGB",(1080,1920),(40+i,50,60)).save(p)
        records.append({"frame":i,"shot_id":"hook_warning",
                        "absolute_x_m":round(travel_x(i),7),
                        "sha256":digest(p),"render_seconds":1.25})
    proof={"episode_id":"rumble-strip-alerts","source_sha256":
        "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877",
        "renderer_source_sha256":digest(SCRIPT),"renderer":"CYCLES",
        "preview_only":False,"resolution":[1080,1920],
        "cycles_samples":32,"fps":30,"rotating_wheel_pivots":4,
        "car_mesh_parts":72,"physically_calibrated":False,"upload_ready":False,
        "original_frame_records":records,"frame_numbers":list(frames),"frames":len(frames),
        "first_frame":frames[0],"last_frame":frames[-1],
        "render_seconds":[1.25 for _ in frames],
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


@pytest.mark.parametrize("position", [float("nan"), float("inf"), -float("inf"), True, "0", None])
def test_invalid_global_position_cannot_certify_native_motion(tmp_path, position):
    doc = make(tmp_path)
    doc["original_frame_records"][0]["absolute_x_m"] = position
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="global position"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("camera", [
    None, {}, [], [[2, 3, 4], [0, 0, 0]],
    [[2, 3], [0, 0, 0], 3.2],
    [[2, 3, 4], [0, 0], 3.2],
    [[float("nan"), 3, 4], [0, 0, 0], 3.2],
    [[2, 3, 4], [0, float("inf"), 0], 3.2],
    [[2, 3, 4], [0, 0, 0], float("nan")],
    [[2, 3, 4], [0, 0, 0], 0],
    [[2, 3, 4], [0, 0, 0], -1],
    [[2, 3, 4], [0, 0, 0], True],
    [[2, 3, 4], [0, 0, 0], "3.2"],
])
def test_invalid_camera_cannot_certify_fixed_shot(tmp_path, camera):
    doc = make(tmp_path)
    doc["camera_by_shot"]["hook_warning"] = camera
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="camera"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("reencode", [False, True])
def test_nonadjacent_repeated_pixels_cannot_masquerade_as_native_motion(tmp_path, reencode):
    doc = make(tmp_path, frames=(1, 2, 3))
    first = tmp_path / "frame_0001.png"
    repeated = tmp_path / "frame_0003.png"
    if reencode:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("description", "Different PNG bytes; identical decoded pixels")
        with Image.open(first) as picture:
            picture.save(repeated, pnginfo=metadata)
        assert digest(first) != digest(repeated)
    else:
        repeated.write_bytes(first.read_bytes())
    doc["original_frame_records"][2]["sha256"] = digest(repeated)
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="cloning"):
        verify(tmp_path, MANIFEST, SCRIPT)


def test_three_distinct_decoded_frames_remain_valid(tmp_path):
    make(tmp_path, frames=(1, 2, 3))
    result = verify(tmp_path, MANIFEST, SCRIPT)
    assert result["frames"] == 3
    assert result["upload_authorized"] is False


@pytest.mark.parametrize("times", [
    None, [], [1.25], [1.25, 1.25, 1.25],
    [float("nan"), 1.25], [float("inf"), 1.25],
    [0, 1.25], [-1, 1.25], [True, 1.25], ["1.25", 1.25],
])
def test_invalid_render_times_cannot_support_cost_planning(tmp_path, times):
    doc = make(tmp_path)
    doc["render_seconds"] = times
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="render time"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("record_time", [None, float("nan"), True, 2.5])
def test_per_frame_time_must_match_the_render_time_series(tmp_path, record_time):
    doc = make(tmp_path)
    doc["original_frame_records"][0]["render_seconds"] = record_time
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="render time"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("case", ["black", "near_black", "tiny_bright_patch"])
def test_black_pixels_cannot_pass_via_large_png_or_valid_metadata(tmp_path, case):
    doc = make(tmp_path)
    path = tmp_path / "frame_0001.png"
    picture = Image.new("RGB", (1080, 1920), (1, 1, 1) if case == "near_black" else (0, 0, 0))
    if case == "tiny_bright_patch":
        picture.paste((255, 255, 255), (530, 950, 550, 970))
    # Isolate decoded-image QA: file size and checksum must already be valid.
    picture.save(path, compress_level=0)
    assert path.stat().st_size >= 10000
    doc["original_frame_records"][0]["sha256"] = digest(path)
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="black or empty"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("field,value", [
    ("frame_numbers", [True, 2]), ("record_frame", True),
    ("frames", 2.0), ("first_frame", True), ("last_frame", 2.0),
])
def test_frame_identity_requires_json_integers(tmp_path, field, value):
    doc = make(tmp_path)
    if field == "record_frame":
        doc["original_frame_records"][0]["frame"] = value
    else:
        doc[field] = value
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="frame numbering"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("container", ["JPEG", "APNG"])
def test_native_png_requires_single_real_png_image(tmp_path, container):
    doc = make(tmp_path)
    path = tmp_path / "frame_0001.png"
    picture = Image.new("RGB", (1080, 1920), (70, 80, 90))
    if container == "JPEG":
        picture.save(path, format="JPEG", quality=95)
    else:
        picture.save(path, format="PNG", save_all=True,
                     append_images=[Image.new("RGB", (1080, 1920), (80, 90, 100))],
                     duration=100, compress_level=0)
    assert path.stat().st_size >= 10000
    doc["original_frame_records"][0]["sha256"] = digest(path)
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="single PNG"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("field,value", [
    ("preview_only", 0), ("physically_calibrated", 0), ("upload_ready", 0),
    ("cycles_samples", 32.0), ("fps", 30.0), ("rotating_wheel_pivots", 4.0),
    ("resolution", [1080.0, 1920]), ("resolution", [1080, 1920.0]),
])
def test_native_contract_rejects_numeric_type_aliases(tmp_path, field, value):
    doc = make(tmp_path)
    doc[field] = value
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="native shard contract"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("parts", [
    float("nan"), float("inf"), -float("inf"), True, 72.0, "72", None,
])
def test_mesh_count_requires_a_real_integer(tmp_path, parts):
    doc = make(tmp_path)
    doc["car_mesh_parts"] = parts
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="car geometry"):
        verify(tmp_path, MANIFEST, SCRIPT)


@pytest.mark.parametrize("edge,width,rejected", [
    ("bottom", 1080, True), ("top", 1080, True), ("bottom", 540, False),
])
def test_full_width_black_edge_band_is_a_camera_clip_void(tmp_path, edge, width, rejected):
    # A camera plane below grade leaves a full-width black band (~5% of the
    # height) while the frame mean still clears the black/empty gate.
    doc = make(tmp_path)
    path = tmp_path / "frame_0001.png"
    picture = Image.new("RGB", (1080, 1920), (120, 118, 112))
    top = 0 if edge == "top" else 1920 - 100
    picture.paste((0, 0, 0), (0, top, width, top + 100))
    picture.save(path, compress_level=0)
    doc["original_frame_records"][0]["sha256"] = digest(path)
    (tmp_path / "episode-proof.json").write_text(json.dumps(doc))
    if rejected:
        with pytest.raises(ValueError, match="black void band"):
            verify(tmp_path, MANIFEST, SCRIPT)
    else:
        assert verify(tmp_path, MANIFEST, SCRIPT)["status"] == "PASS_NATIVE_ORIGINAL_SHARD"
