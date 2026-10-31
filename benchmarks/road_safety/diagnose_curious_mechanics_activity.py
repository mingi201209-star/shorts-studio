"""Diagnose whether the visual_activity FAIL on PR #92 (max_static_visual_seconds
10.0s between output timestamps 15.5s-25.5s, native frames 466-766, entirely
inside the 'rumble_mechanism' progressive long take, frames 461-767) is real
on-screen staticness, below-threshold-but-real motion, or a detector bug.

Note on the earlier (wrong) report: cut_timestamps [0.0, 4.5, 10.5, 15.5,
25.5] with final edge 30.0 gives holds [4.5, 6.0, 5.0, 10.0, 4.5] -- the
10.0s max hold is the 15.5-25.5 interval, NOT 4.5-15.5 as first (and
incorrectly) reported. This script targets the correct window.

Unlike the real gate (which measures the h264-encoded, 2fps-subsampled final
MP4), this operates on the native, lossless, un-subsampled per-frame PNGs
already rendered and QA-passed for those shards -- so it answers "is there
real pixel motion frame-to-frame" independent of any compression or temporal
-subsampling artifact in the measurement pipeline itself.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import numpy as np
from PIL import Image

MEDIA_BOX = (0, 1400)  # matches final_video_qa's picture box: (0, CAPTION_GUTTER_TOP)


def load_media(path: Path) -> np.ndarray:
    with Image.open(path) as picture:
        picture.load()
        array = np.asarray(picture.convert("RGB"), dtype=int)
    top, bottom = MEDIA_BOX
    return array[top:bottom, :, :]


def center_crop(array: np.ndarray, fraction: float = 0.4) -> np.ndarray:
    height, width = array.shape[:2]
    half_h, half_w = int(height * fraction / 2), int(width * fraction / 2)
    cy, cx = height // 2, width // 2
    return array[cy - half_h:cy + half_h, cx - half_w:cx + half_w, :]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards", type=Path, required=True,
                         help="Directory containing downloaded shard folders, each with frame_XXXX.png files")
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frame_paths = {}
    for candidate in args.shards.rglob("frame_*.png"):
        number = int(candidate.stem.split("_")[1])
        frame_paths[number] = candidate
    missing = [n for n in range(args.start, args.end + 1) if n not in frame_paths]
    present = [n for n in range(args.start, args.end + 1) if n in frame_paths]
    if len(present) < 2:
        raise SystemExit(f"not enough frames present in range to diagnose: {len(present)} found, {len(missing)} missing")

    pairs = []
    previous_full, previous_center, previous_n = None, None, None
    for n in present:
        media = load_media(frame_paths[n])
        center = center_crop(media)
        if previous_full is not None and n == previous_n + 1:
            full_diff = float(np.abs(media.astype(int) - previous_full.astype(int)).mean())
            center_diff = float(np.abs(center.astype(int) - previous_center.astype(int)).mean())
            pairs.append({"frame": n, "prev_frame": previous_n,
                          "full_frame_mean_abs_diff": round(full_diff, 4),
                          "center_crop_mean_abs_diff": round(center_diff, 4)})
        previous_full, previous_center, previous_n = media, center, n

    full_diffs = [p["full_frame_mean_abs_diff"] for p in pairs]
    center_diffs = [p["center_crop_mean_abs_diff"] for p in pairs]
    gate_threshold = 12.0
    report = {
        "requested_range": [args.start, args.end],
        "frames_present": len(present),
        "frames_missing": missing,
        "consecutive_pairs_measured": len(pairs),
        "full_frame": {
            "min": round(min(full_diffs), 4) if full_diffs else None,
            "max": round(max(full_diffs), 4) if full_diffs else None,
            "mean": round(statistics.mean(full_diffs), 4) if full_diffs else None,
            "median": round(statistics.median(full_diffs), 4) if full_diffs else None,
            "pairs_above_gate_threshold_12": sum(1 for d in full_diffs if d >= gate_threshold),
            "pairs_above_1": sum(1 for d in full_diffs if d >= 1.0),
            "pairs_above_3": sum(1 for d in full_diffs if d >= 3.0),
            "pairs_above_6": sum(1 for d in full_diffs if d >= 6.0),
        },
        "center_crop_40pct": {
            "min": round(min(center_diffs), 4) if center_diffs else None,
            "max": round(max(center_diffs), 4) if center_diffs else None,
            "mean": round(statistics.mean(center_diffs), 4) if center_diffs else None,
            "median": round(statistics.median(center_diffs), 4) if center_diffs else None,
            "pairs_above_gate_threshold_12": sum(1 for d in center_diffs if d >= gate_threshold),
            "pairs_above_1": sum(1 for d in center_diffs if d >= 1.0),
            "pairs_above_3": sum(1 for d in center_diffs if d >= 3.0),
            "pairs_above_6": sum(1 for d in center_diffs if d >= 6.0),
        },
        "pairs": pairs,
    }
    (args.out / "activity_diagnosis.json").write_text(json.dumps(report, indent=2))
    print("ACTIVITY_DIAGNOSIS_SUMMARY", json.dumps({k: v for k, v in report.items() if k != "pairs"}, indent=2), flush=True)

    # Save a handful of actual frames (start/quarter/mid/three-quarter/end of
    # the measured range) for a human to look at directly -- numbers alone
    # should not be the only evidence for an editorial call.
    if present:
        picks = sorted({present[0], present[len(present)//4], present[len(present)//2],
                        present[3*len(present)//4], present[-1]})
        for n in picks:
            with Image.open(frame_paths[n]) as picture:
                picture.convert("RGB").crop((0, 0, 1080, 1400)).save(args.out / f"sample_frame_{n:04d}.jpg", quality=90)
        print("SAMPLE_FRAMES", picks, flush=True)


if __name__ == "__main__":
    main()
