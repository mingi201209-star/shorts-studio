"""Fail-closed cached native 3D film release check (technical, not editorial)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


class CacheDeliveryError(ValueError):
    """A cache-only film did not satisfy the original native delivery contract."""


def probe_video(filename: Path) -> dict:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,nb_read_frames,sample_rate",
         "-show_entries", "format=duration", "-of", "json", str(filename)],
        capture_output=True, text=True, check=True, timeout=60,
    )
    return json.loads(p.stdout)


def verify_native_cached_delivery(filename: Path, *, deadline_seconds: int = 300,
                                   elapsed_seconds: float | None = None) -> dict:
    if deadline_seconds != 300:
        raise CacheDeliveryError("five-minute SLA must not be weakened")
    if not filename.is_file() or filename.stat().st_size < 1_000_000:
        raise CacheDeliveryError("film file absent or implausibly small")
    profile = probe_video(filename)
    streams = profile.get("streams", [])
    videos = [x for x in streams if x.get("codec_type") == "video"]
    audios = [x for x in streams if x.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audios) < 1:
        raise CacheDeliveryError("exactly one native video and at least one audio track required")
    v = videos[0]
    if (v.get("width"), v.get("height"), v.get("codec_name"), v.get("r_frame_rate")) != (
        1080, 1920, "h264", "30/1"
    ):
        raise CacheDeliveryError("native 1080x1920 30fps H.264 delivery required")
    if int(v.get("nb_read_frames", -1)) != 900:
        raise CacheDeliveryError("900 individually decoded frames required")
    duration = float(profile.get("format", {}).get("duration", "nan"))
    if not 29.95 <= duration <= 30.15:
        raise CacheDeliveryError("film must have 30-second duration")
    if not any(x.get("codec_name") == "aac" for x in audios):
        raise CacheDeliveryError("missing encoded AAC narration")
    if elapsed_seconds is not None and (
        elapsed_seconds < 0 or elapsed_seconds > deadline_seconds
    ):
        raise CacheDeliveryError(f"over budget: {elapsed_seconds:.1f}s > 300s")
    sha = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return {
        "status": "PASS_TECHNICAL_NATIVE_CACHE_DELIVERY",
        "duration_seconds": duration,
        "decoded_frames": 900,
        "resolution": [1080, 1920],
        "video_sha256": sha.hexdigest(),
        "elapsed_seconds": elapsed_seconds,
        "under_five_minutes": elapsed_seconds is not None and elapsed_seconds <= 300,
        "independent_new_geometry_rendered": False,
        "editorial_upload_approved": False,
        "note": "Requires separate source-provenance and assembled-video QA. Reused 3D source only.",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--elapsed", type=float, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = verify_native_cached_delivery(args.file, elapsed_seconds=args.elapsed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf8")
    print("FAST_NATIVE_CACHED_DELIVERY_PASS " + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
