"""EP.24: composes the rendered musical-road film frames, builds the sound mix (frozen narration + the tune synthesized from the model's
tyre thumps, musical_sfx), burns in the narration captions and runs every gate that can be decided from the clip, including the pace
rules and the opening-hook rules (benchmarks/hook_gate.py). No text on the picture other than the captions. Never uploads."""
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
from benchmarks.musical_road import musical_motion as mm
from benchmarks.musical_road import musical_sfx as sfx
from benchmarks.musical_road import musical_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]


def sstep(e0, e1, x):
    """Smoothstep, as in the renderer (kept here so the assembly needs no Blender)."""
    u = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return u * u * (3 - 2 * u)

AUDIO_DIR = ROOT / "examples/episodes/ep24-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_musical_3d.py").read_text()
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
    for js in sorted(panels.rglob("musical-frames-*.json")):
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
    """Every frame was drawn from the model state of its simulated time: the road version, the car's place, speed and wheel turn,
    the note and thump rate under its front tyres; the spacing demonstration's grooves where the model puts them."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        if abs(p["t"] - round(sh["t"], 6)) > 1e-6 or p["variant"] != sh["variant"]:
            problems.append(f"frame {fr['frame']}: simulated time or variant differs")
            continue
        cs = tl.car_state(sh)
        version = "built" if sh["variant"] in ("built", "compare") else "design"
        if p["version"] != version or p["speed"] != cs["speed"] or p["car_visible"] != cs["visible"]:
            problems.append(f"frame {fr['frame']}: road version, speed or car visibility differs")
        if abs(p["car_y"] - cs["y"]) > 1e-3 or abs(p["wheel_angle"] - cs["wheel_angle"]) > 1e-4:
            problems.append(f"frame {fr['frame']}: the car's place or wheel turn differs from the model")
        if p["note"] != cs["note"] or abs(p["thump_rate"] - cs["thump_rate"]) > 1e-2:
            problems.append(f"frame {fr['frame']}: the note under the tyres differs from the model")
        if sh["variant"] == "gap":
            f = min(1.0, max(0.0, sh["t"]))
            if abs(p["morph"] - float(sstep(0.32, 0.72, f))) > 1e-3:
                problems.append(f"frame {fr['frame']}: the grooves are not where the spacing demonstration puts them")
        if p["ghost"] != (sh["variant"] == "compare") or p["glow"] != bool(sh.get("glow")):
            problems.append(f"frame {fr['frame']}: planned-groove lines or the glow trail shown in the wrong shot")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict], segs: list[dict]) -> dict:
    """Frame 1: the car on the grooves with a note under its tyres; then the grooves like a record with the car coming over them,
    the tyre thumping groove by groove in slow motion, the thumps speeding up into a note, wide (low) and close (high) grooves from
    above, a whole phrase of the tune with the played grooves glowing, the car at 35 mph, the road in California, the crew's gap against groove to
    groove (the grooves sliding apart), the built grooves against the planned ones; the loop runs into the opening's moment."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    seg_by = {s["label"]: s for s in segs}
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["variant"] == "built" and p0["car_visible"] and p0["note"] is not None and p0["thump_rate"] > 150):
        problems.append(f"the first frame is not the car playing the grooves ({p0['note']}, {p0['thump_rate']})")
    b = by.get("B-like-a-record", [])
    if not b or b[-1]["car_y"] - b[0]["car_y"] < 30 or not all(p["car_visible"] for p in b):
        problems.append("the car is not seen coming over the grooves")
    c = by.get("C-one-thump", [])
    if not c or sum(p["rings"] > 0 for p in c) < 0.5 * len(c) or abs(seg_by["C-one-thump"]["time_scale"]) * 250 > 12:
        problems.append("the separate thumps are not shown in slow motion")
    d = seg_by.get("D-thumps-to-a-note")
    if d is None:
        problems.append("the thumps never speed up into a note")
    else:
        k = d["knots"]
        slow = (k[1][1] - k[0][1]) / (k[1][0] - k[0][0]) * mm.freq("B3")
        fast = (k[-1][1] - k[-2][1]) / (k[-1][0] - k[-2][0]) * mm.freq("B3")
        if not (slow < 12 and fast > 100):
            problems.append(f"the thumps do not speed up from separate thumps to a note ({slow:.0f}/s to {fast:.0f}/s)")
    e = by.get("E-close-high-wide-low", [])
    if not e or not {"B3", "G#4"} <= {p["note"] for p in e}:
        problems.append("a low (wide) and a high (close) note are not both shown from above")
    f = by.get("F-plays-a-melody", [])
    if not f or not all(p["glow"] for p in f) or f[0]["t"] > 0.0 or f[-1]["t"] < sum(n for _, n in mm.PHRASE) * mm.SIXTEENTH:
        problems.append("a whole phrase of the tune is not shown with the played grooves glowing")
    g = by.get("G-slower-lower", [])
    if not g or not all(p["speed"] == "slow" for p in g) or not any(p["note"] for p in g):
        problems.append("the car is not seen playing the tune at the lower speed")
    h = by.get("H-california", [])
    if not h or not all(p["version"] == "built" and p["car_visible"] for p in h):
        problems.append("the built road with the car is not shown")
    i = by.get("I-the-gap", [])
    if not i or i[0]["morph"] > 0.01 or i[-1]["morph"] < 0.99:
        problems.append("the grooves are not seen sliding from groove-to-groove spacing to the crew's gap")
    j = by.get("J-every-note-flat", [])
    if not j or not all(p["ghost"] and p["version"] == "built" for p in j):
        problems.append("the built grooves are not shown against the planned ones")
    last = frames[-1]["parts"][0]
    if not (last["variant"] == p0["variant"] and -0.01 < p0["t"] - last["t"] < 0.002):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "first_frame": {k: p0[k] for k in ("t", "note", "thump_rate", "car_y", "subject_box")}}


