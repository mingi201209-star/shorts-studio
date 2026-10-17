#!/usr/bin/env python3
"""Isolated GitHub-hosted parallel CPU benchmark: fixed-size contiguous frame chunk.

Only for 3-second concept lookdev. This DOES NOT certify visual/physical accuracy.
"""
import bpy
import hashlib
import json
import os
import time
from pathlib import Path

start = int(os.environ["CHUNK_START"])
end = int(os.environ["CHUNK_END"])
name = os.environ["CHUNK_NAME"]
directory = Path(os.environ["BLENDER_BENCH_OUT"])
directory.mkdir(parents=True, exist_ok=True)

if (start, end, name) not in ((1, 30, "a"), (31, 60, "b"), (61, 90, "c")):
    raise SystemExit("Out-of-scope chunk assignment")
if any(directory.glob("seq_*.png")):
    raise RuntimeError("Output directory is not empty; avoid stale or duplicate frames")

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 8
scene.cycles.use_denoising = True
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 38
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.threads_mode = "FIXED"
scene.render.threads = 4

report = {
    "chunk": name, "start": start, "end": end,
    "blender_version": bpy.app.version_string,
    "samples": 8, "resolution_pct": 38,
    "frames": [],
}
started = time.perf_counter()
for frame in range(start, end + 1):
    scene.frame_set(frame)
    file = directory / f"seq_{frame:04d}.png"
    scene.render.filepath = str(file)
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    elapsed = time.perf_counter() - t
    if not file.is_file() or file.stat().st_size < 10000:
        raise RuntimeError(f"Missing/undersized rendered frame: {frame}")
    report["frames"].append({
        "frame": frame,
        "seconds": round(elapsed, 3),
        "bytes": file.stat().st_size,
        "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
    })
    print(f"BENCH_FRAME chunk={name} frame={frame} seconds={elapsed:.3f}", flush=True)
report["count"] = len(report["frames"])
report["render_seconds"] = round(sum(r["seconds"] for r in report["frames"]), 3)
report["chunk_elapsed_seconds"] = round(time.perf_counter() - started, 3)
assert report["count"] == 30
(directory / f"report_{name}.json").write_text(json.dumps(report, indent=2), encoding="utf8")
print("BENCH_CHUNK_COMPLETE", json.dumps({
    "chunk": name,
    "count": report["count"],
    "render_seconds": report["render_seconds"],
    "elapsed_seconds": report["chunk_elapsed_seconds"],
}), flush=True)
