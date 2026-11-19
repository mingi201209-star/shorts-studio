"""EP.03 speed bumps: final assembly + every gate (technical, original video QA, content). preflight=True collects all failures into one report and
never yields a deliverable. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks.road_safety.episode2_film import caption_filter, check_loudness, loudness, probe, run, silence
from benchmarks.speed_bump import speed_bump_gates as gates
from benchmarks.speed_bump import speed_bump_motion as sim
from shorts_studio.final_video_qa import (
    measure_visual_activity,
    verify_captions_visible,
    verify_no_black_opening,
    verify_visual_activity,
)
from benchmarks.road_safety.runaway_ramp_gates import caption_safety


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_captions_over_picture(video: Path, frames_dir: Path, sample_points: list[tuple[float, tuple[int, int]]], build_dir: Path, fps: int = 30,
                                 diff_threshold: int = 110) -> dict:
    """The captions sit ON the picture (no black band), so "bright pixels in the band" (the check for a black caption band) would also count sky, white
    paint or the reveal's glow. Instead the caption pixels are measured directly: the encoded video frame is compared with the caption-free composed frame
    it was made from, and the rows that changed (white text and its black outline) are the caption rows. Same two requirements as the band check: real
    caption pixels exist in the expected band, and they do not touch the bottom edge."""
    import numpy as np
    from PIL import Image

    evidence = []
    for i, (ts, band) in enumerate(sample_points):
        n = int(round(ts * fps))
        grab = build_dir / f"_capdiff_{i}.png"
        # exactly frame n (0-based) of the encoded video, so it lines up with composed frame n + 1 pixel for pixel
        run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"select=eq(n\\,{n})", "-vsync", "0", "-frames:v", "1", str(grab)])
        shot = np.asarray(Image.open(grab).convert("L"), dtype=np.int16)
        source = np.asarray(Image.open(frames_dir / f"frame_{n + 1:04d}.png").convert("L"), dtype=np.int16)
        if shot.shape != source.shape:
            return {"status": "FAIL", "reason": f"frame size mismatch at t={ts}", "evidence": evidence}
        rows = np.where((np.abs(shot - source) > diff_threshold).any(axis=1))[0]
        rows = rows[(rows >= band[0]) & (rows <= band[1])]
        evidence.append({"t": ts, "rows_in_band": [int(rows.min()), int(rows.max())] if len(rows) else None})
        if len(rows) == 0:
            return {"status": "FAIL", "reason": f"no caption pixels found in the expected band at t={ts}", "evidence": evidence}
        if rows.max() >= shot.shape[0] - 2:
            return {"status": "FAIL", "reason": f"caption pixels touch the very bottom edge at t={ts} (clipped)", "evidence": evidence}
    return {"status": "PASS", "method": "encoded frame vs caption-free composed frame", "evidence": evidence}


def final_cut_checks(flat: Path, info_c: dict) -> dict:
    """Owner review of 1000020414.mp4: first impact within a second, X-ray against the road, spring motion that tracks the simulation, tyre contact,
    consistent LONG / SHORT signs, no repeated neighbouring camera."""
    def load(n):
        return np.array(Image.open(flat / f"frame_{n:04d}.png").convert("RGB"))
    first = gates.first_contact_film_seconds()
    return {
        "first_impact_within_1s": {"status": "PASS" if first <= 1.0 else "FAIL", "problems": [] if first <= 1.0 else [f"first wheel/bump contact at {first:.2f}s"],
                                    "first_contact_film_s": round(first, 2)},
        "tyre_road_contact": gates.tyre_road_contact(info_c),
        "suspension_timing": gates.suspension_timing(),
        "xray_readability": gates.xray_readability(load),
        "spring_tracks_simulation": gates.spring_tracks_simulation(load, info_c["wheelbase"], info_c["spring_proj"]),
        "signs_visible": gates.signs_visible(load, {int(k): v for k, v in info_c["sign_in_view"].items()}),
        "shots_are_distinct": gates.shots_are_distinct(),
    }


def assemble(frames: Path, audio: Path, manifest_path: Path, out: Path, preflight: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    problems: list[str] = []

    def fail(message: str) -> None:
        if not preflight:
            raise ValueError(message)
        problems.append(message)

    manifest = json.loads(manifest_path.read_text())
    total = manifest["total_frames"]
    names = sorted(frames.glob("frame_*.png"))
    if len(names) != total or [p.name for p in names] != [f"frame_{i:04d}.png" for i in range(1, total + 1)]:
        raise ValueError("composed frames incomplete or misnumbered")
    info_c = json.loads((frames / "compose-info.json").read_text())
    flat = out / "frames"
    flat.mkdir()
    for p in names:
        (flat / p.name).symlink_to(p.resolve())
    for name in ("narration.wav", "film.ass", "audio-validation.json"):
        (out / name).write_bytes((audio / name).read_bytes())
    ass = out / "film.ass"
    text = ass.read_text(encoding="utf8")
    if text.count(",0,0,1,3,0,2,90,90,210,1") != 1:
        raise ValueError("caption style line not in the expected form")
    # captions sit on the picture itself (full-height 1080x1920 frame, no black band): thick black outline + shadow, baseline lifted clear of the Shorts overlay
    ass.write_text(text.replace(",0,0,1,3,0,2,90,90,210,1", ",0,0,1,6,2,2,90,90,420,1"), encoding="utf8")
    audio_report = json.loads((out / "audio-validation.json").read_text())
    if audio_report["status"] != "PASS":
        raise ValueError("audio capture did not PASS")

    final = out / ("speed-bump-preflight.mp4" if preflight else sim.FILM_FILES["video"])
    run(["ffmpeg", "-v", "error", "-framerate", str(manifest["fps"]), "-i", str(flat / "frame_%04d.png"), "-i", str(out / "narration.wav"),
         "-vf", f"setpts=N/(30*TB),ass={out / 'film.ass'}", "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])
    pinfo = probe(final)
    video = next(s for s in pinfo["streams"] if s["codec_type"] == "video")
    astream = next(s for s in pinfo["streams"] if s["codec_type"] == "audio")
    if (video["width"], video["height"], video["r_frame_rate"], int(video["nb_read_frames"])) != (1080, 1920, f"{manifest['fps']}/1", total):
        fail("RESOLUTION_FPS_FRAMECOUNT_MISMATCH")
    if astream["codec_name"] != "aac" or astream["sample_rate"] != "48000":
        fail("AUDIO_CODEC_MISMATCH")
    if abs(float(pinfo["format"]["duration"]) - total / manifest["fps"]) > 0.04:
        fail("DURATION_MISMATCH")
    run(["ffmpeg", "-v", "error", "-i", final, "-f", "null", "-"])
    hashes = run(["ffmpeg", "-v", "error", "-i", final, "-map", "0:v:0", "-f", "framemd5", "-"]).stdout
    unique = [x.split(",")[-1].strip() for x in hashes.splitlines() if x and not x.startswith("#")]
    if not (len(unique) == len(set(unique)) == total):
        seen, pairs = {}, []
        for i, v in enumerate(unique, 1):
            if v in seen:
                pairs.append([seen[v], i])
            else:
                seen[v] = i
        print("BUMP_DUPLICATE_FRAMES " + json.dumps({"decoded": len(unique), "pairs": pairs[:60]}), flush=True)
        fail("DUPLICATE_OR_MISSING_FRAMES_IN_FINAL_ENCODE")
    black = run(["ffmpeg", "-hide_banner", "-i", final, "-vf", "blackdetect=d=0.15:pix_th=0.06", "-an", "-f", "null", "-"]).stderr
    if "black_start:" in black:
        fail("UNEXPECTED_BLACK_FRAMES")
    try:
        gaps = silence(final)
        levels = check_loudness(loudness(final))
    except AssertionError as error:
        if not preflight:
            raise
        gaps, levels = None, None
        problems.append(f"AUDIO_QA_FAILED: {error}")

    cues = audio_report["cues"]
    picture, band = (0, 1440), (1400, 1919)
    original_qa = {
        "visual_activity": verify_visual_activity(measure_visual_activity(final, picture, out)),
        "black_opening": verify_no_black_opening(final, picture, out),
        "captions_visible": verify_captions_over_picture(final, flat, [((c["start"] + c["end"]) / 2, band) for c in cues], out),
    }
    print("BUMP_ORIGINAL_QA " + json.dumps(original_qa), flush=True)
    failing = [k for k, v in original_qa.items() if v["status"] != "PASS"]
    if failing:
        fail(f"ORIGINAL_VIDEO_QA_FAILED: {failing}")

    sample = {f: np.array(Image.open(frames / f"frame_{f:04d}.png").convert("RGB")) for f in (10, 90)}
    content_qa = {
        "narration_numbers": gates.narration_numbers(info_c["peaks"]),
        "narration_picture_timing": gates.narration_picture_timing(audio_report),
        **({"picture_events_match_cues": gates.picture_events_match_cues(audio_report)} if sim.SYNC_EVENTS else {}),
        "first_three_seconds": gates.first_three_seconds(sample, gates.first_contact_film_seconds()),
        **(final_cut_checks(flat, info_c) if sim.FILM == "final" else {}),
        "caption_safety": caption_safety(cues, original_qa["captions_visible"]["evidence"]),
        "assumptions_declared": (gates.assumptions_in_description(manifest["description_file"]) if manifest.get("description_file")
                                 else gates.assumptions_in_narration(audio_report)),
        "all_3d_no_overlays": {"status": "PASS" if info_c.get("all_3d") is True and info_c.get("overlays") == "none" and info_c.get("physically_calibrated") is False else "FAIL",
                               "problems": [] if info_c.get("all_3d") is True and info_c.get("overlays") == "none" else ["frames were not produced by the overlay-free 3D renderer"]},
    }
    print("BUMP_SPOKEN_STARTS " + json.dumps(content_qa["narration_picture_timing"]["beat_starts"]), flush=True)
    print("BUMP_CONTENT_QA " + json.dumps(content_qa), flush=True)
    (out / "speed-bump-content-qa.json").write_text(json.dumps(content_qa, indent=2))
    for name, verdict in content_qa.items():
        if verdict["status"] != "PASS":
            fail(f"CONTENT_QA_FAILED {name}: {verdict.get('problems') or verdict}")

    if preflight:
        report = {"status": "FAIL" if problems else "PASS", "problems": problems, "is_preflight": True, "deliverable": False, "upload_authorized": False}
        (out / "speed-bump-preflight.json").write_text(json.dumps(report, indent=2))
        print("BUMP_PREFLIGHT_REPORT " + json.dumps(report), flush=True)
        if problems:
            raise ValueError(f"PREFLIGHT_FAILED: {problems}")
        return report
    result = {"video": str(final.resolve()), "sha256": digest(final), "is_mock": False, "technical_status": "PASS", "content_qa": content_qa,
              "motion_model": "quarter-car simulation, assumed car values; not calibrated", "editorial_status": "HOLD_ACTUAL_REVIEW",
              "human_first_view": "UNVERIFIED", "voice_pronunciation": "UNVERIFIED", "upload_authorized": False,
              "duration_seconds": float(pinfo["format"]["duration"]), "silence_gaps": gaps, "loudness": levels, "frame_count": total}
    (out / sim.FILM_FILES["validation"]).write_text(json.dumps(result, indent=2))
    print("BUMP_FILM_PASS " + result["sha256"], flush=True)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--preflight", action="store_true")
    a = p.parse_args()
    assemble(a.frames, a.audio, a.manifest, a.out, preflight=a.preflight)


if __name__ == "__main__":
    main()
