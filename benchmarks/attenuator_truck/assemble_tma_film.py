"""EP.32: composes the rendered truck-mounted-attenuator film frames, builds the sound mix (frozen narration + effects placed from the
model, tma_sfx, with the channel's signature reveal sting), burns in the narration captions and runs every gate that can be decided
from the clip (physics, pace, opening hook, line alignment, telemetry, visible action, no scene text, loop, smoothness, black opening,
captions, audio). No text on the picture other than the captions. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil

import numpy as np
from pathlib import Path

from PIL import Image

from benchmarks import hook_gate
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.attenuator_truck import tma_motion as m
from benchmarks.attenuator_truck import tma_sfx as sfx
from benchmarks.attenuator_truck import tma_timeline as tl
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep32-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_tma_3d.py").read_text()
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
    for js in sorted(panels.rglob("tma-frames-*.json")):
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
    """Every frame was drawn from the model state of its simulated time (vehicle position, the cushion's crush and fold, the truck's
    roll, the row-by-row crush of the three blocks, debris)."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t, v = sh["t"], sh["variant"]
        if abs(p["t"] - round(t, 6)) > 1e-6 or p["variant"] != v:
            problems.append(f"frame {fr['frame']}: simulated time or variant differs")
            continue
        if v == "deploy":
            if abs(p["fold_deg"] - math.degrees(m.fold_angle(t))) > 1e-2:
                problems.append(f"frame {fr['frame']}: fold angle differs from the model")
        else:
            st = m.vehicle_state(t, v == "pickup")
            y = p["pickup_y"] if v == "pickup" else p["car_y"]
            if abs(y - st["y"]) > 1e-3 or abs(p["crush"] - st["crush"]) > 1e-3 or abs(p["roll"] - st["roll"]) > 1e-3:
                problems.append(f"frame {fr['frame']}: vehicle, crush or roll differs from the model")
            if any(abs(a - b) > 1e-3 for a, b in zip(p["stage_crush"], m.stage_crush(st["crush"]))):
                problems.append(f"frame {fr['frame']}: the rows' crush differs from the model")
            if v == "car" and p["airborne"] != m.airborne_count(t):
                problems.append(f"frame {fr['frame']}: debris differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1 is the car already crushing into the cushion with pieces in the air; the truck is seen parked in the lane before the
    hit; the cushion is seen swinging down from upright; the reveal opens the cushion and slides the blocks apart; the rows are seen
    crushing one after another; the uncrushed outline is drawn while the car stops about eight feet in; the braked truck is seen
    shoved a few feet with tyre marks; the test pickup is stopped inside the stroke; the loop runs into the opening's moment."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["variant"] == "car" and p0["crush"] > 0.5 and p0["airborne"] >= 8):
        problems.append(f"the first frame is not the car crushing into the cushion with pieces flying ({p0})")
    b = by.get("B-shield", [])
    if not b or max(p["t"] for p in b) >= 0 or any(p["fold_deg"] > 1e-6 for p in b):
        problems.append("the truck is not seen parked with its cushion down before the hit")
    c = by.get("C-folds-down", [])
    if not c or c[0]["fold_deg"] < 85 or c[-1]["fold_deg"] > 1:
        problems.append("the cushion is not seen swinging down from upright to level")
    d = by.get("D-honeycomb", [])
    if not d or not all(p["cut"] for p in d) or d[-1]["explode"] < 0.4:
        problems.append("the reveal does not open the cushion and slide the blocks apart")
    e = by.get("E-row-by-row", [])
    if not e or e[-1]["stage_crush"][2] < 0.05 or not all(p["cut"] for p in e):
        problems.append("the rows are not seen crushing one after another, cut open")
    f = by.get("F-eight-feet", [])
    if not f or not all(p["ghost"] for p in f) or not 7.0 <= max(p["crush"] for p in f) / m.FT <= 9.0:
        problems.append("the uncrushed outline is not drawn while the car crushes about eight feet")
    g = by.get("G1-braked", []) + by.get("G2-few-feet", [])
    if not g or not 3.0 <= g[-1]["roll"] / m.FT <= 6.5:
        problems.append("the braked truck is not seen shoved a few feet")
    h = by.get("H-pickup", [])
    if not h or h[-1]["variant"] != "pickup" or not 0.8 * m.STROKE < max(p["crush"] for p in h) < m.STROKE:
        problems.append("the test pickup is not seen stopped inside the stroke")
    last = frames[-1]["parts"][0]
    if not (last["variant"] == "car" and 0 < last["t"] <= p0["t"] + 1e-9):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_frame": p0}


def loop_closes(frames_dir: Path, n: int) -> dict:
    """The seam last -> first is as smooth as the steps right next to it (jump <= 1.5 x the larger neighbouring step)."""
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
    video = a.out / "tma-film-1080x1920.mp4"
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
        "tma_physics": m.tma_physics(),
        "pace": tl.pace(segs),
        "opening_hook": hook_gate.opening_hook(frames, segs, tl.line_starts()[1], tl.FPS),
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
    (a.out / "tma-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("TMA_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("TMA_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "tma-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
