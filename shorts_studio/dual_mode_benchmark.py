"""Checkpointed orchestration; no quality claims independent of the runner."""

from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def benchmark(args, runner):
    started = time.monotonic()
    phases = args.receipt.with_suffix(".phases")
    ffmpeg = Path(shutil.which("ffmpeg"))
    ffprobe = Path(shutil.which("ffprobe"))
    binding = {
        "library": str(args.library.resolve()),
        "cache": str(args.cache.resolve()),
        "frames": args.frames,
        "runtime": runner.runtime(args.blender.resolve(), ffmpeg, ffprobe),
        "benchmark_source_sha256": runner.sha(Path(__file__)),
    }
    if phases.exists():
        if not args.resume:
            raise ValueError("existing benchmark checkpoints; inspect them and use --resume")
        if json.loads((phases / "manifest.json").read_text()) != binding:
            raise ValueError("benchmark inputs changed; retained checkpoints cannot be relabeled")
    else:
        if args.resume:
            raise ValueError("no benchmark checkpoints to resume")
        if args.cache.exists() and any(args.cache.iterdir()):
            raise ValueError("cold benchmark requires a fresh cache")
        phases.mkdir(parents=True)
        write_json(phases / "manifest.json", binding)
    records = {}
    stages = [
        ("premium_cold", "premium", "rolling"),
        ("fast_same_scene", "fast", "rolling"),
        ("fast_new_scene", "fast", "locked"),
    ]
    try:
        for name, mode, motion in stages:
            checkpoint = phases / (name + ".json")
            if checkpoint.exists():
                record = json.loads(checkpoint.read_text())
                root = Path(record["clip_path"]).parent
                if not root.resolve().is_relative_to((args.cache / "scenes").resolve()):
                    raise ValueError("checkpoint points outside scene cache")
                runner.validate_cached(root, record["key"], str(ffmpeg), str(ffprobe))
                if runner.sha(root / "clip.mp4") != record["clip_sha256"]:
                    raise ValueError("checkpoint video changed")
            else:
                if name == "premium_cold" and args.cache.exists() and any(args.cache.iterdir()):
                    raise ValueError(
                        "incomplete cold measurement; retain evidence and use a new experiment"
                    )
                write_json(phases / "status.json", {"state": "running", "phase": name})
                record = runner.run(
                    mode, motion, args.library, args.cache, args.blender, args.frames
                )
                write_json(checkpoint, record)
            if record["mode"] != mode or record["motion"] != motion:
                raise ValueError("checkpoint stage identity differs")
            if not math.isfinite(record["wall_seconds"]) or record["wall_seconds"] <= 0:
                raise ValueError("invalid benchmark timing")
            records[name] = record
        cold, hot, variant = (records[name] for name, _, _ in stages)
        if not cold["asset_built"] or cold["visual_cache_hit"]:
            raise ValueError("cold result was not an actual cold build")
        if not hot["visual_cache_hit"] or hot["asset_built"]:
            raise ValueError("same-scene Fast result was not verified reuse")
        if variant["asset_built"] or variant["visual_cache_hit"]:
            raise ValueError(
                "new-scene Fast result must reuse the model and render new native frames"
            )
        if not cold["asset_id"] == hot["asset_id"] == variant["asset_id"]:
            raise ValueError("benchmark compared different model assets")
        if cold["clip_sha256"] != hot["clip_sha256"]:
            raise ValueError("same-scene reuse changed the video")
    except BaseException as error:
        write_json(phases / "status.json", {"state": "stopped", "reason": str(error)})
        raise
    write_json(phases / "status.json", {"state": "complete"})
    return {
        **records,
        "same_scene_bit_identical": True,
        "same_scene_speed_ratio": cold["wall_seconds"] / hot["wall_seconds"],
        "control_wall_seconds_this_invocation": time.monotonic() - started,
        "frames_per_scene": args.frames,
        "fps": 30,
        "note": "Cached clip reuse is not new-scene rendering speed. Kinematic proof, not final Short.",
    }
