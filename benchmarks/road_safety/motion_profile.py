"""Motion profile of a finished video: how much the picture keeps moving.

Used to compare our films with a reference clip on equal terms. Three numbers:

* median / mean absolute difference between consecutive frames (15 fps sample)
* share of consecutive-frame pairs that are almost still (difference < 4) or move a lot (> 25)
* "registered beats": the shared visual_activity rule (2 fps, a frame counts when it differs from the last
  registered frame by >= 12) -- how many there are and the longest stretch without one

The picture area is cropped so a phone's status bar, side buttons, caption text and navigation bar do not count.
This measures how much pixels change. It does not say whether the motion is meaningful, and a screen recording
of a streamed video carries re-encoding noise, so a reference measured from one is an upper bound on its motion.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

SAMPLE_FPS = 15
BEAT_FPS = 2.0
BEAT_THRESHOLD = 12.0


def diff_series(frames: list[np.ndarray]) -> np.ndarray:
    """Mean absolute difference between consecutive grayscale frames."""
    return np.array([float(np.abs(b - a).mean()) for a, b in zip(frames, frames[1:])])


def summarize(d: np.ndarray) -> dict:
    return {"pairs": int(len(d)), "mean": round(float(d.mean()), 2), "median": round(float(np.median(d)), 2),
            "p10": round(float(np.percentile(d, 10)), 2), "p90": round(float(np.percentile(d, 90)), 2),
            "share_over_12": round(float((d > 12).mean()), 3), "share_over_25": round(float((d > 25).mean()), 3),
            "share_under_4": round(float((d < 4).mean()), 3)}


def registered_beats(frames: list[np.ndarray], fps: float = BEAT_FPS, threshold: float = BEAT_THRESHOLD) -> dict:
    """The shared visual_activity rule on already-sampled frames (one per 1/fps seconds)."""
    ref, last = frames[0], 0.0
    beats, longest = [0.0], 0.0
    for i, f in enumerate(frames[1:], 1):
        t = i / fps
        if float(np.abs(f - ref).mean()) >= threshold:
            longest = max(longest, t - last)
            beats.append(t)
            ref, last = f, t
    longest = max(longest, len(frames) / fps - last)
    seconds = len(frames) / fps
    return {"beats": len(beats), "seconds": round(seconds, 1), "seconds_per_beat": round(seconds / len(beats), 2),
            "longest_without_beat_s": round(longest, 2)}


def resample(frames: list[np.ndarray], src_fps: float, dst_fps: float) -> list[np.ndarray]:
    step = src_fps / dst_fps
    return [frames[int(round(i * step))] for i in range(int(len(frames) / step))]


def extract_frames(video: Path, crop: str, fps: int = SAMPLE_FPS, scale: str = "215:275") -> list[np.ndarray]:
    """Decode a video to small grayscale frames with ffmpeg (crop is ffmpeg's w:h:x:y)."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},crop={crop},scale={scale}",
                        "-q:v", "3", f"{tmp}/f_%05d.png"], check=True)
        return [np.asarray(Image.open(p).convert("L"), dtype=np.float32) for p in sorted(Path(tmp).glob("f_*.png"))]


def profile(videos: list[Path], crop: str) -> dict:
    """Profile one clip made of one or more consecutive files (a recording split in parts)."""
    frames: list[np.ndarray] = []
    for v in videos:
        frames += extract_frames(v, crop)
    return {"motion": summarize(diff_series(frames)), "beats": registered_beats(resample(frames, SAMPLE_FPS, BEAT_FPS))}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("videos", nargs="+", type=Path, help="one clip; several files are treated as consecutive parts")
    p.add_argument("--crop", default="860:1100:0:320", help="ffmpeg crop w:h:x:y of the picture area "
                   "(default suits a 1080x1920 film; a phone screen recording needs the rows of the video, e.g. 860:1100:0:420)")
    a = p.parse_args()
    print(json.dumps(profile(a.videos, a.crop), indent=2))


if __name__ == "__main__":
    main()
