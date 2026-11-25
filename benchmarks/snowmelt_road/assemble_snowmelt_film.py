"""EP.31: composes the rendered snow-melting-road film frames, builds the sound mix (frozen narration + effects placed from the world
model, snowmelt_sfx), burns in the narration captions and runs every gate that can be decided from the clip, including the pace rules
and the opening-hook rules (benchmarks/hook_gate.py). No text on the picture other than the captions. Never uploads."""
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
from benchmarks.snowmelt_road import snowmelt_motion as sm
from benchmarks.snowmelt_road import snowmelt_sfx as sfx
from benchmarks.snowmelt_road import snowmelt_timeline as tl
from benchmarks.snowmelt_road import snowmelt_world as w
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep31-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_snowmelt_3d.py").read_text()
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


def old_film(im: Image.Image) -> Image.Image:
    """Old sepia film for the "nineteen sixties" shot: grey tones tinted warm, a dark vignette, a fixed grain (the same on every frame,
    so it adds no flicker)."""
    a = np.asarray(im, dtype=np.float32) / 255.0
    g = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    g = 0.08 + 0.88 * g
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    r = np.hypot((xx - a.shape[1] / 2) / (a.shape[1] / 2), (yy - a.shape[0] / 2) / (a.shape[0] / 2))
    vig = 1.0 - 0.38 * np.clip(r - 0.45, 0.0, 1.0) ** 1.4
    grain = np.random.default_rng(1961).normal(0.0, 0.018, g.shape)
    g = np.clip(g * vig + grain, 0.0, 1.0)
    out = np.stack([g * 1.06 + 0.03, g * 0.86 + 0.015, g * 0.62], -1)
    return Image.fromarray((np.clip(out, 0.0, 1.0) * 255).astype(np.uint8))


def compose(panels: Path, out: Path, n: int) -> tuple[list[dict], str]:
    out.mkdir(parents=True, exist_ok=True)
    frames, sha = {}, None
    segs = tl.segments()
    for js in sorted(panels.rglob("snowmelt-frames-*.json")):
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
            if tl.frame_state(f, segs).get("vintage"):
                im = old_film(im)
            im.save(out / f"frame_{f + 1:04d}.png")
            frames[f] = fr
    if sorted(frames) != list(range(n)):
        raise SystemExit(f"rendered {len(frames)} frames, expected exactly frames 0..{n - 1}")
    return [frames[i] for i in range(n)], sha


