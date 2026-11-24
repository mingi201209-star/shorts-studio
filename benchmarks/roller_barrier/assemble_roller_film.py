"""EP.26: composes the rendered rolling-barrier film frames, builds the sound mix (frozen narration + effects placed from the model,
roller_sfx), burns in the narration captions and runs every gate that can be decided from the clip, including the pace rules and the
opening-hook rules (benchmarks/hook_gate.py). No text on the picture other than the captions. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks import hook_gate
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.roller_barrier import roller_motion as rm
from benchmarks.roller_barrier import roller_sfx as sfx
from benchmarks.roller_barrier import roller_timeline as tl
from benchmarks.roller_barrier import roller_world as rw
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep26-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)
DYN_K = (-6, 22)                        # the roller pairs the renderer can move, as in the renderer


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_roller_3d.py").read_text()
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
    for js in sorted(panels.rglob("roller-frames-*.json")):
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
    """Every frame was drawn from the model state of its story time: the car's place, heading and wheel turn; the rollers' squash
    and the barrier's give (or the steel rail's); the sparks; the cut-open view only in section shots."""
    problems = []
    ys = (np.arange(*DYN_K) + 0.5) * rm.ROLL_PITCH
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t = sh["t"]
        if abs(p["t"] - round(t, 6)) > 1e-6 or p["variant"] != sh["variant"]:
            problems.append(f"frame {fr['frame']}: story time or variant differs")
            continue
        bar = "steel" if sh["variant"] == "steel" else "roller"
        if sh["variant"] != "still":
            q = rm.pose(t, bar)
            if abs(p["car_x"] - q["x"]) > 1e-3 or abs(p["car_y"] - q["y"]) > 1e-3 or abs(p["car_psi_deg"] - math.degrees(q["psi"])) > 1e-2:
                problems.append(f"frame {fr['frame']}: the car's place or heading differs from the model")
            if abs(p["wheel_angle"] - rm.wheel_angle(t, bar)) > 1e-3:
                problems.append(f"frame {fr['frame']}: the wheel turn differs from the model")
        elif p["car_visible"]:
            problems.append(f"frame {fr['frame']}: a car in a shot without one")
        sq, gv = rm.barrier_state(t, ys, bar) if sh["variant"] != "still" else (np.zeros(1), np.zeros(1))
        if bar == "roller" and (abs(p["max_squash"] - round(float(sq.max()), 4)) > 1e-3 or abs(p["max_give"] - round(float(gv.max()), 4)) > 1e-3):
            problems.append(f"frame {fr['frame']}: the rollers' squash or the barrier's give differ from the model")
        if bar == "steel" and (abs(p["rail_give"] - round(float(gv.max()), 4)) > 1e-3 or p["sparks"] != len(rm.spark_points(t))):
            problems.append(f"frame {fr['frame']}: the steel rail's give or the sparks differ from the model")
        if p["section"] != bool(sh.get("section")):
            problems.append(f"frame {fr['frame']}: cut-open view differs from the timeline")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1: the car pressed into the rollers, several of them spinning; then the car racing down to the sharp bend, the steel
    rail giving way and throwing sparks, a pair of rollers cut open (foam on a steel shaft), the car sliding in and the rollers
    spinning up, the foam squashing, a row of rollers whirling, the car rolling on at speed, back to the middle of its lane, the whole
    crash from straight above, the barrier along another bend; the loop runs into the opening's moment."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["car_visible"] and p0["max_squash"] > 0.05 and p0["rollers_spinning"] >= 3 and not p0["section"]):
        problems.append("the first frame is not the car pressed into spinning rollers")
    b = by.get("B-korean-curve", [])
    if not b or not all(p["car_visible"] and p["t"] < 0 for p in b) or b[-1]["car_y"] - b[0]["car_y"] < 20:
        problems.append("the car is not seen racing toward the bend")
    c = by.get("C-steel-scrapes", [])
    if not c or not all(p["variant"] == "steel" for p in c) or max(p["sparks"] for p in c) < 30 or max(p["rail_give"] for p in c) < 0.3:
        problems.append("the steel rail is not seen giving way with sparks")
    d = by.get("D-foam-on-posts", [])
    if not d or not all(p["section"] and not p["car_visible"] for p in d):
        problems.append("the cut-open rollers are not shown on their own")
    e = by.get("E-rollers-spin", [])
    if not e or e[0]["rollers_spinning"] > 0 or e[-1]["rollers_spinning"] < 5:
        problems.append("the rollers are not seen starting to spin as the car slides in")
    f = by.get("F-foam-squashes", [])
    if not f or max(p["max_squash"] for p in f) < 0.1:
        problems.append("the foam is not seen squashing")
    g = by.get("G-crash-into-rotation", [])
    if not g or min(p["rollers_spinning"] for p in g[-5:]) < 8:
        problems.append("a row of rollers is not seen whirling")
    h1 = by.get("H1-keeps-rolling", [])
    if not h1 or min(p["speed"] for p in h1) < 0.8 * rm.V0:
        problems.append("the car does not keep rolling at speed")
    h2 = by.get("H2-back-to-its-lane", [])
    if not h2 or not (h2[0]["car_x"] > h2[-1]["car_x"] and abs(h2[-1]["car_x"] - rm.LANE_X) < 0.5 and abs(h2[-1]["car_psi_deg"]) < 3.0):
        problems.append("the car is not seen back in its lane")
    i = by.get("I-62-mph-test", [])
    if not i or i[0]["t"] > -0.2 or i[-1]["t"] < 0.4 or not any(p["in_contact"] for p in i):
        problems.append("the whole crash is not shown")
    j = by.get("J-sixty-miles", [])
    if not j or any(p["car_visible"] for p in j):
        problems.append("the barrier along another bend is not shown on its own")
    k = by.get("K-loop", [])
    if not k or k[0]["t"] > -0.5 or not k[0]["car_visible"]:
        problems.append("the loop does not start with the car coming")
    last = frames[-1]["parts"][0]
    if not (-0.01 < p0["t"] - last["t"] < 0.002):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "first_frame": {k_: p0[k_] for k_ in ("t", "max_squash", "max_give", "rollers_spinning", "subject_box")}}


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
    video = a.out / "roller-film-1080x1920.mp4"
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
        "roller_physics": rm.roller_physics(),
        "world_layout": rw.lane_check(),
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
    (a.out / "roller-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("ROLLER_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("ROLLER_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "roller-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
