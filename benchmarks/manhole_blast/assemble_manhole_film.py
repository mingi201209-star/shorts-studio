"""EP.23: composes the rendered manhole film frames, builds the sound mix (frozen narration + effects placed from the model,
manhole_sfx), burns in the narration captions and runs every gate that can be decided from the clip, including the pace rules and the
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
from benchmarks.manhole_blast import manhole_motion as mm
from benchmarks.manhole_blast import manhole_sfx as sfx
from benchmarks.manhole_blast import manhole_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep23-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_manhole_3d.py").read_text()
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
    for js in sorted(panels.rglob("manhole-frames-*.json")):
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
    """Every frame was drawn from the model state of its simulated time: the gas share, the arc, the char on the splice, the vault
    pressure, the outflow and the fireball, and where the cover is (height, drift, turn, tilt); section shots are cut open."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        if abs(p["t"] - round(sh["t"], 6)) > 1e-6 or p["variant"] != sh["variant"]:
            problems.append(f"frame {fr['frame']}: simulated time or variant differs")
            continue
        st = mm.state(sh["t"], sh["variant"])
        for k, tol in (("gas", 1e-4), ("arc", 1e-3), ("char", 1e-3), ("pressure", 1.0), ("outflow", 1e-2), ("fireball", 1e-3)):
            if abs(p[k] - st[k]) > tol:
                problems.append(f"frame {fr['frame']}: {k} differs from the model ({p[k]} vs {st[k]:.5f})")
        for k in ("x", "y", "z", "tumble", "tilt"):
            if abs(p["cover"][k] - st["cover"][k]) > 1e-3:
                problems.append(f"frame {fr['frame']}: the cover's {k} differs from the model")
        if p["section"] != bool(sh.get("section")):
            problems.append(f"frame {fr['frame']}: cut-open view differs from the timeline")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1: the cover in the air over a column of fire with sparks flying; then the vault under the street, meltwater dropping
    onto the cables, arcs, the gas filling the vault past its flammable limit, the spark and the flame through the vault lifting the
    cover, the cover flying up and crashing down, a vented cover breathing smoke, the gas staying low under it, a latched cover popping
    up 3.5 in and dropping back; the loop runs into the opening's moment."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["variant"] == "blast" and p0["cover"]["z"] > 1.5 and p0["fire_puffs"] >= 10 and p0["sparks_airborne"] >= 20):
        problems.append(f"the first frame is not the cover in the air over fire and sparks ({p0['cover']['z']}, {p0['fire_puffs']}, {p0['sparks_airborne']})")
    b = by.get("B-vaults-under-streets", [])
    if not b or not all(p["section"] for p in b):
        problems.append("the vault under the street is not shown cut open")
    c = by.get("C-salty-meltwater", [])
    if not c or sum(p["drops_falling"] > 0 for p in c) < 0.5 * len(c):
        problems.append("meltwater is not seen dropping onto the cables")
    d = by.get("D-insulation-arcs", [])
    if not d or not any(p["arc"] > 0.3 for p in d):
        problems.append("no arc is seen at the splice")
    e = by.get("E-gas-fills-the-vault", [])
    if not e or e[0]["gas"] > 0.5 * mm.LFL or e[-1]["gas"] < mm.LFL:
        problems.append("the gas is not seen filling the vault past its flammable limit")
    f = by.get("F-one-spark", [])
    if not f or not any(p["arc"] > 0.5 for p in f) or f[-1]["burn"] < 0.5 or f[-1]["cover"]["z"] < 0.2:
        problems.append("the spark, the flame through the vault and the cover lifting are not all seen")
    g = by.get("G-three-hundred-pounds", [])
    if not g or max(p["cover"]["z"] for p in g) < 5.0:
        problems.append("the cover is not seen flying high")
    g2 = by.get("G2-crashes-down", [])
    if not g2 or g2[-1]["cover"]["z"] > 0.05 or not any(p["cover"]["tilt"] > 0.02 for p in g2):
        problems.append("the cover is not seen landing and wobbling")
    h = by.get("H-covers-with-vents", [])
    if not h or not all(p["variant"] == "vented" for p in h) or not any(p["smoke_puffs"] > 0 for p in h):
        problems.append("a vented cover breathing smoke is not shown")
    i = by.get("I-gas-escapes", [])
    if not i or not all(p["section"] for p in i) or max(p["gas"] for p in i) >= 0.5 * mm.LFL:
        problems.append("the gas is not seen staying low under a vented cover")
    j = by.get("J-latched-covers", [])
    seat = -mm.T_COVER / 2
    if not j or max(p["cover"]["z"] for p in j) < seat + mm.Z_LATCH - 0.002 or abs(j[-1]["cover"]["z"] - seat) > 0.002:
        problems.append("a latched cover is not seen popping up 3.5 in and dropping back")
    last = frames[-1]["parts"][0]
    if not (last["variant"] == p0["variant"] and -0.01 < p0["t"] - last["t"] < 0.002):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "first_frame": {k: p0[k] for k in ("t", "cover", "fireball", "fire_puffs", "sparks_airborne", "subject_box")}}


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
    video = a.out / "manhole-film-1080x1920.mp4"
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
        "manhole_physics": mm.manhole_physics(),
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
    (a.out / "manhole-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("MANHOLE_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("MANHOLE_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "manhole-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
