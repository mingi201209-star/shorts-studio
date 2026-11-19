"""Assemble the sand-barrel-cushion episode from native shards + real
captured audio into a final MP4, then run the same technical QA rigor
(loudness, silence, black-opening, caption visibility, visual activity,
duplicate-frame detection) the rest of this project's video pipeline uses.

Content gates (crash_cushion_gates.py) read the renderer's per-frame
telemetry: narration-to-screen match sentence by sentence, two physical
events starting inside the first three seconds, simulated motion inside
plausible bounds, and captions inside the safe part of the caption band.
These are geometric/simulation checks, not image understanding; the result
says so. The black caption band itself is the designed Shorts safe area and
is never scored as wasted picture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmarks.road_safety.episode2_film import (
    caption_filter,
    check_loudness,
    loudness,
    probe,
    run,
    silence,
)
from benchmarks.road_safety import crash_cushion_gates as gates
from shorts_studio.final_video_qa import (
    measure_visual_activity,
    verify_captions_visible,
    verify_no_black_opening,
    verify_visual_activity,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_native_frames(native: Path, manifest: dict) -> dict[int, Path]:
    proofs = sorted(native.rglob("cushion-proof.json"))
    if not proofs:
        raise ValueError("no native shard proofs found")
    renderer_sha256 = None
    frame_paths: dict[int, Path] = {}
    for proof_path in proofs:
        proof = json.loads(proof_path.read_text())
        folder = proof_path.parent
        if renderer_sha256 is None:
            renderer_sha256 = proof["renderer_source_sha256"]
        elif proof["renderer_source_sha256"] != renderer_sha256:
            raise ValueError("mixed renderer_source_sha256 across shards; refuse to assemble")
        for checksum in proof["checksums"]:
            frame = checksum["frame"]
            path = folder / f"frame_{frame:04d}.png"
            if digest(path) != checksum["sha256"]:
                raise ValueError(f"frame hash mismatch: {path}")
            if frame in frame_paths:
                raise ValueError(f"duplicate frame number across shards: {frame}")
            frame_paths[frame] = path
    total = manifest["total_frames"]
    if set(frame_paths) != set(range(1, total + 1)):
        missing = sorted(set(range(1, total + 1)) - set(frame_paths))
        raise ValueError(f"MISSING_NATIVE_FRAMES: {missing[:10]}{'...' if len(missing) > 10 else ''}")
    return frame_paths


def collect_telemetry(native: Path, manifest: dict) -> tuple[dict[int, dict], dict]:
    telemetry: dict[int, dict] = {}
    summaries = None
    for proof_path in sorted(native.rglob("cushion-proof.json")):
        proof = json.loads(proof_path.read_text())
        if summaries is None:
            summaries = proof["motion_summary"]
        elif proof["motion_summary"] != summaries:
            raise ValueError("shards disagree about the simulated motion; refuse to assemble")
        for record in proof["telemetry"]:
            telemetry[record["frame"]] = record
    if set(telemetry) != set(range(1, manifest["total_frames"] + 1)):
        raise ValueError("TELEMETRY_INCOMPLETE")
    return telemetry, summaries


def assemble(native: Path, audio: Path, manifest_path: Path, out: Path, preflight: bool = False) -> dict:
    """preflight=True takes cheap low-resolution preview shards, upscales
    them to the manifest resolution and runs every gate below, collecting
    ALL failures into one report instead of stopping at the first. It never
    produces a deliverable: the output is named and flagged as a preflight."""
    out.mkdir(parents=True, exist_ok=False)
    problems: list[str] = []

    def fail(message: str) -> None:
        if not preflight:
            raise ValueError(message)
        problems.append(message)

    manifest = json.loads(manifest_path.read_text())
    frame_paths = collect_native_frames(native, manifest)

    flat = out / "frames"
    flat.mkdir()
    for frame, path in frame_paths.items():
        (flat / f"frame_{frame:04d}.png").symlink_to(path.resolve())

    for name in ("narration.wav", "film.ass", "audio-validation.json"):
        (out / name).write_bytes((audio / name).read_bytes())
    # Lift the captions clear of the YouTube Shorts overlay (title, channel
    # and description cover roughly the bottom fifth of the frame). The
    # shared caption builder puts the baseline 210px above the bottom edge;
    # 420 places the line at about rows 1445-1500, still inside the black
    # caption band (1400-1919) and above the overlay. Done here on this
    # episode's copy so other episodes' caption layout is untouched.
    ass_path = out / "film.ass"
    ass_text = ass_path.read_text(encoding="utf8")
    if ass_text.count(",2,90,90,210,1") != 1:
        raise ValueError("caption style line not in the expected form")
    ass_path.write_text(ass_text.replace(",2,90,90,210,1", ",2,90,90,420,1"), encoding="utf8")
    audio_report = json.loads((out / "audio-validation.json").read_text())
    if audio_report["status"] != "PASS":
        raise ValueError("audio capture did not PASS")

    final = out / ("sand-barrel-preflight.mp4" if preflight else "sand-barrel-cushion.mp4")
    video_filter = caption_filter(out)
    if manifest.get("look") == "cinematic":
        # Grade first; caption_filter then repaints the black band and burns
        # the captions, so the grade never touches the YouTube-safe area.
        from benchmarks.road_safety import cinematic
        video_filter = f"{cinematic.GRADE_FILTER},{video_filter}"
    if preflight:
        width, height = manifest["resolution"]
        video_filter = f"scale={width}:{height}:flags=lanczos,{video_filter}"
    run(["ffmpeg", "-v", "error", "-framerate", str(manifest["fps"]),
         "-i", str(flat / "frame_%04d.png"),
         "-i", str(out / "narration.wav"),
         "-vf", video_filter,
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])

    info = probe(final)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio_stream = next(s for s in info["streams"] if s["codec_type"] == "audio")
    expected_w, expected_h = manifest["resolution"]
    if (video["width"], video["height"], video["r_frame_rate"], int(video["nb_read_frames"])) != (
        expected_w, expected_h, f"{manifest['fps']}/1", manifest["total_frames"]
    ):
        fail("RESOLUTION_FPS_FRAMECOUNT_MISMATCH")
    if audio_stream["codec_name"] != "aac" or audio_stream["sample_rate"] != "48000":
        fail("AUDIO_CODEC_MISMATCH")
    if abs(float(info["format"]["duration"]) - manifest["total_frames"] / manifest["fps"]) > 0.04:
        fail("DURATION_MISMATCH")

    run(["ffmpeg", "-v", "error", "-i", final, "-f", "null", "-"])
    hashes = run(["ffmpeg", "-v", "error", "-i", final, "-map", "0:v:0", "-f", "framemd5", "-"]).stdout
    unique = [x.split(",")[-1].strip() for x in hashes.splitlines() if x and not x.startswith("#")]
    if not (len(unique) == len(set(unique)) == manifest["total_frames"]):
        seen: dict[str, int] = {}
        pairs = []
        for index, value in enumerate(unique, start=1):
            if value in seen:
                pairs.append([seen[value], index])
            else:
                seen[value] = index
        print("CUSHION_DUPLICATE_FRAMES " + json.dumps(
            {"decoded_frames": len(unique), "duplicate_pairs": pairs[:60]}), flush=True)
        fail("DUPLICATE_OR_MISSING_FRAMES_IN_FINAL_ENCODE")
    black = run(["ffmpeg", "-hide_banner", "-i", final, "-vf",
                 "blackdetect=d=0.15:pix_th=0.06", "-an", "-f", "null", "-"]).stderr
    if "black_start:" in black:
        print("CUSHION_BLACK_FRAMES " + json.dumps(
            [line.split("blackdetect")[-1].strip() for line in black.splitlines() if "black_start:" in line]),
            flush=True)
        fail("UNEXPECTED_BLACK_FRAMES")

    try:
        gaps = silence(final)
        levels = check_loudness(loudness(final))
    except AssertionError as error:
        if not preflight:
            raise
        gaps, levels = None, None
        problems.append(f"AUDIO_QA_FAILED: {error}")

    cues = json.loads((out / "audio-validation.json").read_text())["cues"]
    picture = (0, 1400)
    band = (1400, 1919)
    original_qa = {
        "visual_activity": verify_visual_activity(measure_visual_activity(final, picture, out)),
        "black_opening": verify_no_black_opening(final, picture, out),
        "captions_visible": verify_captions_visible(
            final, [((c["start"] + c["end"]) / 2, band) for c in cues], out),
    }
    print("CUSHION_ORIGINAL_QA " + json.dumps(original_qa), flush=True)
    failing = [k for k, v in original_qa.items() if v["status"] != "PASS"]
    if failing:
        fail(f"ORIGINAL_VIDEO_QA_FAILED: {failing}")

    telemetry, summaries = collect_telemetry(native, manifest)
    audio_report = json.loads((out / "audio-validation.json").read_text())
    content_qa = {
        "motion_plausibility": gates.motion_plausibility(summaries),
        "narration_screen_match": gates.narration_screen_match(manifest, audio_report, telemetry),
        "first_three_seconds": gates.first_three_seconds(manifest, telemetry),
        "caption_safety": gates.caption_safety(cues, original_qa["captions_visible"]["evidence"]),
    }
    print("CUSHION_SPOKEN_WINDOWS " + json.dumps(
        [[s["sentence"], s["spoken"], s["frames"]] for s in content_qa["narration_screen_match"]["sentences"]]),
        flush=True)
    print("CUSHION_CONTENT_QA " + json.dumps(content_qa), flush=True)
    (out / "sand-barrel-content-qa.json").write_text(json.dumps(content_qa, indent=2))
    for name, verdict in content_qa.items():
        if verdict["status"] != "PASS":
            fail(f"CONTENT_QA_FAILED {name}: {verdict.get('problems') or verdict}")

    if preflight:
        report = {"status": "FAIL" if problems else "PASS", "problems": problems,
                  "is_preflight": True, "deliverable": False, "upload_authorized": False}
        (out / "sand-barrel-preflight.json").write_text(json.dumps(report, indent=2))
        print("CUSHION_PREFLIGHT_REPORT " + json.dumps(report), flush=True)
        if problems:
            raise ValueError(f"PREFLIGHT_FAILED: {problems}")
        return report

    result = {
        "video": str(final.resolve()),
        "sha256": digest(final),
        "is_mock": False,
        "technical_status": "PASS",
        "content_screen_match": "PASS",
        "content_screen_match_method": "simulation-state + visibility telemetry (not image understanding)",
        "content_qa": content_qa,
        "motion_model": "momentum-accretion drag on a rigid car + ballistic sand; not a validated crash simulation",
        "editorial_status": "HOLD_ACTUAL_REVIEW",
        "human_first_view": "UNVERIFIED",
        "upload_authorized": False,
        "resolution": [video["width"], video["height"]],
        "fps": manifest["fps"],
        "duration_seconds": float(info["format"]["duration"]),
        "silence_gaps": gaps,
        "loudness": levels,
        "original_video_qa": original_qa,
        "frame_count": manifest["total_frames"],
    }
    (out / "sand-barrel-validation.json").write_text(json.dumps(result, indent=2))
    print("CUSHION_FILM_PASS " + result["sha256"], flush=True)
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--native", type=Path, required=True)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--preflight", action="store_true")
    args = p.parse_args()
    assemble(args.native, args.audio, args.manifest, args.out, preflight=args.preflight)


if __name__ == "__main__":
    main()
