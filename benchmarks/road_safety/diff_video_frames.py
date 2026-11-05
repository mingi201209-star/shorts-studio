"""Print a per-frame pixel-difference summary against frame 1, to rigorously
check whether a video is actually static rather than relying on a handful of
time-seeked stills (which can be misled by keyframe-seek behavior)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def extract_all_frames(video: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), str(out_dir / "f_%04d.png")],
        check=True,
    )
    return sorted(out_dir.glob("f_*.png"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    frames = extract_all_frames(args.video, args.out)
    if not frames:
        print("NO_FRAMES_EXTRACTED", file=sys.stderr)
        sys.exit(1)
    with Image.open(frames[0]) as im0:
        base = im0.convert("RGB").copy()
    print(f"FRAME_DIFF_TOTAL {len(frames)}", flush=True)
    for idx, path in enumerate(frames, start=1):
        with Image.open(path) as im:
            cur = im.convert("RGB")
            diff = ImageChops.difference(base, cur)
            stat = ImageStat.Stat(diff)
            mean_diff = sum(stat.mean) / len(stat.mean)
            max_diff = max(stat.extrema[c][1] for c in range(len(stat.extrema)))
        print(f"FRAME_DIFF {idx:04d} mean={mean_diff:.4f} max={max_diff}", flush=True)


if __name__ == "__main__":
    main()
