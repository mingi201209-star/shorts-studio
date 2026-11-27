"""EP.35: composes the rendered carrier arresting-wire film frames, builds the sound mix (frozen narration in the channel's Bumper
voice + effects placed from the model, wire_sfx, with the channel's signature reveal sting), burns in the narration captions in the
channel's caption look (benchmarks/identity/captions.py) and runs every gate that can be decided from the clip.

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
from benchmarks.carrier_wire import wire_motion as m
from benchmarks.carrier_wire import wire_sfx as sfx
from benchmarks.carrier_wire import wire_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.identity import captions
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep35-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    for src in ("render_wire_3d.py",):
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
    for js in sorted(panels.rglob("wire-frames-*.json")):
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
    """Every frame was drawn from the model state of its simulated time: the hook's position past the wire, the cable payout and
    the ram's travel (the crew shots: no jet, the crew at the wire)."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t, v = sh["t"], sh["variant"]
        if abs(p["t"] - round(t, 6)) > 1e-6 or p["variant"] != v:
            problems.append(f"frame {fr['frame']}: simulated time or variant differs")
            continue
        if v == "crew":
            if not p.get("crew"):
                problems.append(f"frame {fr['frame']}: the crew is missing")
        else:
            st = m.jet_state(t)
            if abs(p["d"] - st["d"]) > 1e-3 or abs(p["payout"] - st["payout"]) > 1e-3 or abs(p["ram"] - st["ram"]) > 1e-3:
                problems.append(f"frame {fr['frame']}: the jet, the cable or the ram differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1 is the jet already caught, the wire stretched, sparks at the hook; the jet is seen coming in; the hook swings down; the
    hook is seen catching the wire; the reveal and the engine shots are in the x-ray look with the ram moving and the oil flowing;
    the jet is seen stopped over a football field's length; the engines are at full power; Bumper is in the cockpit and gives a
    thumbs up after the stop; the crew unhooks the worn wire and drags it away."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["variant"] == "jet" and p0["d"] > 5.0 and p0["payout"] > 0.5 and p0["sparks"] >= 3):
        problems.append(f"the first frame is not the jet already caught with sparks at the hook ({p0})")
    b1 = by.get("B1-short-deck", [])
    if not b1 or max(p["t"] for p in b1) >= m.stop_time() * 0 + -0.35 or b1[-1]["hook_y"] <= b1[0]["hook_y"]:
        problems.append("the jet is not seen coming in to the deck")
    c = by.get("C-snags-third", [])
    if not c or c[0]["d"] >= 0 or c[-1]["d"] <= 0:
        problems.append("the hook is not seen catching the wire")
    x = by.get("D-below-deck", []) + by.get("E1-piston", []) + by.get("E2-valve-heat", [])
    if not x or not all(p["xray"] for p in x) or x[-1]["ram"] <= x[0]["ram"] or max(p["oil_flow"] for p in x) <= 0:
        problems.append("the engine is not shown in the x-ray look with the ram moving and the oil flowing")
    f = by.get("F-football-field", [])
    if not f or not all(p["field"] for p in f) or f[-1]["speed"] > 0 or abs(f[-1]["d"] / m.FT - m.RUNOUT_FT) > 5:
        problems.append("the jet is not seen stopped over the football field")
    g = by.get("G-full-throttle", [])
    if not g or not all(p["full_power"] for p in g):
        problems.append("the engines are not at full power")
    h = by.get("H-thats-me", [])
    if not h or not all(p["cockpit"] for p in h) or max(p["thumbs_up"] for p in h) < 0.99 or max(p["pilot_lean"] for p in h) <= 0:
        problems.append("Bumper is not seen in the cockpit, thrown forward and then giving a thumbs up")
    i = by.get("I1-worn-wire", []) + by.get("I2-thrown-away", [])
    if not i or not all(p.get("crew") for p in i) or by.get("I2-thrown-away", [{}])[-1].get("wire_end_x", 0) > -30:
        problems.append("the crew is not seen dragging the worn wire away")
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
    video = a.out / "wire-film-1080x1920.mp4"
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
        "wire_physics": m.wire_physics(),
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
    (a.out / "wire-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("WIRE_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("WIRE_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "wire-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
