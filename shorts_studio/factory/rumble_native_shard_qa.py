"""Technical QA for newly rendered 1080p Cycles32 episode2 shards. Not publish approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from .rumble_episode2 import PINNED_ASSET, load_episode, shot_for_frame, travel_x

NEAR_TYRES = ("Front_tire", "Rear_tire")
# Metres relative to the flat road land (z=0); grooves are cut 16 mm below it.
TYRE_CONTACT_Z = (-0.001, 0.004)


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def finite_number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def valid_camera(camera) -> bool:
    if not isinstance(camera, list) or len(camera) != 3:
        return False
    location, rotation, scale = camera
    return (
        all(isinstance(vector, list) and len(vector) == 3
            and all(finite_number(value) for value in vector)
            for vector in (location, rotation))
        and finite_number(scale) and scale > 0
    )


def visual_content_checks(path: Path, previous: Image.Image | None, *,
                          expected_size: tuple[int, int] = (1080, 1920)) -> Image.Image:
    """Pure pixel-content checks, independent of any production-contract
    metadata (sample count, renderer identity, etc.): a real single-frame
    RGB PNG at the expected size, not a blank/near-black frame, no black
    -void band at a frame edge (an orthographic camera plane below road
    grade), and not an exact clone of `previous`. Used by verify()'s full
    production contract and standalone by experiments that deliberately
    render at a non-production setting (e.g. a reduced sample count) and
    still want a real answer to "is the picture itself broken", separate
    from "does it match the approved manifest exactly"."""
    with Image.open(path) as picture:
        if picture.format != "PNG" or getattr(picture, "n_frames", 1) != 1:
            raise ValueError("native source must be a single PNG image")
        picture.load()
        if picture.size != expected_size or picture.mode != "RGB":
            raise ValueError("fake scaled/downsampled frame")
        current = picture.copy()
    if sum(ImageStat.Stat(current.resize((30, 50))).mean) < 25:
        raise ValueError(f"black or empty visual: {path.name}")
    width, height = current.size
    for top in (0, height - 40):
        band = current.crop((0, top, width, top + 40)).resize((54, 2))
        if all(high < 8 for _, high in band.getextrema()):
            raise ValueError(f"black void band at frame edge: {path.name}")
    if previous is not None and ImageChops.difference(previous, current).getbbox() is None:
        raise ValueError("frame cloning instead of actual 3D motion")
    return current


def verify(out: Path, manifest: Path, renderer: Path) -> dict:
    episode = load_episode(manifest)
    proof = json.loads((out/"episode-proof.json").read_text())
    requirements = {
        "episode_id": episode["episode_id"], "source_sha256":PINNED_ASSET,
        "renderer_source_sha256":digest(renderer), "renderer":"CYCLES",
        "preview_only":False,"resolution":[1080,1920],"cycles_samples":32,
        "fps":30,"rotating_wheel_pivots":4,
        "physically_calibrated":False,"upload_ready":False,
    }
    for key, value in requirements.items():
        if type(proof.get(key)) is not type(value) or proof.get(key) != value:
            raise ValueError(f"native shard contract failed: {key}")
    if any(type(dimension) is not int for dimension in proof["resolution"]):
        raise ValueError("native shard contract failed: resolution")
    parts = proof.get("car_mesh_parts")
    if type(parts) is not int or parts < 65:
        raise ValueError("missing detailed car geometry")
    records = proof.get("original_frame_records",[])
    nums = proof.get("frame_numbers",[])
    if (not isinstance(records, list) or not records or len(records) > 30
            or not isinstance(nums, list) or not nums
            or any(type(n) is not int or not 1 <= n <= episode["total_frames"] for n in nums)
            or any(not isinstance(record, dict) or type(record.get("frame")) is not int
                   for record in records)
            or any(type(proof.get(key)) is not int
                   for key in ("frames", "first_frame", "last_frame"))
            or nums != [r["frame"] for r in records]):
        raise ValueError("missing or invalid original frame numbering")
    if nums != list(range(nums[0],nums[-1]+1)):
        raise ValueError("noncontiguous original frames")
    if (len(nums)!=proof["frames"] or nums[0]!=proof["first_frame"]
            or nums[-1]!=proof["last_frame"]):
        raise ValueError("frame proof inconsistent")
    times = proof.get("render_seconds")
    if (not isinstance(times, list) or len(times) != len(records)
            or any(not finite_number(value) or value <= 0 for value in times)):
        raise ValueError("missing or invalid render time evidence")
    for record, elapsed in zip(records, times):
        recorded = record.get("render_seconds")
        if not finite_number(recorded) or recorded != elapsed:
            raise ValueError("inconsistent per-frame render time evidence")
    expected_files = [f"frame_{n:04d}.png" for n in nums]
    if sorted(p.name for p in out.glob("frame_*.png"))!=expected_files:
        raise ValueError("missing/extra original image")
    old = None
    decoded_hashes = set()
    for frame, record in zip(nums,records):
        if record["shot_id"] != shot_for_frame(episode,frame)["id"]:
            raise ValueError("wrong story beat frame")
        position = record.get("absolute_x_m")
        if not finite_number(position) or abs(position - travel_x(frame)) > 0.000001:
            raise ValueError("global position changed on shard boundary")
        # Near-side tyres must sit on the flat land between milled grooves:
        # no visible floating gap and no sinking through the road surface.
        contact = record.get("near_tyre_min_z_m")
        if (not isinstance(contact, dict) or set(contact) != set(NEAR_TYRES)
                or not all(finite_number(z) and TYRE_CONTACT_Z[0] <= z <= TYRE_CONTACT_Z[1]
                           for z in contact.values())):
            raise ValueError(f"missing, floating or penetrating tyre contact: frame {frame}")
        path = out / f"frame_{frame:04d}.png"
        if not path.exists() or path.stat().st_size < 10000:
            raise ValueError("no complete real image")
        if digest(path)!=record["sha256"]:
            raise ValueError("native source image hash mismatch")
        current = visual_content_checks(path, old)
        decoded_sha = hashlib.sha256(current.tobytes()).hexdigest()
        if decoded_sha in decoded_hashes:
            raise ValueError("frame cloning instead of actual 3D motion")
        decoded_hashes.add(decoded_sha)
        old=current
    cameras = proof.get("camera_by_shot", {})
    if not isinstance(cameras, dict) or set(cameras) != {
        shot_for_frame(episode,n)["id"] for n in nums
    }:
        raise ValueError("missing fixed shot camera evidence")
    if not all(valid_camera(camera) for camera in cameras.values()):
        raise ValueError("invalid fixed shot camera evidence")
    return {"status":"PASS_NATIVE_ORIGINAL_SHARD","frames":len(nums),
            "source_sha256":PINNED_ASSET, "pixel_size":[1080,1920],
            "samples":32, "upload_authorized":False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--renderer",type=Path,required=True)
    args=parser.parse_args()
    print("ORIGINAL_CYCLES32_RUMBLE_PASS",
          json.dumps(verify(args.out,args.manifest,args.renderer)),flush=True)


if __name__=="__main__":
    main()
