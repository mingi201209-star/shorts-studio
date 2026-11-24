"""EP.27: composes the rendered submersible-bridge film frames, builds the sound mix (frozen narration + effects placed from the model,
sinking_sfx), burns in the narration captions and runs every gate that can be decided from the clip, including the pace rules and
the opening-hook rules (benchmarks/hook_gate.py). No text on the picture other than the captions. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks import hook_gate
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from benchmarks.submersible_bridge import sinking_motion as sm
from benchmarks.submersible_bridge import sinking_sfx as sfx
from benchmarks.submersible_bridge import sinking_timeline as tl
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep27-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_sinking_3d.py").read_text()
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
    for js in sorted(panels.rglob("sinking-frames-*.json")):
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
    """Every frame was drawn from the model state of its story time: the deck's height and speed, the gates and their lights, the
    ship's place, how wet the road is; the lift bridge only in its shot, under-water shots under water."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t = sh["t"]
        if abs(p["t"] - round(t, 6)) > 1e-6:
            problems.append(f"frame {fr['frame']}: story time differs")
            continue
        if abs(p["deck_z"] - sm.deck_z(t)) > 1e-3 or abs(p["deck_speed"] - sm.deck_speed(t)) > 1e-4:
            problems.append(f"frame {fr['frame']}: the deck differs from the model")
        if abs(p["gates_down"] - sm.gates_down(t)) > 1e-3 or p["lights"] != sm.lights_on(t):
            problems.append(f"frame {fr['frame']}: the gates differ from the model")
        if abs(p["ship_bow_y"] - sm.ship_bow_y(t)) > 1e-2 or p["ship_over_deck"] != sm.ship_over_deck(t) or abs(p["wet"] - sm.wet(t)) > 1e-3:
            problems.append(f"frame {fr['frame']}: the ship or the wet road differ from the model")
        if p["ghost"] != bool(sh.get("ghost")) or p["under"] != bool(sh.get("under")):
            problems.append(f"frame {fr['frame']}: the lift bridge or the under-water view differ from the timeline")
        if p["under"] and not p["cam_world"][2] < -0.3:
            problems.append(f"frame {fr['frame']}: an under-water shot with the camera above the water")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1: the sea flooding over the road behind the closed gates; then the canal cut from above, a gate coming down in front of
    the waiting car, the deck sinking all the way under water, its end sliding down past the depth bands at the model's speed, the
    deck settling in a cloud of silt, the ship's hull passing over the drowned road, its masts going by with nothing over them, the
    towers a lift bridge would need, the ship going on, the road rising out of the water with water pouring off it; the loop runs
    into the opening's moment."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (-0.6 < p0["deck_z"] < 0.0 and p0["foam"] > 0.3 and p0["gates_down"] > 0.99 and not p0["under"]):
        problems.append(f"the first frame is not the sea flooding over the road behind closed gates ({p0['deck_z']}, {p0['foam']})")
    b = by.get("B-corinth-canal", [])
    if not b or min(p["cam_world"][2] for p in b) < 40:
        problems.append("the canal is not shown from above")
    c = by.get("C-gates-stop-traffic", [])
    if not c or c[0]["gates_down"] > 0.2 or c[-1]["gates_down"] < 0.99:
        problems.append("a gate is not seen coming down")
    d = by.get("D-sinks-26-feet", [])
    if not d or not all(p["under"] for p in d) or d[0]["deck_z"] - d[-1]["deck_z"] < sm.Z_UP - sm.Z_DOWN - 0.1:
        problems.append("the whole road is not seen sinking under water")
    e = by.get("E-13-feet-a-minute", [])
    if not e or abs((e[-1]["deck_z"] - e[0]["deck_z"]) / (e[-1]["t"] - e[0]["t"]) * 60 + 4.0) > 0.4:
        problems.append("the deck is not seen going down at about 4 m (13 ft) a minute")
    f = by.get("F-on-the-bottom", [])
    if not f or abs(f[-1]["deck_z"] - sm.Z_DOWN) > 1e-3 or max(p["silt"] for p in f) < 5:
        problems.append("the deck is not seen settling on the bottom")
    g = by.get("G-ships-sail-over", [])
    if not g or not all(p["under"] for p in g) or not any(p["ship_over_deck"] for p in g):
        problems.append("the ship is not seen passing over the drowned road")
    h = by.get("H-no-mast-too-tall", [])
    if not h or not any(p["ship_over_deck"] for p in h) or max(p["deck_z"] for p in h) > -sm.SHIP_DRAFT - 1.0:
        problems.append("the masts are not seen going over the sunken road")
    i = by.get("I-lift-bridge-towers", [])
    if not i or not all(p["ghost"] for p in i):
        problems.append("the lift bridge's towers are not shown")
    j1 = by.get("J1-ship-passed", [])
    if not j1 or j1[-1]["ship_bow_y"] - sm.SHIP_L < sm.DECK_W / 2:
        problems.append("the ship is not seen going on past the bridge")
    j2 = by.get("J2-rises-dripping", [])
    if not j2 or j2[0]["deck_z"] > 0.0 or j2[-1]["deck_z"] < 0.5 or max(p["falls"] for p in j2) < 0.3:
        problems.append("the road is not seen rising out of the water, dripping")
    k = by.get("K-loop", [])
    if not k or k[0]["gates_down"] < 0.99 or k[0]["deck_z"] < sm.Z_UP - 1e-3:
        problems.append("the loop does not start with the road up behind closed gates")
    last = frames[-1]["parts"][0]
    if not (-0.05 < p0["t"] - last["t"] < 0.01):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "first_frame": {k_: p0[k_] for k_ in ("t", "deck_z", "foam", "gates_down", "subject_box")}}


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
    video = a.out / "sinking-film-1080x1920.mp4"
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
        "sinking_physics": sm.sinking_physics(),
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
    (a.out / "sinking-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("SINKING_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("SINKING_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "sinking-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
