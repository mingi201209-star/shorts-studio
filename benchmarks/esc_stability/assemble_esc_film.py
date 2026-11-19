"""EP.07: composes the rendered ESC film frames (split-screen halves stacked: top = ESC, bottom = no ESC), muxes the frozen narration
(examples/episodes/ep07-audio) with burned-in captions and runs every gate that can be decided from the clip. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from benchmarks.esc_stability import esc_motion as am
from benchmarks.esc_stability import esc_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep07-audio"
W, H = 1080, 1920


def no_scene_text() -> dict:
    src = (Path(__file__).resolve().parent / "render_esc_3d.py").read_text()
    hits = [b for b in ('"FONT"', "'FONT'", "body_text", "text_add") if b in src]
    return {"status": "FAIL" if hits else "PASS", "problems": [f"renderer creates scene text ({h})" for h in hits]}


def probe_video(video: Path) -> dict:
    """ffprobe when present; the CI fallback ffmpeg ships no ffprobe, so then every frame is decoded with OpenCV and counted."""
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
    for js in sorted(panels.rglob("esc-frames-*.json")):
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
                im.paste((20, 20, 24), (0, H // 2 - 3, W, H // 2 + 3))
            else:
                im = ims[0].resize((W, H), Image.LANCZOS) if ims[0].size != (W, H) else ims[0]
            im.save(out / f"frame_{f + 1:04d}.png")
            frames[f] = fr
    if sorted(frames) != list(range(n)):
        raise SystemExit(f"rendered {len(frames)} frames, expected exactly frames 0..{n - 1}")
    return [frames[i] for i in range(n)], sha


def telemetry_matches_model(frames: list[dict], segs: list[dict]) -> dict:
    """Every rendered part was drawn from the model state of its frame (same simulated time, position, wheel speed, pressure)."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        for part in fr["parts"]:
            m = am.at(part["variant"], sh["t"])
            if abs(part["t"] - sh["t"]) > 1e-4 or abs(part["y"] - m["y"]) > 2e-3 or abs(part["heading_deg"] - round(__import__("math").degrees(m["heading"]), 2)) > 0.02:
                problems.append(f"frame {fr['frame']} ({part['variant']}): renderer state differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """What the narration names really happens on screen: in the opening the bottom car (no ESC) turns past 45 degrees while the top (ESC)
    car stays within 20 degrees; the rear tyres of the car without ESC slide in segments B/C; the ESC car brakes the outside front wheel in
    segment I; the ESC car ends pointing down the road."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr)
    problems = []
    a = by.get("A-split-swerve", [])
    off_max = max((abs(fr["parts"][1]["heading_deg"]) for fr in a), default=0)
    esc_max = max((abs(fr["parts"][0]["heading_deg"]) for fr in a), default=99)
    if off_max < 45:
        problems.append(f"the car without ESC turns only {off_max:.0f} degrees in the opening")
    if esc_max > 20:
        problems.append(f"the ESC car turns {esc_max:.0f} degrees in the opening")
    first_45 = next((fr["frame"] / tl.FPS for fr in a if abs(fr["parts"][1]["heading_deg"]) > 45), None)
    if not any(p["rear_sliding"] for seg in ("B-rear-loses-grip", "C-turns-faster") for fr in by.get(seg, []) for p in fr["parts"]):
        problems.append("the rear tyres never slide on screen")
    braked = [p for fr in by.get("I-outer-brake", []) for p in fr["parts"] if p["braked_wheel"]]
    if not braked or any(p["braked_wheel"] != ("front_right" if p["yaw_rate"] > 0 else "front_left") for p in braked):
        problems.append("the outside front wheel is not the one braked in segment I")
    end = by.get("L-stays-straight", [])
    if not end or abs(end[-1]["parts"][0]["heading_deg"]) > 8:
        problems.append("the ESC car does not end pointing down the road")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "off_heading_max_in_opening_deg": off_max, "esc_heading_max_in_opening_deg": esc_max,
            "off_past_45deg_film_s": first_45, "braked_frames_in_I": len(braked)}


def loop_closes(frames_dir: Path, n: int, opening: int = 24) -> dict:
    """The last frame leads back into the first as smoothly as any other cut-free step of the opening: the jump last -> first is compared with
    the typical frame-to-frame change of the opening's first second (the cars move at 80 km/h with a following camera, so neighbouring frames
    already differ). Seamless when the jump is at most 1.5 x the opening's median step."""
    import numpy as np

    def g(i):
        return np.asarray(Image.open(frames_dir / f"frame_{i:04d}.png").convert("L"), dtype=np.float32)

    steps = [float(np.abs(g(i + 1) - g(i)).mean()) for i in range(1, opening)]
    typical = float(np.median(steps))
    jump = float(np.abs(g(n) - g(1)).mean())
    return {"status": "PASS" if jump <= 1.5 * typical else "FAIL", "mean_abs_diff_last_vs_first": round(jump, 2), "opening_median_step": round(typical, 2)}


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
    shutil.copy(AUDIO_DIR / "narration.wav", a.out / "narration.wav")
    ass = a.out / "film.ass"
    text = (AUDIO_DIR / "film.ass").read_text(encoding="utf8")
    style = ",0,0,1,3,0,2,90,90,210,1"
    if text.count(style) != 1:
        raise SystemExit("caption style line not in the expected form")
    ass.write_text(text.replace(style, ",0,0,1,6,2,2,90,90,420,1"), encoding="utf8")       # same caption look as EP.05: thicker outline, above the bottom UI
    seconds = n / tl.FPS
    video = a.out / "esc-film-1080x1920.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(tl.FPS), "-i", str(frames_dir / "frame_%04d.png"), "-i", str(a.out / "narration.wav"),
         "-vf", f"setpts=N/({tl.FPS}*TB),ass={ass}", "-af", "apad", "-map", "0:v:0", "-map", "1:a:0", "-t", f"{seconds}", "-r", str(tl.FPS), "-c:v", "libx264",
         "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", video])
    info = probe_video(video)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    problems = []
    if (vs["width"], vs["height"], int(vs["nb_read_frames"])) != (W, H, n):
        problems.append(f"video is {vs['width']}x{vs['height']} with {vs['nb_read_frames']} frames, expected {n}")
    cues = [c for c in audio["cues"] if c["end"] <= seconds - 0.1]
    report = {
        "esc_physics": am.esc_physics(),
        "scene_alignment": tl.scene_alignment(segs),
        "telemetry_matches_model": telemetry_matches_model(frames, segs),
        "visible_action": visible_action(frames),
        "no_scene_text": no_scene_text(),
        "loop_closes": loop_closes(frames_dir, n),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "captions_visible": verify_captions_over_picture(video, frames_dir, [((c["start"] + c["end"]) / 2, (1400, 1919)) for c in cues], a.out, fps=tl.FPS),
    }
    report["preview_status"] = "PASS" if not problems and all(v["status"] in ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING") for v in report.values() if isinstance(v, dict) and "status" in v) else "FAIL"
    report.update(problems=problems, renderer_source_sha256=sha, frames=n, seconds=round(seconds, 3), narration_sha256=narration_sha,
                  segments=[{k: s[k] for k in ("label", "t0", "t1", "sim0", "sim1", "time_scale")} for s in segs],
                  note="preview only: nothing uploaded; voice pronunciation, sound-off readability and a human first view UNVERIFIED")
    (a.out / "esc-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("ESC_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("ESC_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "96k", a.out / "esc-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
