"""Build two PRIVATE first-5s hook A/B edits from audited real Blender MP4.

This is non-production editorial experimentation; it never claims the ORIGINAL
native 900-frame assembler passed. Frame provenance is linked to run 40084843910.
The failed original visual-activity gate remains failed. Reusing footage is an
editorial edit, not a new 900-frame native render or authorisation to upload.
Requires ffmpeg, ffprobe; for original visual-change QA: OpenCV and numpy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

SOURCE_ORIGINAL_RUN = 40084843910
SOURCE_REVIEW_SHA256 = "e01a7843645b135203043602acda58759bf3418308b216bb57751027033933f0"
RENDERER_SOURCE_SHA256 = "1ed298a8b17b6927c2aec01238ae968da7b297173aa7fbd25db21ac7e0f9d42d"
PIXEL_DELTA_THRESHOLD = 12.0  # unchanged shorts_studio.final_video_qa
SAMPLING_FPS = 2.0
review_status = "INTERNAL_REVIEW_ONLY_EDITORIAL_HOLD"
automatic_upload_authorized = False

# All shot times refer to the same original 900 native Cycles32 Blender frames.
# No AI-generated stills, fake grooves, geometric replacement, or source mixing.
SHOT_PLANS = {
    "A": ((0, 45), (165, 225), (315, 360)),
    "B": ((165, 210), (0, 60), (315, 360)),
}


def _checked_plan(plan) -> tuple[tuple[int, int], ...]:
    plan = tuple(tuple(pair) for pair in plan)
    if (len(plan) != 3
            or any(len(pair) != 2 or
                   any(type(x) is not int for x in pair) or
                   not (0 <= pair[0] < pair[1] <= 900) for pair in plan)
            or sum(end - start for start, end in plan) != 150
            or len({start // 150 for start, _ in plan}) != 3
            or any(start // 150 != (end - 1) // 150 for start, end in plan)):
        raise ValueError("must use exactly 150 distinct native frames across three real 3D source shots")
    return plan


def build_filtergraph(plan, *, full: bool) -> str:
    """Preserve the *original 0-5s* subtitle band; recut picture ONLY."""
    plan = _checked_plan(plan)
    inputs = "[0:v]split=5[s0][s1][s2][subs][late]" if full else "[0:v]split=4[s0][s1][s2][subs]"
    pieces = [inputs]
    for n, (first, last) in enumerate(plan):
        pieces.append(
            f"[s{n}]trim=start_frame={first}:end_frame={last},"
            f"setpts=PTS-STARTPTS,crop=1080:1400:0:0,setsar=1[v{n}]"
        )
    pieces.extend([
        "[v0][v1][v2]concat=n=3:v=1:a=0[actual3d]",
        "[subs]trim=start_frame=0:end_frame=150,setpts=PTS-STARTPTS,"
        "crop=1080:520:0:1400,setsar=1[original_caption]",
        "[actual3d][original_caption]vstack=inputs=2[opening]",
    ])
    if full:
        pieces.extend([
            "[late]trim=start_frame=150:end_frame=900,setpts=PTS-STARTPTS[late25]",
            "[opening][late25]concat=n=2:v=1:a=0,format=yuv420p,fps=30[vout]",
        ])
    else:
        pieces.append("[opening]format=yuv420p,fps=30[vout]")
    return ";".join(pieces)


def evaluate_differences(diffs: list[float]) -> dict:
    """Exact original 2fps/12-point rule, cropped to real 0:1400 media."""
    if (not isinstance(diffs, list) or len(diffs) not in (9, 59)
            or any(type(d) not in (int, float) or not math.isfinite(d)
                   or d < 0 for d in diffs)):
        raise ValueError("must provide nine (5s) or 59 (30s) real frame deltas")
    cuts = [0.0] + [
        i / SAMPLING_FPS for i, delta in enumerate(diffs, start=1)
        if delta >= PIXEL_DELTA_THRESHOLD
    ]
    end = (len(diffs) + 1) / SAMPLING_FPS
    maximum_hold = max(b - a for a, b in zip(cuts + [], cuts[1:] + [end]))
    first5 = sum(0 < t < 5 for t in cuts)
    ok = first5 >= 1 and maximum_hold <= 5.05
    return {
        "status": "PASS" if ok else "FAIL",
        "first_5s_visual_changes": first5,
        "cut_timestamps_s": cuts,
        "max_static_visual_seconds": maximum_hold,
        "sample_fps": SAMPLING_FPS,
        "original_unmodified_threshold": PIXEL_DELTA_THRESHOLD,
    }


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def _ffprobe(path: Path) -> dict:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-count_frames", "-show_streams",
        "-show_format", "-of", "json", str(path),
    ], timeout=70)
    return json.loads(raw)


def _check_video(path: Path, frames: int) -> None:
    if not path.is_file() or path.stat().st_size < 100_000:
        raise RuntimeError("missing or tiny original 3D film")
    info = _ffprobe(path)
    vids = [s for s in info["streams"] if s["codec_type"] == "video"]
    auds = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if len(vids) != 1 or len(auds) != 1:
        raise RuntimeError("expected exactly one native video and one voice track")
    v, a = vids[0], auds[0]
    if (v.get("codec_name") != "h264"
            or (v.get("width"), v.get("height")) != (1080, 1920)
            or v.get("r_frame_rate") != "30/1"
            or int(v.get("nb_read_frames", -1)) != frames
            or a.get("codec_name") != "aac"
            or abs(float(info["format"]["duration"]) - frames / 30) > .07):
        raise RuntimeError("source/output isn't correct 1080x1920 H264/AAC 30fps")


def _audio_digest(path: Path) -> str:
    return subprocess.check_output([
        "ffmpeg", "-loglevel", "error", "-i", str(path), "-map", "0:a:0",
        "-c:a", "copy", "-f", "md5", "-",
    ], timeout=60).decode().strip()


def _measure_original_cadence(video: Path, temp: Path) -> dict:
    # Pixel frames in JPEG reproduce the PRODUCTION final_video_qa algorithm,
    # including its 2fps sampling and same 1080x1400 media crop; subtitles
    # cannot fake the visual activity change.
    import cv2
    import numpy as np

    temp.mkdir(parents=True, exist_ok=True)
    for stale in temp.glob("f_*.jpg"):
        stale.unlink()
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video), "-vf", "fps=2,crop=1080:1400:0:0",
        str(temp / "f_%05d.jpg"),
    ], check=True, timeout=100)
    pictures = sorted(temp.glob("f_*.jpg"))
    if len(pictures) not in (10, 60):
        raise RuntimeError("original sampled clip requires 10 or 60 images")
    previous = cv2.imread(str(pictures[0]))
    if previous is None:
        raise RuntimeError("unreadable native review frame")
    deltas = []
    for frame in pictures[1:]:
        current = cv2.imread(str(frame))
        if current is None or current.shape != previous.shape:
            raise RuntimeError("inconsistent native media frame geometry")
        deltas.append(float(np.abs(current.astype(int) - previous.astype(int)).mean()))
        previous = current
    result = evaluate_differences(deltas)
    result["per_half_second_pixel_deltas"] = [round(n, 3) for n in deltas]
    return result


def produce(source: Path, out: Path, *, include_full: bool = True) -> dict:
    if not source.is_file() or _sha256(source) != SOURCE_REVIEW_SHA256:
        raise RuntimeError("source must be EXACT failed-visual-QA original 900-frame review MP4")
    _check_video(source, 900)
    out.mkdir(parents=True, exist_ok=True)
    original_audio = _audio_digest(source)
    report = {
        "status": "NOT_UPLOAD_READY", "review_status": review_status,
        "original_run": SOURCE_ORIGINAL_RUN,
        "original_run_conclusion": "failure",
        "original_rejection": "ORIGINAL_VIDEO_QA visual_activity first_5s_visual_changes=0",
        "source_sha256": SOURCE_REVIEW_SHA256,
        "renderer_source_sha256": RENDERER_SOURCE_SHA256,
        "original_qa_unchanged": True, "automatic_upload_authorized": False,
        "candidates": {},
    }
    for name, cuts in SHOT_PLANS.items():
        seconds = 30 if include_full else 5
        dest = out / f"episode2-{name}-{seconds}s-EDITORIAL-HOLD.mp4"
        graph = build_filtergraph(cuts, full=include_full)
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-filter_complex", graph, "-map", "[vout]", "-map", "0:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-threads", "6", "-pix_fmt", "yuv420p", "-r", "30",
        ]
        if include_full:
            cmd += ["-c:a", "copy"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "48000"]
        cmd += ["-t", str(seconds), "-movflags", "+faststart", str(dest)]
        subprocess.run(cmd, check=True, timeout=200)
        _check_video(dest, seconds * 30)
        audio_identical = (_audio_digest(dest) == original_audio) if include_full else None
        if include_full and not audio_identical:
            raise RuntimeError("source English narration changed; editorial recut is invalid")
        activity = _measure_original_cadence(dest, out / f"_qa_A_B_{name}")
        report["candidates"][name] = {
            "file": str(dest), "video_sha256": _sha256(dest),
            "source_spans_original_native_frame_exclusive": cuts,
            "whole_original_30s_audio_bitstream_identical": audio_identical,
            "first5_caption_stripe": "original frames 0-149, unchanged timing",
            "real_pixel_qa": activity, "upload_authorized": False,
        }
        print("PRIVATE_AB_REAL_3D", name, activity["status"],
              activity["first_5s_visual_changes"], flush=True)
    report["status"] = (
        "FIRST5_PIXELS_PASS_EDITORIAL_HOLD"
        if all(c["real_pixel_qa"]["status"] == "PASS"
               for c in report["candidates"].values())
        else "FIRST5_PIXELS_FAIL_EDITORIAL_HOLD"
    )
    target = out / "INTERNAL_EDITORIAL_AB_REPORT.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    if report["status"] != "FIRST5_PIXELS_PASS_EDITORIAL_HOLD":
        raise RuntimeError("original unchanged visual activity gate still fails; preserve evidence")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--first5-only", action="store_true")
    args = parser.parse_args()
    result = produce(args.source, args.out, include_full=not args.first5_only)
    print("PRIVATE_FIRST5_ONLY_REEDIT_VALIDATED_NOT_UPLOAD_READY",
          result["status"], flush=True)


if __name__ == "__main__":
    main()
