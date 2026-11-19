"""Print base64 JPEG stills from a finished mp4 at specific timestamps,
straight into stdout (captured in the CI job's own log) -- because this
project's sandbox cannot download GitHub Actions artifact ZIPs (the blob
-storage redirect target is blocked by egress policy). Used to compare an
assembled/captioned final video before vs after an editorial change, at
matching timestamps, rather than trusting QA pass/fail alone.
"""
from __future__ import annotations

import argparse
import base64
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--label", required=True, help="Tag printed with each frame, e.g. BEFORE or AFTER")
    parser.add_argument("--timestamps", type=float, nargs="+", required=True)
    parser.add_argument("--width", type=int, default=270)
    args = parser.parse_args()

    for t in args.timestamps:
        out = Path(f"/tmp/frame_{args.label}_{t:06.2f}.jpg")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(args.video),
             "-frames:v", "1", "-vf", f"scale={args.width}:-1", str(out)],
            check=True,
        )
        data = out.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        tag = f"{args.label}_{t:06.2f}"
        print(f"FRAME_B64_START {tag}", flush=True)
        print(encoded, flush=True)
        print(f"FRAME_B64_END {tag}", flush=True)


if __name__ == "__main__":
    main()
