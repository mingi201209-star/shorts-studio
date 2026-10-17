#!/usr/bin/env python3
"""Verify all chunk frame hashes and continuity before composing 3-second preview.

Never permit silent missing or duplicate frames. All filenames fixed to this 90-frame test.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct

parent = Path(os.environ["CHUNKS_INPUT_DIR"])
dest = Path(os.environ["FRAMES_MERGED_DIR"])
dest.mkdir(parents=True, exist_ok=True)
expected_files = {}
reports = []
for key, start, end in (("a", 1, 30), ("b", 31, 60), ("c", 61, 90)):
    frames_dir = parent / f"frames-{key}"
    report_file = parent / f"report-{key}" / f"report_{key}.json"
    if not report_file.is_file():
        raise FileNotFoundError(report_file)
    report = json.loads(report_file.read_text(encoding="utf8"))
    assert (report["chunk"], report["start"], report["end"], report["count"]) == (key, start, end, 30)
    assert (report["samples"], report["resolution_pct"]) == (8, 38)
    assert len(report["frames"]) == 30
    listed = sorted(p.name for p in frames_dir.glob("seq_*.png"))
    expected = [f"seq_{i:04d}.png" for i in range(start, end + 1)]
    assert listed == expected, f"{key}: missing, extra or misnamed frames"
    for entry in report["frames"]:
        i = int(entry["frame"])
        assert start <= i <= end
        filename = f"seq_{i:04d}.png"
        assert filename not in expected_files, f"duplicate frame {i}"
        f = frames_dir / filename
        assert f.stat().st_size == entry["bytes"]
        assert hashlib.sha256(f.read_bytes()).hexdigest() == entry["sha256"], filename
        with f.open("rb") as h:
            prefix = h.read(24)
        assert prefix[:8] == b"\x89PNG\r\n\x1a\n", filename
        width, height = struct.unpack(">II", prefix[16:24])
        assert (width, height) == (410, 729), (filename, width, height)
        expected_files[filename] = f
    reports.append(report)

assert len(expected_files) == 90
ordered = [f"seq_{i:04d}.png" for i in range(1, 91)]
assert sorted(expected_files) == ordered, "frame continuity violation"
for name in ordered:
    shutil.copy2(expected_files[name], dest / name)

elapsed = [r["chunk_elapsed_seconds"] for r in reports]
seconds = [r["render_seconds"] for r in reports]
summary = {
    "status": "TECHNICAL_BENCHMARK_ONLY_NOT_UPLOAD_READY",
    "frames": 90, "duration_seconds": 3, "fps": 30,
    "samples": 8, "resolution": "410x729 native, 38% of 1080x1920",
    "chunk_render_seconds": {r["chunk"]: r["render_seconds"] for r in reports},
    "chunk_elapsed_seconds": {r["chunk"]: r["chunk_elapsed_seconds"] for r in reports},
    "sum_chunk_render_seconds": round(sum(seconds), 3),
    "max_chunk_elapsed_seconds": round(max(elapsed), 3),
    "theoretical_render_only_speedup": round(sum(seconds)/max(elapsed), 3),
    "limitation": "Rendered in 3 concurrent workers; setup, scheduling, and upload/download overhead excluded from timing ratio; image is a conceptual unvalidated crash representation.",
}
(dest.parent / "parallel_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
print("PARALLEL_VERIFY_PASS", json.dumps(summary), flush=True)
