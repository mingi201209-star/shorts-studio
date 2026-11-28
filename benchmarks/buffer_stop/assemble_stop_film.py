"""EP.36: composes the rendered friction buffer stop film frames (the comparison shot's two panels stacked, the cab on top and the
car below), builds the sound mix (frozen narration in the channel's Bumper voice + effects placed from the model, stop_sfx, with the
channel's signature reveal sting), burns in the narration captions in the channel's caption look (benchmarks/identity/captions.py)
and runs every gate that can be decided from the clip.

Gates: physics, pace, opening hook, line alignment, telemetry, visible action, no scene text, smoothness, black opening, captions
(on the picture and within the width), audio. No loop gate: from EP.35 the end belongs to the next part's teaser (playbook section
10). No text on the picture other than the captions. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil

from pathlib import Path

from PIL import Image

from benchmarks import hook_gate
from benchmarks.buffer_stop import stop_motion as m
from benchmarks.buffer_stop import stop_sfx as sfx
from benchmarks.buffer_stop import stop_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.identity import captions
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep36-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    for src in ("render_stop_3d.py", "stop_parts.py"):
        txt = (Path(__file__).resolve().parent / src).read_text()
        problems += [f"renderer creates scene text ({b})" for b in ('"FONT"', "'FONT'", "body_text", "text_add") if b in txt]
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
    for js in sorted(panels.rglob("stop-frames-*.json")):
        rec = json.loads(js.read_text())
        if sha is None:
            sha = rec["renderer_source_sha256"]
        elif rec["renderer_source_sha256"] != sha:
            raise SystemExit("mixed renderer versions across shards")
        for fr in rec["frames"]:
            f = fr["frame"]
            names = [f"frame_{f:05d}_top.png", f"frame_{f:05d}_bot.png"] if fr["split"] else [f"frame_{f:05d}.png"]
            ims = []
            for name, part in zip(names, fr["parts"]):
                path = js.parent / name
                if hashlib.sha256(path.read_bytes()).hexdigest() != part["sha256"]:
                    raise SystemExit(f"hash mismatch {path}")
                ims.append(Image.open(path).convert("RGB"))
            if fr["split"]:
                im = Image.new("RGB", (W, H))
                im.paste(ims[0].resize((W, H // 2), Image.LANCZOS), (0, 0))
                im.paste(ims[1].resize((W, H // 2), Image.LANCZOS), (0, H // 2))
                im.paste((20, 20, 24), (0, H // 2 - 4, W, H // 2 + 4))
            else:
                im = ims[0].resize((W, H), Image.LANCZOS) if ims[0].size != (W, H) else ims[0]
            im.save(out / f"frame_{f + 1:04d}.png")
            frames[f] = fr
    if sorted(frames) != list(range(n)):
        raise SystemExit(f"rendered {len(frames)} frames, expected exactly frames 0..{n - 1}")
    return [frames[i] for i in range(n)], sha


def telemetry_matches_model(frames: list[dict], segs: list[dict]) -> dict:
    """Every frame was drawn from the model state of its simulated time: the train's front, the stop's slide and the buffers'
    squash; the wall what-if's train; the comparison car; afterwards, the stop between its slid place and its mark."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        t = sh["t"]
        for p in fr["parts"]:
            if abs(p["t"] - round(t, 6)) > 1e-6:
                problems.append(f"frame {fr['frame']}: simulated time differs")
                continue
            v = p["variant"]
            if v == "train":
                st = m.state(t)
                if any(abs(p[k] - st[k2]) > 1e-3 for k, k2 in (("train_y", "train_y"), ("stop_y", "stop_y"), ("compression", "compression"))):
                    problems.append(f"frame {fr['frame']}: the train, the stop or the buffers differ from the model")
            elif v == "wall":
                if abs(p["train_y"] - m.wall_state(t)["train_y"]) > 1e-3:
                    problems.append(f"frame {fr['frame']}: the what-if train differs from the model")
            elif v == "car":
                if abs(p["car_x"] - m.car_state(t - 0.25)["x"]) > 1e-3:
                    problems.append(f"frame {fr['frame']}: the car differs from the model")
            elif v == "crew":
                if not p.get("crew") or not -1e-3 <= p["stop_y"] <= m.impact()[-1][4] + 1e-3:          # recorded to 4 decimals
                    problems.append(f"frame {fr['frame']}: the crew or the stop's place is wrong")
            else:
                problems.append(f"frame {fr['frame']}: unknown variant {v}")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1 is the train already shoving the stop, buffers squashed, sparks off the shoes; the what-if train hits the wall and
    throws debris; the stop is seen at rest with the train coming; the reveal is in the x-ray look; the buffers squash in x-ray;
    the stop slides with sparks; the shoes slide hot in x-ray; the slide is laid out and the train stops at its end; the split
    shows the car thrown hard and the cab gentle; Bumper waves once stopped; the crew turns the bolts, then the stop goes back."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["variant"] == "train" and p0["sliding"] and p0["sparks"] >= 3 and p0["compression"] > 0.05):
        problems.append(f"the first frame is not the train already shoving the stop with sparks ({p0})")
    b1 = [ps[0] for ps in by.get("B1-wall", [])]
    if not b1 or b1[0]["hit"] or not b1[-1]["hit"] or max(p["debris"] for p in b1) < 10:
        problems.append("the what-if train is not seen hitting the wall and throwing debris")
    b2 = [ps[0] for ps in by.get("B2-built-to-slide", [])]
    if not b2 or any(p["stop_y"] != 0 for p in b2) or b2[-1]["train_y"] > -30:
        problems.append("the stop is not seen at rest with the train still far off")
    c = [ps[0] for ps in by.get("C-shoes", [])]
    if not c or not all(p["xray"] for p in c):
        problems.append("the shoes are not revealed in the x-ray look")
    d = [ps[0] for ps in by.get("D-buffers", [])]
    if not d or not all(p["xray"] for p in d) or d[0]["compression"] > 0 or max(p["compression"] for p in d) < 0.3:
        problems.append("the buffers are not seen squashing in the x-ray look")
    e1 = [ps[0] for ps in by.get("E1-shoved", [])]
    if not e1 or not all(p["sliding"] for p in e1) or e1[-1]["stop_y"] <= e1[0]["stop_y"] + 3 or min(p["sparks"] for p in e1) < 3:
        problems.append("the stop is not seen shoved along the rails with sparks")
    e2 = [ps[0] for ps in by.get("E2-heat", [])]
    if not e2 or not all(p["xray"] and p["sliding"] for p in e2):
        problems.append("the shoes are not seen sliding in the x-ray look")
    f = [ps[0] for ps in by.get("F-sixty-feet", [])]
    if not f or not all(p["marker"] for p in f) or f[-1]["train_speed"] > 0 or abs(f[-1]["stop_y"] - m.impact()[-1][4]) > 0.05:
        problems.append("the slide is not laid out with the train stopped at its end")
    g = by.get("G-gentler", [])
    if not g or not all(len(ps) == 2 for ps in g) or max(ps[1]["car_lean"] for ps in g) < 0.5 or max(ps[0]["driver_lean"] for ps in g) > 0.25 \
            or max(ps[1]["car_decel_g"] for ps in g) < m.CAR_HARD_BRAKING_G:
        problems.append("the split does not show the car thrown hard and the cab gentle")
    h = [ps[0] for ps in by.get("H-thats-me", [])]
    if not h or not all(p["cab"] for p in h) or max(p["wave"] for p in h) < 0.99 or any(p["train_speed"] > 0 for p in h):
        problems.append("Bumper is not seen waving from the stopped cab")
    i1 = [ps[0] for ps in by.get("I1-loosen", [])]
    if not i1 or not all(p.get("crew") for p in i1) or i1[0]["nut_turn"] == i1[-1]["nut_turn"]:
        problems.append("the crew is not seen turning the shoe bolts")
    i2 = [ps[0] for ps in by.get("I2-push-back", [])]
    if not i2 or not all(p.get("push") for p in i2) or i2[-1]["stop_y"] > 0.3 or i2[0]["stop_y"] < 15:
        problems.append("the stop is not seen pushed back to its mark")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_frame": p0}


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
    ass_text = captions.restyle((AUDIO_DIR / "film.ass").read_text(encoding="utf8"))
    ass.write_text(ass_text, encoding="utf8")
    widest = captions.widest_line_px(ass_text)
    video = a.out / "stop-film-1080x1920.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(tl.FPS), "-i", str(frames_dir / "frame_%04d.png"), "-i", str(a.out / "mix.wav"),
         "-vf", f"setpts=N/({tl.FPS}*TB),{captions.ass_filter(ass)}", "-af", "apad", "-map", "0:v:0", "-map", "1:a:0", "-t", f"{seconds}", "-r", str(tl.FPS),
         "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", video])
    info = probe_video(video)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    problems = []
    if (vs["width"], vs["height"], int(vs["nb_read_frames"])) != (W, H, n):
        problems.append(f"video is {vs['width']}x{vs['height']} with {vs['nb_read_frames']} frames, expected {n}")
    cues = [c for c in audio["cues"] if c["end"] <= seconds - 0.1]
    cap = verify_captions_over_picture(video, frames_dir, [((c["start"] + c["end"]) / 2, CAPTION_BAND) for c in cues], a.out, fps=tl.FPS)
    if widest > captions.MAX_LINE_PX:
        cap = {"status": "FAIL", "reason": f"a caption line is {widest:.0f} px wide (max {captions.MAX_LINE_PX})", **cap}
    cap["widest_line_px"] = round(widest)
    report = {
        "stop_physics": m.stop_physics(),
        "pace": tl.pace(segs),
        "opening_hook": hook_gate.opening_hook(frames, segs, tl.line_starts()[1], tl.FPS),
        "scene_alignment": tl.scene_alignment(segs),
        "telemetry_matches_model": telemetry_matches_model(frames, segs),
        "visible_action": visible_action(frames),
        "no_scene_text": no_scene_text(),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "captions_visible": cap,
        "audio_mix": audio_mix(levels),
    }
    report["preview_status"] = "PASS" if not problems and all(v["status"] in ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING") for v in report.values() if isinstance(v, dict) and "status" in v) else "FAIL"
    report.update(problems=problems, renderer_source_sha256=sha, frames=n, seconds=round(seconds, 3), narration_sha256=narration_sha,
                  loop="none: the end belongs to the next part's teaser (playbook section 10)",
                  segments=[{k: s[k] for k in ("label", "t0", "t1", "sim0", "sim1", "time_scale")} for s in segs],
                  note="preview only: nothing uploaded; the sound mix and voice are not human-checked; a human first view UNVERIFIED")
    (a.out / "stop-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("STOP_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("STOP_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "stop-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