def loop_closes(frames_dir: Path, n: int) -> dict:
    """The seam last -> first is as smooth as the steps right next to it (jump <= 1.5 x the larger neighbouring step)."""
    def g(i):
        return np.asarray(Image.open(frames_dir / f"frame_{i:04d}.png").convert("L"), dtype=np.float32)

    before = float(np.abs(g(n) - g(n - 1)).mean())
    after = float(np.abs(g(2) - g(1)).mean())
    jump = float(np.abs(g(n) - g(1)).mean())
    return {"status": "PASS" if jump <= 1.5 * max(before, after) else "FAIL", "mean_abs_diff_last_vs_first": round(jump, 2),
            "step_before_seam": round(before, 2), "step_after_seam": round(after, 2)}


def tune_matches_model(fx_wav: Path, segs: list[dict]) -> dict:
    """The tyre tune in the effects really plays the model's notes: in every real-time shot, the pitch measured from the
    synthesized thumps (tune.wav, the thumps before the rest of the effects are added; autocorrelation over 40 ms windows while
    both axles are on the same note stretch) is the model's thump rate within 30 cents."""
    from benchmarks.guardrail_end.terminal_sfx import SR, read_wav
    x = read_wav(fx_wav)
    rows, problems = [], []
    for s in segs:
        if s["variant"] not in ("built", "design", "slow", "compare") or abs(s["time_scale"] - 1.0) > 1e-6:
            continue
        version = "built" if s["variant"] in ("built", "compare") else "design"
        speed = "slow" if s["variant"] == "slow" else "design"
        vel = mm.V_SLOW if speed == "slow" else mm.V_DESIGN
        for y0, y1, _, name, _, _ in mm.layout(version):
            if (y1 - y0 - mm.WHEELBASE) / vel < 0.05:                         # both axles on the same note for a whole window
                continue
            t_mid = ((y0 + mm.WHEELBASE + y1) / 2 - mm.START_Y) / vel
            ft = s["t0"] + (t_mid - s["sim0"])
            if not s["t0"] + 0.05 < ft < s["t1"] - 0.05:
                continue
            i = int(ft * SR)
            w = x[i - int(0.02 * SR): i + int(0.02 * SR)]
            w = w - w.mean()
            ac = np.correlate(w, w, mode="full")[len(w) - 1:]
            expect = mm.played_freq(name, version, vel)
            lo, hi = int(SR / (expect * 1.5)), int(SR / (expect / 1.5))
            lag = lo + int(np.argmax(ac[lo:hi]))
            got = SR / lag
            err = 1200 * math.log2(got / expect)
            rows.append({"segment": s["label"], "note": name, "expect_hz": round(expect, 1), "measured_hz": round(got, 1), "cents": round(err, 1)})
            if abs(err) > 30:
                problems.append(f"{s['label']} {name}: measured {got:.1f} Hz, model {expect:.1f} Hz")
    if len(rows) < 6:
        problems.append(f"only {len(rows)} notes could be measured")
    return {"status": "FAIL" if problems else "PASS", "problems": problems[:6], "notes_measured": len(rows),
            "worst_cents": max((abs(r["cents"]) for r in rows), default=None), "sample": rows[:6]}


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
    video = a.out / "musical-film-1080x1920.mp4"
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
        "musical_physics": mm.musical_physics(),
        "pace": tl.pace(segs),
        "opening_hook": hook_gate.opening_hook(frames, segs, tl.line_starts()[1], tl.FPS),
        "scene_alignment": tl.scene_alignment(segs),
        "telemetry_matches_model": telemetry_matches_model(frames, segs),
        "visible_action": visible_action(frames, segs),
        "no_scene_text": no_scene_text(),
        "loop_closes": loop_closes(frames_dir, n),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "captions_visible": verify_captions_over_picture(video, frames_dir, [((c["start"] + c["end"]) / 2, CAPTION_BAND) for c in cues], a.out, fps=tl.FPS),
        "audio_mix": audio_mix(levels),
        "tune_matches_model": tune_matches_model(a.out / "tune.wav", segs),
    }
    report["preview_status"] = "PASS" if not problems and all(v["status"] in ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING") for v in report.values() if isinstance(v, dict) and "status" in v) else "FAIL"
    report.update(problems=problems, renderer_source_sha256=sha, frames=n, seconds=round(seconds, 3), narration_sha256=narration_sha,
                  segments=[{k: s[k] for k in ("label", "t0", "t1", "sim0", "sim1", "time_scale")} for s in segs],
                  note="preview only: nothing uploaded; the sound mix and voice are not human-checked; a human first view UNVERIFIED")
    (a.out / "musical-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("MUSICAL_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("MUSICAL_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "musical-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
