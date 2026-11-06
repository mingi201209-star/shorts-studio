"""Reuse the preserved 37 frames and merge only the 53 newly rendered frames."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def motion_body(source):
    main = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    loop = next(n for n in main.body if isinstance(n, ast.For)
                and isinstance(n.target, ast.Name) and n.target.id == "frame")
    return ast.dump(ast.Module(body=loop.body, type_ignores=[]), include_attributes=False)


def assemble(preserved, shards, out, repo):
    assert os.environ.get("GITHUB_ACTIONS") == "true", "GitHub-only asset assembly"
    inventory_path = repo / "examples/experiments/curious-driver-pilot-preserved-41416805484.json"
    inventory = json.loads(inventory_path.read_text())
    old_renderer = repo / "benchmarks/road_safety/renderer_snapshots/render_driver_insert_055db61.py"
    renderer = repo / "benchmarks/road_safety/render_driver_insert.py"
    assert digest(old_renderer) == inventory["renderer_sha256"]
    old, new = old_renderer.read_text(), renderer.read_text()
    a, b = "    bpy.ops.object.select_all", "    poses = []"
    assert old[old.index(a):old.index(b)] == new[new.index(a):new.index(b)]
    assert motion_body(old) == motion_body(new), "scene or motion changed; cannot reuse"
    assert digest(next(preserved.rglob("driver-render.log"))) == inventory["render_log_sha256"]
    out.mkdir(parents=True, exist_ok=False)
    hashes, generations, poses = {}, {}, []
    for name, sha in inventory["png_sha256"].items():
        candidates = list(preserved.rglob(name))
        assert len(candidates) == 1 and digest(candidates[0]) == sha
        shutil.copyfile(candidates[0], out / name)
        hashes[name], generations[name] = sha, digest(old_renderer)
    source_receipts = []
    for path in sorted(shards.rglob("driver-pilot.json")):
        proof = json.loads(path.read_text())
        assert proof["renderer_sha256"] == digest(renderer)
        assert (proof["samples"], proof["resolution"], proof["fps"]) == (32, [1080, 1920], 30)
        assert proof["frame_count"] == len(proof["frame_numbers"])
        assert set(proof["png_sha256"]) == {f"{n:04d}.png" for n in proof["frame_numbers"]}
        for name, sha in proof["png_sha256"].items():
            assert name not in hashes, "duplicated frame; preserved frames must not be rerendered"
            assert digest(path.parent / name) == sha
            shutil.copyfile(path.parent / name, out / name)
            hashes[name], generations[name] = sha, digest(renderer)
        poses.extend(proof["poses"])
        source_receipts.append({"sha256": digest(path), "frames": proof["frame_numbers"]})
    assert set(hashes) == {f"{n:04d}.png" for n in range(1, 91)}
    assert len(set(hashes.values())) == 90
    proof = {
        "status": "RENDERED_REVIEW_REQUIRED", "is_final": False, "silent": True,
        "narration_alignment": "NOT_YET_APPLIED", "human_review": "UNVERIFIED",
        "editorial_status": "REVIEW_REQUIRED", "samples": 32, "resolution": [1080, 1920],
        "fps": 30, "frame_count": 90, "renderer_sha256": digest(renderer),
        "renderer_reference_scope": "current range-capable renderer; per-frame generations below",
        "generation_by_frame": generations, "png_sha256": hashes,
        "preserved_inventory_sha256": digest(inventory_path),
        "preserved_frame_count": 37, "new_frame_count": 53,
        "source_receipts": source_receipts,
        "poses_for_new_frames": poses,
    }
    (out / "driver-pilot.json").write_text(json.dumps(proof, indent=2) + "\n")
    print("DRIVER_PILOT_MERGED 37 reused + 53 new; review required")


def main():
    p = argparse.ArgumentParser()
    for name in ("preserved", "shards", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    assemble(args.preserved, args.shards, args.out, Path(__file__).resolve().parents[2])


if __name__ == "__main__":
    main()
