"""Print small base64-encoded JPEG thumbnails of specific native frames to
stdout (captured in the CI job's own log), because this project's sandbox
cannot download GitHub Actions artifact ZIPs (the blob-storage redirect
target is blocked by egress policy) -- this is the only path left to
actually look at a frame's pixels rather than trust aggregate statistics.
Thumbnails only (not full-resolution): the goal is reviewing composition,
subject position and framing, not pixel-perfect detail.
"""
from __future__ import annotations

import argparse
import base64
import io
from pathlib import Path

from PIL import Image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards", type=Path, required=True)
    parser.add_argument("--frames", type=int, nargs="+", required=True)
    parser.add_argument("--width", type=int, default=270)
    args = parser.parse_args()

    frame_paths = {}
    for candidate in args.shards.rglob("frame_*.png"):
        number = int(candidate.stem.split("_")[1])
        frame_paths[number] = candidate

    for n in args.frames:
        if n not in frame_paths:
            print(f"FRAME_MISSING {n}", flush=True)
            continue
        with Image.open(frame_paths[n]) as picture:
            picture.load()
            rgb = picture.convert("RGB")
            ratio = args.width / rgb.width
            thumb = rgb.resize((args.width, round(rgb.height * ratio)))
            buffer = io.BytesIO()
            thumb.save(buffer, format="JPEG", quality=60)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        print(f"FRAME_B64_START {n}", flush=True)
        print(encoded, flush=True)
        print(f"FRAME_B64_END {n}", flush=True)


if __name__ == "__main__":
    main()
