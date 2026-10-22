"""Technical QA for newly rendered 1080p Cycles32 episode2 shards. Not publish approval."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

from .rumble_episode2 import PINNED_ASSET, load_episode, shot_for_frame, travel_x


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


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
        if proof.get(key) != value:
            raise ValueError(f"native shard contract failed: {key}")
    if proof.get("car_mesh_parts",0) < 65:
        raise ValueError("missing detailed car geometry")
    records = proof.get("original_frame_records",[])
    nums = proof.get("frame_numbers",[])
    if not records or len(records)>30 or nums != [r["frame"] for r in records]:
        raise ValueError("missing or invalid original frame numbering")
    if nums != list(range(nums[0],nums[-1]+1)):
        raise ValueError("noncontiguous original frames")
    if (len(nums)!=proof["frames"] or nums[0]!=proof["first_frame"]
            or nums[-1]!=proof["last_frame"]):
        raise ValueError("frame proof inconsistent")
    expected_files = [f"frame_{n:04d}.png" for n in nums]
    if sorted(p.name for p in out.glob("frame_*.png"))!=expected_files:
        raise ValueError("missing/extra original image")
    old = None
    for frame, record in zip(nums,records):
        if record["shot_id"] != shot_for_frame(episode,frame)["id"]:
            raise ValueError("wrong story beat frame")
        if abs(record["absolute_x_m"] - travel_x(frame)) > 0.000001:
            raise ValueError("global position changed on shard boundary")
        path = out / f"frame_{frame:04d}.png"
        if not path.exists() or path.stat().st_size < 10000:
            raise ValueError("no complete real image")
        if digest(path)!=record["sha256"]:
            raise ValueError("native source image hash mismatch")
        with Image.open(path) as picture:
            picture.load()
            if picture.size!=(1080,1920) or picture.mode!="RGB":
                raise ValueError("fake scaled/downsampled frame")
            current=picture.copy()
        if old is not None and ImageChops.difference(old,current).getbbox() is None:
            raise ValueError("frame cloning instead of actual 3D motion")
        old=current
    if set(proof.get("camera_by_shot",{})) != {
        shot_for_frame(episode,n)["id"] for n in nums
    }:
        raise ValueError("missing fixed shot camera evidence")
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
