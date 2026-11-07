"""Diagnose-only: measure real visual_activity for the three road-paint
shots whose QA failed on run 42322407163, from a cheap cycles_samples=7
diagnose render, without waiting on a full 32-shard production run.
Delete alongside road-paint-motion-diagnose.yml once the fix is confirmed.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from shorts_studio.final_video_qa import measure_visual_activity, verify_visual_activity

SHOTS = {
    "night_wide": (1, 162),
    "bead_macro_ray": (290, 490),
    "bead_macro_closing": (801, 960),
}
FPS = 30


def main() -> None:
    native = Path(os.environ["RUNNER_TEMP"]) / "native"
    work = Path(os.environ["RUNNER_TEMP"]) / "clips"
    work.mkdir(parents=True, exist_ok=True)

    frame_paths = {}
    for p in native.rglob("frame_*.png"):
        n = int(p.stem.split("_")[1])
        frame_paths[n] = p

    for shot_id, (start, end) in SHOTS.items():
        clip_dir = work / shot_id
        clip_dir.mkdir(parents=True, exist_ok=True)
        for i, frame in enumerate(range(start, end + 1), start=1):
            dst = clip_dir / f"f_{i:04d}.png"
            if not dst.exists():
                os.symlink(frame_paths[frame].resolve(), dst)
        mp4 = work / f"{shot_id}.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-framerate", str(FPS),
            "-i", str(clip_dir / "f_%04d.png"),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            str(mp4),
        ], check=True)
        activity = measure_visual_activity(mp4, (0, 1400), work)
        verdict = verify_visual_activity(activity)
        duration = (end - start + 1) / FPS
        print(f"MOTION_DIAGNOSE {shot_id} duration={duration:.3f}s verdict={verdict['status']}")
        print(f"MOTION_DIAGNOSE {shot_id} evidence={activity}")


if __name__ == "__main__":
    main()
