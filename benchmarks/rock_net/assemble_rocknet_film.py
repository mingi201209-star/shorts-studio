"""EP.21: composes the rendered rockfall-net film frames, builds the sound mix (frozen narration + effects placed from the model,
rocknet_sfx), burns in the narration captions and runs every gate that can be decided from the clip, including the pace rules and the
opening-hook rules (benchmarks/hook_gate.py). No text on the picture other than the captions. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks import hook_gate
from benchmarks.rock_net import rocknet_motion as rm
from benchmarks.rock_net import rocknet_sfx as sfx
from benchmarks.rock_net import rocknet_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep21-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_rocknet_3d.py").read_text()
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
    for js in sorted(panels.rglob("rocknet-frames-*.json")):
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


def sstep(e0, e1, x):
    u = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return u * u * (3 - 2 * u)


def expected(t: float, variant: str) -> dict:
    """The model state the renderer must have drawn (the clean-up time-lapse blends the end state back to the rest state)."""
    if variant == "restore":
        f = min(1.0, max(0.0, t))
        relax = sstep(0.40, 0.80, f)
        grow = sstep(0.62, 0.90, f)
        return {"w": rm.deflection(30.0) * (1 - relax), "lean": rm.post_lean(30.0) * (1 - relax), "rock_scale": 1.0 - sstep(0.0, 0.45, f),
                "loop_r": rm.loop_radius(30.0) + (rm.LOOP_R0 - rm.loop_radius(30.0)) * grow, "slip": rm.brake_slip(30.0) * (1 - grow),
                "power": 0.0, "rock": rm.rock_center(30.0)}
    return {"w": rm.deflection(t), "lean": rm.post_lean(t), "rock_scale": 1.0, "loop_r": rm.loop_radius(t), "slip": rm.brake_slip(t),
            "power": rm.brake_power(t), "rock": rm.rock_center(t)}


def telemetry_matches_model(frames: list[dict], segs: list[dict]) -> dict:
    """Every frame was drawn from the model state of its simulated time: net deflection, the rock's position, brake slip and loop
    size, post lean, brake power; the clean-up blend in the time-lapse."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t, v = sh["t"], sh["variant"]
        if abs(p["t"] - round(t, 6)) > 1e-6 or p["variant"] != v:
            problems.append(f"frame {fr['frame']}: simulated time or variant differs")
            continue
        e = expected(t, v)
        if abs(p["w"] - e["w"]) > 1e-3 or abs(p["lean"] - e["lean"]) > 1e-4 or abs(p["rock_scale"] - e["rock_scale"]) > 1e-3:
            problems.append(f"frame {fr['frame']}: net deflection, post lean or rock differ from the model")
        if abs(p["loop_r"] - e["loop_r"]) > 1e-3 or abs(p["slip"] - e["slip"]) > 1e-3 or abs(p["power"] - e["power"]) > 1.0:
            problems.append(f"frame {fr['frame']}: brake state differs from the model")
        if max(abs(a - b) for a, b in zip(p["rock"], e["rock"])) > 1e-3:
            problems.append(f"frame {fr['frame']}: rock position differs from the model")
        cy = tl.car_y(sh)
        if (cy is None) != (p["car_y"] is None) or (cy is not None and abs(cy - p["car_y"]) > 1e-3):
            problems.append(f"frame {fr['frame']}: car position differs from the timeline")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1: the boulder already deep in the net with chips in the air; the road and car with the rock coming; the rings close up
    before the hit; the hit; the net stretching past twenty feet against its rest outline; the brakes running and their loops
    shrinking and glowing; the rock at rest with nothing broken; the clean-up; the loop runs into the opening's moment."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["w"] >= 2.0 and p0["chips_airborne"] >= 5):
        problems.append(f"the first frame is not the rock in the net with chips flying ({p0['w']} m, {p0['chips_airborne']} chips)")
    b = by.get("B-nets-above-the-road", [])
    if not b or any(p["car_y"] is None for p in b) or b[-1]["t"] >= 0:
        problems.append("the road shot does not show the car with the rock still coming")
    c = by.get("C-chain-mail-rings", [])
    if not c or c[-1]["t"] >= 0 or c[-1]["w"] > 0:
        problems.append("the rings are not shown before the hit")
    d = by.get("D-not-stopped-dead", [])
    if not d or d[0]["w"] > 0 or d[-1]["w"] < 3.0:
        problems.append("the hit is not seen")
    e = by.get("E-stretches-twenty-feet", [])
    if not e or not all(p["ghost"] for p in e) or max(p["w"] for p in e) < 20 * rm.FT:
        problems.append("the stretch past twenty feet is not shown against the rest outline")
    g = by.get("G-loops-shrink-heat", [])
    if not g or g[0]["loop_r"] - g[-1]["loop_r"] < 0.1 or not any(p["power"] > 0 for p in g):
        problems.append("the brake loops are not seen shrinking and heating")
    f = by.get("F-brake-rings", [])
    if not f or f[-1]["slip"] <= f[0]["slip"]:
        problems.append("the brakes are not seen starting to run")
    h = by.get("H-nothing-snaps", [])
    if not h or h[-1]["t"] < rm.stop_time() or h[-1]["w"] < 20 * rm.FT:
        problems.append("the rock is not seen at rest in the net")
    j = by.get("J-replace-the-brakes", [])
    if not j or j[-1]["rock_scale"] > 0.01 or j[-1]["w"] > 0.01 or abs(j[-1]["loop_r"] - rm.LOOP_R0) > 1e-3:
        problems.append("the clean-up (rock cleared, net back, new brakes) is not seen")
    last = frames[-1]["parts"][0]
    if not (last["variant"] == p0["variant"] and -0.01 < p0["t"] - last["t"] < 0.002):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_frame": {k: p0[k] for k in ("t", "w", "chips_airborne", "subject_box")}}


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
    video = a.out / "rocknet-film-1080x1920.mp4"
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
        "rocknet_physics": rm.rocknet_physics(),
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
    (a.out / "rocknet-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("ROCKNET_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("ROCKNET_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "rocknet-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
