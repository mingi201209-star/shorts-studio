"""Merge a from-scratch 90-frame driver pilot render into one sequence.

Unlike assemble_driver_pilot.py, this does NOT reuse the preserved partial
inventory from run 41416805484: that inventory was rendered with the old
motion math, and render_driver_insert.py's motion was intentionally changed
(continuous breathing + three blinks added inside the pre-notice,
inter-notice/turn, and post-turn holds, fixing the confirmed
boring-static-shot finding). Every frame here comes from the current
renderer, rendered in parallel shards on GitHub Actions standard runners.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble(shards: Path, out: Path, repo: Path) -> None:
    assert os.environ.get("GITHUB_ACTIONS") == "true", "GitHub-only asset assembly"
    renderer = repo / "benchmarks/road_safety/render_driver_insert.py"
    renderer_sha = digest(renderer)
    out.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, str] = {}
    poses = []
    for path in sorted(shards.rglob("driver-pilot.json")):
        proof = json.loads(path.read_text())
        assert proof["renderer_sha256"] == renderer_sha, "shard rendered by a different renderer version"
        assert (proof["samples"], proof["resolution"], proof["fps"]) == (32, [1080, 1920], 30)
        assert proof["is_final"] is False and proof["narration_alignment"] == "NOT_YET_APPLIED"
        assert proof["frame_count"] == len(proof["frame_numbers"])
        assert set(proof["png_sha256"]) == {f"{n:04d}.png" for n in proof["frame_numbers"]}
        for name, sha in proof["png_sha256"].items():
            assert name not in hashes, f"duplicated frame across shards: {name}"
            assert digest(path.parent / name) == sha
            shutil.copyfile(path.parent / name, out / name)
            hashes[name] = sha
        poses.extend(proof["poses"])
    assert set(hashes) == {f"{n:04d}.png" for n in range(1, 91)}, "missing frames"
    assert len(set(hashes.values())) == 90, "duplicate pixel content across frames"
    proof = {
        "status": "RENDERED_REVIEW_REQUIRED", "is_final": False, "silent": True,
        "narration_alignment": "NOT_YET_APPLIED", "human_review": "UNVERIFIED",
        "editorial_status": "REVIEW_REQUIRED", "samples": 32, "resolution": [1080, 1920],
        "fps": 30, "frame_count": 90, "renderer_sha256": renderer_sha,
        "renderer_change": "idle motion fix (breathing + 3 blinks) for confirmed static-hold finding",
        "png_sha256": hashes, "poses": sorted(poses, key=lambda p: p["frame"]),
    }
    (out / "driver-pilot.json").write_text(json.dumps(proof, indent=2) + "\n")
    print("DRIVER_PILOT_FRESH_MERGED 90 frames, single renderer generation")


def main():
    p = argparse.ArgumentParser()
    for name in ("shards", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    assemble(args.shards, args.out, Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    main()
