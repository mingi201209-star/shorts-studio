"""EP.05: composes the rendered film frames (720x1280 master -> 1080x1920), muxes the frozen narration with the burned-in captions (the film starts PRE_ROLL_S before the speech) and runs every
gate that can be decided from the clip. Never uploads. Gates that exist only for EP.04 (crumple geometry) are not applicable; the EP.05 gates are listed in the report."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks.belt_limiter import belt_motion as bm
from benchmarks.belt_limiter import belt_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import cue_mismatches, gray_diffs, shift_ass
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
W, H = 1080, 1920


def no_scene_text_belt() -> dict:
    src = (Path(__file__).resolve().parent / "render_belt_3d.py").read_text()
    banned = ("curves.new", '"FONT"', "'FONT'", "body_text", "text_add", "type=\"FONT\"")
    hits = [b for b in banned if b in src]
    return {"status": "FAIL" if hits else "PASS", "problems": [f"renderer creates scene text ({h})" for h in hits]}


def compose(panels: Path, out: Path, n_frames: int):
    shots, sha = [], None
    out.mkdir(parents=True, exist_ok=True)
    for bj in sorted(panels.rglob("belt-shots.json")):
        rec = json.loads(bj.read_text())
        if sha is None:
            sha = rec["renderer_source_sha256"]
        elif rec["renderer_source_sha256"] != sha:
            raise SystemExit("mixed renderer versions across shards")
        for s in rec["shots"]:
            path = bj.parent / f"frame_{int(s['shot']):05d}.png"
            if hashlib.sha256(path.read_bytes()).hexdigest() != s["sha256"]:
                raise SystemExit(f"hash mismatch {path}")
            im = Image.open(path).convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            im.save(out / f"frame_{int(s['shot']) + 1:04d}.png")
            shots.append(s)
    shots.sort(key=lambda s: int(s["shot"]))
    if [int(s["shot"]) for s in shots] != list(range(n_frames)):
        raise SystemExit(f"rendered {len(shots)} frames, expected exactly frames 0..{n_frames - 1}")
    return shots, sha


def telemetry_matches_model(shots: list[dict], segs: list[dict]) -> dict:
    """The numbers the renderer used for every frame (simulated time, chest load, pay-out) equal the model for that frame's segment, belt and time: nothing was drawn from a different state."""
    problems = []
    for s in shots:
        sh = tl.frame_shot(int(s["shot"]), segs)
        t = bm.contact_time_s() + sh["dt"]
        m = bm.at(sh["variant"], t)
        if abs(s["sim_time"] - t) > 2e-5 or abs(s["chest_g"] - m["chest_g"]) > 0.02 or abs(s["payout_m"] - m["payout_m"]) > 2e-4:
            problems.append(f"frame {s['shot']}: renderer state differs from the model")
            if len(problems) > 5:
                break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(shots: list[dict], segs: list[dict]) -> dict:
    """The actions the narration names really move in the rendered numbers: the pretensioner pulls the driver back (segment D/E), the reel pays out webbing (segment G), the plain belt
    loads the chest harder than the modern one in the same crash."""
    by = {}
    for s in shots:
        by.setdefault(s["segment"], []).append(s)
    problems = []
    pull = max((x["pull_back_m"] for x in by.get("E-cabin-held-back", [])), default=0.0)
    if pull < 0.01:
        problems.append(f"pretensioner pull-back is only {pull * 100:.1f} cm in the cabin view")
    pay = [x["payout_m"] for x in by.get("G-reel-inside", [])]
    if not pay or max(pay) - min(pay) < 0.03:
        problems.append("webbing pay-out does not change visibly in the reel shot")
    plain = max((x["chest_g"] for x in by.get("I-plain-belt", [])), default=0.0)
    modern = max((x["chest_g"] for x in by.get("H-gentle-stop", [])), default=0.0)
    if not plain > modern * 1.2:
        problems.append(f"plain belt chest load {plain:.1f} g is not clearly above the modern belt {modern:.1f} g on screen")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "pull_back_cm": round(pull * 100, 1), "payout_change_cm": round((max(pay) - min(pay)) * 100, 1) if pay else 0,
            "plain_peak_g_on_screen": round(plain, 1), "modern_peak_g_on_screen": round(modern, 1)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panels", type=Path, required=True)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames-dir", type=Path, default=None)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    frames = a.frames_dir or (a.out / "frames")
    film = json.loads((ROOT / "examples/experiments/belt-film.json").read_text())
    segs = tl.segments(film["line_starts"], film["total_s"])
    n = tl.frame_count(film["total_s"])
    shots, sha = compose(a.panels, frames, n)
    audio_report = json.loads((a.audio / "audio-validation.json").read_text())
    frozen = json.loads((ROOT / "examples/experiments/belt-real-cues.json").read_text())
    narration_sha = hashlib.sha256((a.audio / "narration.wav").read_bytes()).hexdigest()
    print("FROZEN_AUDIO_SHA256 " + narration_sha, flush=True)
    mismatches = cue_mismatches(audio_report["cues"], frozen["cues"])
    if mismatches:
        print("FROZEN_CUE_MISMATCH " + json.dumps(mismatches[:6]), flush=True)
        raise SystemExit("audio cue timing differs from the frozen narration")
    for name in ("narration.wav", "film.ass"):
        (a.out / name).write_bytes((a.audio / name).read_bytes())
    pre = tl.PRE_ROLL_S
    ass = a.out / "film.ass"
    text = ass.read_text(encoding="utf8")
    style = ",0,0,1,3,0,2,90,90,210,1"
    if text.count(style) != 1:
        raise SystemExit("caption style line not in the expected form")
    ass.write_text(shift_ass(text.replace(style, ",0,0,1,6,2,2,90,90,420,1"), pre), encoding="utf8")
    cues = [{**c, "start": c["start"] + pre, "end": c["end"] + pre} for c in audio_report["cues"]]
    seconds = n / tl.FPS
    video = a.out / "belt-film-1080x1920.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(tl.FPS), "-i", str(frames / "frame_%04d.png"), "-i", str(a.out / "narration.wav"),
         "-vf", f"setpts=N/({tl.FPS}*TB),ass={a.out / 'film.ass'}", "-af", f"adelay={int(round(pre * 1000))}:all=1", "-map", "0:v:0", "-map", "1:a:0", "-t", f"{seconds}", "-c:v", "libx264",
         "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", video])
    info = probe(video)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    problems = []
    if (vs["width"], vs["height"], int(vs["nb_read_frames"])) != (W, H, n):
        problems.append(f"video is {vs['width']}x{vs['height']} with {vs['nb_read_frames']} frames, expected {n}")
    in_clip = [c for c in cues if c["end"] <= seconds - 0.1]
    beat_starts = [b["start"] + pre for b in audio_report["beats"]]
    report = {
        "belt_limiter_physics": bm.belt_limiter_physics(),
        "timeline_monotone": tl.monotone_in_segment(segs),
        "belt_scene_alignment": tl.belt_scene_alignment(segs, beat_starts),
        "telemetry_matches_model": telemetry_matches_model(shots, segs),
        "visible_action": visible_action(shots, segs),
        "no_scene_text": no_scene_text_belt(),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "captions_visible": verify_captions_over_picture(video, frames, [((c["start"] + c["end"]) / 2, (1400, 1919)) for c in in_clip], a.out),
    }
    ok_status = ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING")
    report["preview_status"] = "PASS" if not problems and all(v["status"] in ok_status for v in report.values() if isinstance(v, dict) and "status" in v) else "FAIL"
    report.update(problems=problems, renderer_source_sha256=sha, frames=n, seconds=round(seconds, 3), narration_sha256=narration_sha,
                  not_applicable="EP.04 crumple geometry/energy gates and the shared scene-spec evidence gate are not applied to EP.05; scene alignment is checked against the segment table and the contact sheet",
                  note="preview only: not a deliverable, no upload; voice pronunciation, sound-off readability and human first view UNVERIFIED")
    (a.out / "belt-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("BELT_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items()}, default=str), flush=True)
    print("BELT_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    print("BELT_FILM_NUMBERS " + json.dumps({k: report[k] for k in ("belt_limiter_physics", "visible_action", "belt_scene_alignment")}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "96k", a.out / "belt-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
