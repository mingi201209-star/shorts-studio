"""Level-matches the captured TTS sentences before the audio is built: free TTS gives each sentence a slightly different loudness (the short last sentence of EP.04 is 2.4 LU
quieter than the first), which the unchanged "even shot loudness" gate (<= 3 LU between shots) rejects. Each sentence gets a plain gain so that its integrated loudness is
TARGET_LUFS (peaks limited). Word timings are untouched (a gain does not move words); the hash and duration in capture.json are updated to the levelled files."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

TARGET_LUFS = -16.5


def integrated_lufs(path: Path) -> float:
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = err[err.rindex("Integrated loudness"):]
    return float(re.search(r"I:\s+(-?\d+\.\d+)\s+LUFS", summary).group(1))


def level(folder: Path, target: float = TARGET_LUFS) -> list[dict]:
    capture = json.loads((folder / "capture.json").read_text())
    rows = []
    for i, beat in enumerate(capture["beats"], 1):
        raw = folder / f"beat_{i:02}.mp3"
        before = integrated_lufs(raw)
        gain = target - before
        out = folder / f"beat_{i:02}.levelled.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"volume={gain:.3f}dB,alimiter=limit=0.89", "-c:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
        out.replace(raw)
        beat["audio_sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
        beat["duration"] = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(raw)], text=True))
        rows.append({"beat": i, "before_lufs": before, "gain_db": round(gain, 2), "after_lufs": integrated_lufs(raw)})
    (folder / "capture.json").write_text(json.dumps(capture, indent=2) + "\n")
    return rows


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--folder", type=Path, required=True)
    for row in level(p.parse_args().folder):
        print("LEVELLED_BEAT " + json.dumps(row), flush=True)
