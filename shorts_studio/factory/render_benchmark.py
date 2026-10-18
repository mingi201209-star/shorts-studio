"""Reproducible A/B/A Blender performance benchmark for the road-safety pilot.

No quality setting changes: both variants have identical camera, geometry,
resolution, samples and seed. Persistent data affects Blender caching only.
This script never marks an unfinished/native-untested video as upload-ready.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import time
from pathlib import Path

from PIL import Image, ImageChops


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def compare_frames(left: Path, right: Path) -> dict:
    a_files = sorted(left.glob("frame_*.png"))
    b_files = sorted(right.glob("frame_*.png"))
    if not a_files or len(a_files) != len(b_files):
        raise ValueError("missing or unequal frame counts")
    different = 0
    max_diff = 0
    for a, b in zip(a_files, b_files):
        with Image.open(a) as img_a, Image.open(b) as img_b:
            if img_a.size != img_b.size or img_a.mode != img_b.mode:
                raise ValueError("frame format mismatch")
            diff = ImageChops.difference(img_a, img_b)
            if diff.getbbox() is not None:
                different += 1
                max_diff = max(max_diff, *(v[1] for v in diff.getextrema()))
    return {"frames_compared": len(a_files), "different_frames": different,
            "max_channel_difference": max_diff, "pixel_exact": different == 0}


def run(blender: str, root: Path, output: Path, profile: str, mode: str, frames: int) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    args = [blender, "-b", "-noaudio", "-t", "4",
            "-P", str(root / "shorts_studio/factory/rumble_surface.py"),
            "--", "--manifest", str(root / "examples/factory/rumble-strips.json"),
            "--shot", "tire-contacts-grooves", "--out", str(output),
            "--frames", str(frames)]
    if profile == "persistent":
        args.append("--persistent-data")
    if mode == "preview":
        args.append("--preview")
    start = time.perf_counter()
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, check=False, timeout=540)
    wall_s = time.perf_counter() - start
    (output / "render.log").write_text(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"{profile} exited {proc.returncode}: {proc.stdout[-2500:]}")
    manifest = json.loads((output / "motion-metadata.json").read_text())
    if manifest["actual_frames"] != frames:
        raise RuntimeError("wrong frame count")
    if manifest["persistent_data"] != (profile == "persistent"):
        raise RuntimeError("wrong benchmark profile")
    if manifest["samples"] != (6 if mode == "preview" else 32):
        raise RuntimeError("sample count changed")
    frame_paths = sorted(output.glob("frame_*.png"))
    if len(frame_paths) != frames or len({sha256(p) for p in frame_paths}) != frames:
        raise RuntimeError("frame duplication/missing frame detected")
    return {"profile": profile, "wall_seconds": round(wall_s, 3),
            "render_seconds": manifest["render_seconds_per_frame"],
            "steady_median_seconds": round(statistics.median(
                manifest["render_seconds_per_frame"][1:]), 3),
            "total_frame_seconds": round(sum(manifest["render_seconds_per_frame"]), 3),
            "output_bytes": sum(p.stat().st_size for p in frame_paths),
            "files_sha256": [sha256(p) for p in frame_paths]}


def execute(root: Path, destination: Path, blender: str, mode: str, frames: int) -> dict:
    if destination.exists():
        raise FileExistsError(f"benchmark output already exists: {destination}")
    destination.mkdir(parents=True)
    trial_profiles = ("baseline_1", "persistent", "baseline_2")
    outputs = {}
    for name in trial_profiles:
        profile = "persistent" if name == "persistent" else "baseline"
        out = destination / name
        print(f"START {mode} {name}", flush=True)
        outputs[name] = run(blender, root, out, profile, mode, frames)
        print(f"FINISHED {name} {outputs[name]['wall_seconds']}s", flush=True)
    first = compare_frames(destination / "baseline_1", destination / "persistent")
    second = compare_frames(destination / "baseline_2", destination / "persistent")
    baseline = statistics.median([outputs["baseline_1"]["steady_median_seconds"],
                                  outputs["baseline_2"]["steady_median_seconds"]])
    optimized = outputs["persistent"]["steady_median_seconds"]
    speedup = baseline / optimized if optimized else 0
    exact = first["pixel_exact"] and second["pixel_exact"]
    result = {
        "mode": mode, "frames_per_trial": frames, "trials": outputs,
        "comparison_1": first, "comparison_2": second,
        "speedup_x": round(speedup, 3),
        "decision": "candidate_only" if exact and speedup >= 1.15 else "reject_or_inconclusive",
        "production_claim": False,
        "reason": "Only native-resolution quality and stability tests can authorize a change",
    }
    (destination / "benchmark.json").write_text(json.dumps(result, indent=2))
    print("BENCHMARK_COMPLETE " + json.dumps(
        {"mode": mode, "frames": frames, "speedup_x": round(speedup, 3),
         "pixel_exact": exact, "decision": result["decision"]}), flush=True)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--blender", default="blender")
    p.add_argument("--mode", choices=("preview", "native"), default="preview")
    p.add_argument("--frames", type=int, default=4)
    args = p.parse_args()
    if args.frames < 2 or args.frames > 15:
        p.error("benchmarks must use 2-15 distinct frames")
    result = execute(args.repo.resolve(), args.out, args.blender, args.mode, args.frames)
    if not result["comparison_1"]["pixel_exact"] or not result["comparison_2"]["pixel_exact"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
