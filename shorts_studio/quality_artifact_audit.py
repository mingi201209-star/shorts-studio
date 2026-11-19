"""Independent byte/format provenance audit of a completed ORIGINAL native 30s MP4.

The original assembler must pass its own unchanged CLIP/visual/speech gates.
Passing this audit is still NOT editorial acceptance or upload authorization.
The audit cannot prove photorealism, physical suspension, or audience retention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from .quality_program import build_scorecard


def probe_video(file: Path) -> dict:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-show_streams",
         "-show_format", "-of", "json", str(file)],
        check=True, capture_output=True, text=True, timeout=60,
    )
    return json.loads(p.stdout)


def audit_film(video: Path, report: dict, probe_fn=None) -> dict:
    """Return only evidence result. Inability to inspect is always REJECTED."""
    score = build_scorecard(report)
    result = {
        "status": "EVIDENCE_REJECTED",
        "native_technical_status": score["technical_status"],
        "original_semantic_status": score["semantic_status"],
        "original_viewer_status": score["viewer_status"],
        "sha256_checked": False,
        "video_sha256": None,
        "human_review": score["human_review"],
        "editorial_decision": "HOLD",
        "upload_authorized": False,
        "note": "Full MP4 byte/format integrity only; editor must watch and listen.",
    }
    if score["technical_status"] != "PASS":
        result["reason"] = "original assembler validation report invalid or missing"
        return result
    if not video.is_file() or video.stat().st_size < 100000:
        result["reason"] = "original final MP4 missing or implausibly tiny"
        return result
    expected = report.get("sha256")
    h = hashlib.sha256()
    with video.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    result["video_sha256"] = h.hexdigest()
    if result["video_sha256"] != expected:
        result["reason"] = "actual MP4 byte hash disagrees with original report"
        return result
    result["sha256_checked"] = True
    try:
        info = (probe_fn or probe_video)(video)
        video_streams = [s for s in info["streams"] if s["codec_type"] == "video"]
        audio_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]
        if len(video_streams) != 1 or len(audio_streams) != 1:
            raise ValueError("unexpected number of video/audio streams")
        v, a = video_streams[0], audio_streams[0]
        if (v.get("codec_name") != "h264"
                or (v.get("width"), v.get("height")) != (1080, 1920)
                or v.get("r_frame_rate") != "30/1"
                or int(v.get("nb_read_frames", -1)) != 900
                or a.get("codec_name") != "aac"
                or a.get("sample_rate") != "48000"
                or a.get("channels") != 1
                or not math.isfinite(float(info["format"]["duration"]))
                or abs(float(info["format"]["duration"]) - 30.0) >= .04):
            raise ValueError("invalid 900-frame H264/AAC/30-second native format")
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        result["reason"] = "ffprobe verification failed: " + type(exc).__name__
        return result
    result["status"] = "EVIDENCE_VALIDATED"
    result["reason"] = "original strict film QA and independent MP4 hash/codec checks passed"
    result["original_video_status"] = "PASS"
    result["video_size_bytes"] = video.stat().st_size
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--film-validation", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.film_validation.read_text())
    result = audit_film(args.video, report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print("WEEK1_INDEPENDENT_FINAL_MP4_AUDIT "
          + json.dumps({"status": result["status"],
                        "native_technical_status": result["native_technical_status"],
                        "editorial_decision": result["editorial_decision"]}), flush=True)
    if result["status"] != "EVIDENCE_VALIDATED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
