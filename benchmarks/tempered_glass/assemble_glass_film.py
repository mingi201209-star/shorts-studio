"""EP.14: composes the rendered tempered-glass film frames, builds the sound mix (frozen narration + effects placed from the model,
glass_sfx), burns in the narration captions and runs every gate that can be decided from the clip, including the pace rules from the
competitor research (first cut by 1.5 s, cuts and words per minute). No text on the picture other than the captions. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.tempered_glass import glass_motion as gm
from benchmarks.tempered_glass import glass_sfx as sfx
from benchmarks.tempered_glass import glass_timeline as tl
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep14-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_glass_3d.py").read_text()
    problems += [f"renderer creates scene text ({b})" for b in ('"FONT"', "'FONT'", "body_text", "text_add") if b in src]
    me = Path(__file__).read_text()
    problems += [f"assembly draws text ({b})" for b in ("ImageDraw", "ImageFont", ".text(") if me.count(b) > 1]      # once here, in this list
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def probe_video(video: Path) -> dict:
    if shutil.which("ffprobe"):
        return probe(video)
    import cv2
    cap = cv2.VideoCapture(str(video))
    n, w, h = 0, 0, 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        n += 1
        h, w = fr.shape[:2]
    cap.release()
    return {"streams": [{"codec_type": "video", "width": w, "height": h, "nb_read_frames": str(n), "counted_by": "opencv decode"}]}


def compose(panels: Path, out: Path, n: int) -> tuple[list[dict], str]:
    out.mkdir(parents=True, exist_ok=True)
    frames, sha = {}, None
    for js in sorted(panels.rglob("glass-frames-*.json")):
        rec = json.loads(js.read_text())
        if sha is None:
            sha = rec["renderer_source_sha256"]
        elif rec["renderer_source_sha256"] != sha:
            raise SystemExit("mixed renderer versions across shards")
        for fr in rec["frames"]:
            f = fr["frame"]
            path = js.parent / f"frame_{f:05d}.png"
            if hashlib.sha256(path.read_bytes()).hexdigest() != fr["parts"][0]["sha256"]:
                raise SystemExit(f"hash mismatch {path}")
            im = Image.open(path).convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            im.save(out / f"frame_{f + 1:04d}.png")
            frames[f] = fr
    if sorted(frames) != list(range(n)):
        raise SystemExit(f"rendered {len(frames)} frames, expected exactly frames 0..{n - 1}")
    return [frames[i] for i in range(n)], sha


def telemetry_matches_model(frames: list[dict], segs: list[dict]) -> dict:
    """Every frame was drawn from the model state of its simulated time (crack state, hammer, pane, ball, windshield cracks)."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t = sh["t"]
        if abs(p["t"] - round(t, 7)) > 1e-6 or p["variant"] != sh["variant"]:
            problems.append(f"frame {fr['frame']}: simulated time or variant differs")
        elif p["variant"] == "tempered":
            if p["hammer_angle"] is None or abs(p["hammer_angle"] - gm.hammer_angle(t)) > 1e-3:
                problems.append(f"frame {fr['frame']}: hammer differs from the model")
            if t >= 0:
                _, _, cracked = gm.piece_state(t)
                if abs(p["cracked_fraction"] - float(cracked.mean())) > 2e-3:
                    problems.append(f"frame {fr['frame']}: crack front differs from the model")
        elif p["variant"] == "quench" and abs(p["pane_y"] - (-0.35 + gm.PANE_SPEED * t)) > 2e-3:
            problems.append(f"frame {fr['frame']}: pane position differs from the model")
        elif p["variant"] == "ball" and abs(p["ball_h"] - gm.ball_state(t)[0]) > 2e-3:
            problems.append(f"frame {fr['frame']}: ball differs from the model")
        elif p["variant"] == "windshield" and abs(p["ws_crack_m"] - max(0.0, t) * gm.V_CRACK) > 2e-3:
            problems.append(f"frame {fr['frame']}: windshield crack differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1 is already the burst; the crack front is seen part-way across the pane; the cubes reach the road; the ball bounces off the
    tempered pane; the windshield cracks but stays; the ordinary pane breaks into shards; the loop ends on the hammer's touch."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0.get("released") and p0.get("cracked_fraction", 0) > 0.99):
        problems.append(f"the first frame is not the burst ({p0})")
    part = [p["cracked_fraction"] for k in ("E2-lets-go", "F-mile-per-second") for p in by.get(k, []) if "cracked_fraction" in p]
    if not any(0.1 < c < 0.9 for c in part):
        problems.append("the crack front is never seen part-way across the pane")
    g1 = by.get("G1-blunt-cubes", [])
    if not g1 or g1[-1].get("landed_fraction", 0) < 0.5:
        problems.append("the cubes do not reach the road in the cube shot")
    d = by.get("D-four-times", [])
    hs = [p["ball_h"] for p in d]
    if not hs or min(hs) > 0.01 or max(hs[hs.index(min(hs)):]) < 0.05:
        problems.append("the steel ball does not bounce off the tempered pane")
    h = by.get("H-windshield", [])
    if not h or h[-1]["ws_crack_m"] < 0.2:
        problems.append("the windshield star does not form")
    if not any(p["variant"] == "annealed" and p["t"] > 0.1 for p in by.get("G2-knife-shards", [])):
        problems.append("the ordinary pane is not shown breaking into shards")
    if frames[-1]["parts"][0]["t"] < 0:
        problems.append("the loop does not end on the hammer's touch")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_frame": p0}


def loop_closes(frames_dir: Path, n: int) -> dict:
    """The seam last -> first is as smooth as the steps right next to it (jump <= 1.5 x the larger neighbouring step)."""
    import numpy as np

    def g(i):
        return np.asarray(Image.open(frames_dir / f"frame_{i:04d}.png").convert("L"), dtype=np.float32)

    before = float(np.abs(g(n) - g(n - 1)).mean())
    after = float(np.abs(g(2) - g(1)).mean())
    jump = float(np.abs(g(n) - g(1)).mean())
    return {"status": "PASS" if jump <= 1.5 * max(before, after) else "FAIL", "mean_abs_diff_last_vs_first": round(jump, 2),
            "step_before_seam": round(before, 2), "step_after_seam": round(after, 2)}


def audio_mix(levels: dict) -> dict:
    """Loudness for Shorts, no clipping, and every line clearly above the effects."""
    problems = []
    if not -16.5 <= levels["mix_lufs"] <= -13.5:
        problems.append(f"mix loudness {levels['mix_lufs']} LUFS outside -16.5..-13.5")
    if levels["mix_true_peak_dbfs"] > -1.0:
        problems.append(f"true peak {levels['mix_true_peak_dbfs']} dBFS above -1")
    if levels["speech_over_effects_db_min"] < 8.0:
        problems.append(f"a line is only {levels['speech_over_effects_db_min']} dB above the effects")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, **levels}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames-dir", type=Path, default=None)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    frames_dir = a.frames_dir or (a.out / "frames")
    segs = tl.segments()
    n = tl.frame_count()
    frames, sha = compose(a.panels, frames_dir, n)
    audio = json.loads((AUDIO_DIR / "audio-validation.json").read_text())
    narration_sha = hashlib.sha256((AUDIO_DIR / "narration.wav").read_bytes()).hexdigest()
    if narration_sha != audio["narration_sha256"]:
        raise SystemExit("narration.wav differs from the frozen audio")
    seconds = n / tl.FPS
    levels = sfx.build(AUDIO_DIR / "narration.wav", a.out, seconds)
    ass = a.out / "film.ass"
    text = (AUDIO_DIR / "film.ass").read_text(encoding="utf8")
    style = ",0,0,1,3,0,2,90,90,210,1"
    if text.count(style) != 1:
        raise SystemExit("caption style line not in the expected form")
    ass.write_text(text.replace(style, ",0,0,1,6,2,2,90,90,420,1"), encoding="utf8")      # EP.05 caption look: thick outline, above the bottom UI
    video = a.out / "glass-film-1080x1920.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(tl.FPS), "-i", str(frames_dir / "frame_%04d.png"), "-i", str(a.out / "mix.wav"),
         "-vf", f"setpts=N/({tl.FPS}*TB),ass={ass}", "-af", "apad", "-map", "0:v:0", "-map", "1:a:0", "-t", f"{seconds}", "-r", str(tl.FPS), "-c:v", "libx264",
         "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", video])
    info = probe_video(video)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    problems = []
    if (vs["width"], vs["height"], int(vs["nb_read_frames"])) != (W, H, n):
        problems.append(f"video is {vs['width']}x{vs['height']} with {vs['nb_read_frames']} frames, expected {n}")
    cues = [c for c in audio["cues"] if c["end"] <= seconds - 0.1]
    report = {
        "glass_physics": gm.glass_physics(),
        "pace": tl.pace(segs),
        "scene_alignment": tl.scene_alignment(segs),
        "telemetry_matches_model": telemetry_matches_model(frames, segs),
        "visible_action": visible_action(frames),
        "no_scene_text": no_scene_text(),
        "loop_closes": loop_closes(frames_dir, n),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "captions_visible": verify_captions_over_picture(video, frames_dir, [((c["start"] + c["end"]) / 2, CAPTION_BAND) for c in cues], a.out, fps=tl.FPS),
        "audio_mix": audio_mix(levels),
    }
    report["preview_status"] = "PASS" if not problems and all(v["status"] in ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING") for v in report.values() if isinstance(v, dict) and "status" in v) else "FAIL"
    report.update(problems=problems, renderer_source_sha256=sha, frames=n, seconds=round(seconds, 3), narration_sha256=narration_sha,
                  segments=[{k: s[k] for k in ("label", "t0", "t1", "sim0", "sim1", "time_scale")} for s in segs],
                  note="preview only: nothing uploaded; the sound mix and voice are not human-checked; a human first view UNVERIFIED")
    (a.out / "glass-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("GLASS_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("GLASS_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "glass-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
