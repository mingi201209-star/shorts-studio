"""Fail-closed render-farm output integrity check, for a test-only preview."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def verify_folder(folder: Path, shard: int, pinned_script_sha: str):
    proof=json.loads((folder/"proof.json").read_text(encoding="utf8"))
    if (proof.get("schema_version")!=1 or proof.get("shard")!=shard or
        proof.get("renderer_sha256")!=pinned_script_sha or
        proof.get("resolution")!=[320,576] or proof.get("samples")!=6 or
        proof.get("fps")!=30 or proof.get("upload_ready") is not False or
        proof.get("native_unique_frames") is not True):
        raise ValueError("source identity or render quality contract mismatch")
    frames=proof.get("frames")
    if not isinstance(frames,list) or len(frames)!=3:
        raise ValueError("wrong frame count")
    all_found=sorted(folder.glob("frame_*.png"))
    expect=[folder/f"frame_{index:04d}.png" for index in range(1+shard*3,4+shard*3)]
    if all_found!=expect:
        raise ValueError("missing/duplicate/extra native frame")
    hashes=[]
    for row,path in zip(frames, expect):
        idx=int(path.stem.split("_")[1])
        payload=path.read_bytes()
        checksum=hashlib.sha256(payload).hexdigest()
        if (row.get("frame")!=idx or row.get("sha256")!=checksum or
            not payload.startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("frame checksum/header mismatch")
        hashes.append(checksum)
    if len(set(hashes))!=len(hashes):
        raise ValueError("duplicate visual frames")
    return {"shard":shard,"frame_count":3,"renderer_sha256":pinned_script_sha,
            "frames":hashes,"production_approved":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",type=Path,required=True)
    parser.add_argument("--shard",type=int,required=True)
    parser.add_argument("--script",type=Path,required=True)
    args=parser.parse_args()
    expected=hashlib.sha256(args.script.read_bytes()).hexdigest()
    print(json.dumps(verify_folder(args.folder,args.shard,expected),indent=2))

if __name__=="__main__":
    main()