def telemetry_matches_model(frames: list[dict], segs: list[dict]) -> dict:
    """Every frame was drawn from the world model at its story time: the jets' droplets (none on the newer road; only the near half
    in section shots), where the car is, how far the ground has sunk; the cut, the sinking and the pipes only where the timeline asks."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t = sh["t"]
        if abs(p["t"] - round(t, 6)) > 1e-6:
            problems.append(f"frame {fr['frame']}: story time differs")
            continue
        section, pipes = bool(sh.get("section")), bool(sh.get("pipes"))
        if p["section"] != section or p["pipes"] != pipes or abs(p["sink"] - round(sh["sink"], 6)) > 1e-6:
            problems.append(f"frame {fr['frame']}: the cut, the sinking or the pipes differ from the timeline")
        want = 0 if pipes else len(w.droplets(t, -1e9, 1e9, (-1.0,) if section else (-1.0, 1.0), sh["sink"] * w.SINK_MAX)[0])
        if p["droplets"] != want:
            problems.append(f"frame {fr['frame']}: {p['droplets']} droplets drawn, the jets have {want}")
        cy = None if section else w.car_y(t)
        if (p["car_y"] is None) != (cy is None) or (cy is not None and abs(p["car_y"] - cy) > 1e-3):
            problems.append(f"frame {fr['frame']}: the car is not where the model has it")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1: the street spraying water in falling snow, a car coming through the jets; then from above the snowy town down into
    the street to its nozzles, a nozzle up close, down the well to the warm water deep underground, flakes vanishing as they land in
    the water, the whole street as old film (the 1960s), snow falling past a thermometer at the freezing mark, the water landing and
    running off as water, a long row of jets, the ground sinking round the well, the newer road's warm pipes (no jets), the car
    driving off through the spray; the loop runs into the opening's moment (owner rule 2026-11-25: show exactly what each line says)."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["droplets"] > 0 and p0["car_y"] is not None and 5.0 < p0["car_y"] < 40.0 and p0["nozzles_in_view"] >= 20 and not p0["section"]):
        problems.append("the first frame is not the street spraying water with a car coming through")
    b = by.get("B-built-into-street", [])
    if not b or b[0]["cam_world"][2] < 30.0 or b[-1]["cam_world"][2] > 6.0 or (b[-1]["nearest_nozzle_m"] or 99.0) > 8.0:
        problems.append("the snowy town is not followed down into the street to its nozzles")
    c = by.get("C-nozzles-centre", [])
    if not c or max(p["nearest_nozzle_m"] or 99.0 for p in c) > 1.6:
        problems.append("no nozzle is shown up close")
    d = by.get("D-from-deep-underground", [])
    if not d or not all(p["section"] for p in d) or d[0]["cam_world"][2] < 0.0 or d[-1]["cam_world"][2] > -35.0:
        problems.append("the well is not followed deep underground")
    e = by.get("E-melts-as-it-lands", [])
    if not e or min(p["ripples"] for p in e) < 20 or min(p["flakes"] for p in e) < 500:
        problems.append("flakes are not seen landing in the water")
    f = by.get("F-nagaoka-street", [])
    if not f or min(p["nozzles_in_view"] for p in f) < 50:
        problems.append("the whole street is not shown")
    g1 = by.get("G1-near-freezing", [])
    if not g1 or min(p["flakes"] for p in g1) < 1000 or not all(p.get("thermometer") for p in g1):
        problems.append("the snow is not seen falling past a thermometer at the freezing mark")
    g2 = by.get("G2-stays-liquid", [])
    if not g2 or min(p["ripples"] for p in g2) < 50 or min(p["droplets"] for p in g2) == 0:
        problems.append("the water is not seen landing and running as water")
    h1 = by.get("H1-lots-of-water", [])
    if not h1 or min(p["nozzles_in_view"] for p in h1) < 40:
        problems.append("the long row of jets is not shown")
    h2 = by.get("H2-ground-sinks", [])
    if not h2 or not all(p["section"] for p in h2) or h2[0]["sink"] > 0.05 or h2[-1]["sink"] < 0.95:
        problems.append("the ground is not seen sinking round the well")
    i = by.get("I-pipes-under-pavement", [])
    if not i or not all(p["pipes"] and p["droplets"] == 0 for p in i):
        problems.append("the newer road's pipes are not shown")
    j = by.get("J-washes-snow-away", [])
    if not j or any(p["car_y"] is None for p in j) or j[-1]["car_y"] >= j[0]["car_y"]:
        problems.append("the car is not seen driving on through the spray")
    last = frames[-1]["parts"][0]
    if not (-0.5 < p0["t"] - last["t"] < 0.5):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "first_frame": {k_: p0[k_] for k_ in ("t", "car_y", "droplets", "nozzles_in_view", "subject_box")}}


def vintage_look(frames_dir: Path, segs: list[dict]) -> dict:
    """The "nineteen sixties" shot reads as old film (warm and nearly colourless); the shots on either side keep their colour."""
    problems, rows = [], []
    for s in segs:
        f = int((s["t0"] + s["t1"]) / 2 * tl.FPS)
        a = np.asarray(Image.open(frames_dir / f"frame_{f + 1:04d}.png").convert("RGB"), dtype=np.float32)
        mx, mn = a.max(axis=2), a.min(axis=2)
        sat = float(np.mean((mx - mn) / np.maximum(mx, 1.0)))
        warm = float(np.mean(a[..., 0]) - np.mean(a[..., 2]))
        old = bool(s["flags"].get("vintage"))
        rows.append({"segment": s["label"], "saturation": round(sat, 3), "warm": round(warm, 1), "vintage": old})
        if old and not (sat < 0.45 and warm > 15.0):
            problems.append(f"{s['label']} does not read as old sepia film")
    if not any(r["vintage"] for r in rows):
        problems.append("no shot is marked as the past")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "shots": rows}


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
    video = a.out / "snowmelt-film-1080x1920.mp4"
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
        "snowmelt_physics": sm.snowmelt_physics(),
        "pace": tl.pace(segs),
        "opening_hook": hook_gate.opening_hook(frames, segs, tl.line_starts()[1], tl.FPS),
        "scene_alignment": tl.scene_alignment(segs),
        "telemetry_matches_model": telemetry_matches_model(frames, segs),
        "visible_action": visible_action(frames),
        "no_scene_text": no_scene_text(),
        "vintage_look": vintage_look(frames_dir, segs),
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
    (a.out / "snowmelt-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("SNOWMELT_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("SNOWMELT_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "snowmelt-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
