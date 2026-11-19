"""Encodes the PNG frames of one render shard into a near-lossless H.264 segment (crf 8) and writes the proof JSON beside it, then deletes the PNGs: a native 1080x1920 film is
several GB of PNGs but a few tens of MB as segments, which is what the next job downloads. The proof keeps the SHA-256 of every source frame, the renderer source hash,
the telemetry and the evidence."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--fps", type=int, default=30)
    a = p.parse_args()
    proof = json.loads((a.dir / "crumple-proof.json").read_text())
    frames = sorted(proof["checksums"], key=lambda c: c["frame"])
    seq = a.dir / "seq"
    seq.mkdir(exist_ok=True)
    for i, c in enumerate(frames):
        (seq / f"s_{i:04d}.png").hardlink_to(a.dir / f"frame_{c['frame']:04d}_{c['panel']}.png")
    first = frames[0]["frame"]
    out = a.dir / f"shard-{first:04d}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps), "-i", str(seq / "s_%04d.png"), "-c:v", "libx264", "-preset", "slow", "-crf", "8",
                    "-pix_fmt", "yuv420p", "-g", "30", str(out)], check=True)
    proof["segment"] = {"file": out.name, "first_frame": first, "frames": len(frames)}
    (a.dir / "crumple-proof.json").write_text(json.dumps(proof, indent=1))
    for c in frames:
        (a.dir / f"frame_{c['frame']:04d}_{c['panel']}.png").unlink()
    for f in seq.iterdir():
        f.unlink()
    seq.rmdir()
    print(f"ENCODED {out.name} {len(frames)} frames")


if __name__ == "__main__":
    main()
