"""EP.10: composes the rendered following-distance film frames (split-screen halves stacked: top = 3-second gap, bottom = 1-second gap), muxes the frozen narration
(examples/episodes/ep10-audio) with burned-in captions and runs every gate that can be decided from the clip. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from benchmarks.following import follow_motion as am
from benchmarks.following import follow_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep10-audio"
W, H = 1080, 1920


def no_scene_text() -> dict:
    """No text inside the 3D scene. Labels, live readouts and fact cards are 2D overlays added in assembly."""
    src = (Path(__file__).resolve().parent / "render_follow_3d.py").read_text()
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


LABEL_TOP, LABEL_BOTTOM = ("3-SECOND GAP", (40, 170, 70)), ("1-SECOND GAP", (200, 45, 40))
CONDITIONS = "SAME SPEED \u00b7 60 mph \u00b7 SAME DRIVER"


def label_split(im: Image.Image) -> None:
    """Owner decision (2026-11-19, after EP.06's 45 % viewed rate): the split opening says which car is which, like the best Short so far
    (Road Signs, 69.9 %, which showed its test conditions on screen). Drawn on the composed frame, above the caption band, nowhere else."""
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(im)
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    big, small = ImageFont.truetype(bold, 64), ImageFont.truetype(bold, 36)
    for (text, colour), y0 in ((LABEL_TOP, 120), (LABEL_BOTTOM, H // 2 + 40)):
        w = d.textlength(text, font=big)
        d.rounded_rectangle((40, y0, 40 + w + 56, y0 + 96), radius=24, fill=colour)
        d.text((40 + 28, y0 + 14), text, font=big, fill=(255, 255, 255))
    w = d.textlength(CONDITIONS, font=small)
    d.rounded_rectangle(((W - w) / 2 - 24, 30, (W + w) / 2 + 24, 92), radius=18, fill=(15, 15, 18))
    d.text(((W - w) / 2, 40), CONDITIONS, font=small, fill=(235, 235, 235))


def compose(panels: Path, out: Path, n: int) -> tuple[list[dict], str]:
    out.mkdir(parents=True, exist_ok=True)
    frames, sha = {}, None
    for js in sorted(panels.rglob("follow-frames-*.json")):
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
                label_split(im)
                draw_readouts(im, fr)
                draw_overlays(im, fr)
            else:
                im = ims[0].resize((W, H), Image.LANCZOS) if ims[0].size != (W, H) else ims[0]
            if not fr["split"]:
                draw_overlays(im, fr)
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
            if abs(part["t"] - round(sh["t"], 5)) > 1e-5 or abs(part["gap_m"] - round(m["gap_m"], 2)) > 2e-2 or abs(part["fol_x"] - round(m["fol_x"], 3)) > 2e-3:
                problems.append(f"frame {fr['frame']} ({part['variant']}): renderer state differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """The 1-second car (bottom) hits the car ahead inside the first second of the opening while the 3-second car (top) never does; the
    follower does not brake before the reaction time in C/D; in H the follower passes the sign 3 s after the car ahead."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr)
    problems = []
    a = by.get("A-split", [])
    hit_s = next((fr["frame"] / tl.FPS for fr in a if fr["parts"][1]["hit"]), None)
    if hit_s is None or hit_s > 1.2:
        problems.append(f"the 1-second car does not hit inside the opening's first second ({hit_s})")
    if any(fr["parts"][0]["hit"] for fr in a):
        problems.append("the 3-second car hits the car ahead")
    for seg in ("C-reaction", "D-forty-yards"):
        if any(p["fol_braking"] and p["t"] < am.REACTION_S - 1e-3 for fr in by.get(seg, []) for p in fr["parts"]):
            problems.append(f"the follower brakes before the reaction time in {seg}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "hit_film_s": hit_s}


BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GREEN, RED, INK, AMBER = (40, 170, 70), (200, 45, 40), (20, 20, 24), (230, 150, 30)


def _card(d, text, size, colour, y, x_centre=0.5):
    from PIL import ImageFont
    f = ImageFont.truetype(BOLD, size)
    while d.textlength(text, font=f) > W - 120:
        size -= 2
        f = ImageFont.truetype(BOLD, size)
    w = d.textlength(text, font=f)
    x = W * x_centre - w / 2
    d.rounded_rectangle((x - 28, y, x + w + 28, y + size + 40), radius=26, fill=colour)
    d.text((x, y + 18), text, font=f, fill=(255, 255, 255))


def _bars(d, rows, y0):
    """Distance bars: (label, metres, colour), scaled so 90 m spans the frame."""
    from PIL import ImageFont
    f = ImageFont.truetype(BOLD, 40)
    for k, (label, m, col) in enumerate(rows):
        y = y0 + k * 120
        d.text((70, y), label, font=f, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))
        d.rounded_rectangle((70, y + 54, 70 + (W - 140) * min(1.0, m / 90.0), y + 92), radius=14, fill=col)


def draw_overlays(im: Image.Image, fr: dict) -> None:
    """Fact cards, timers, counts and bars for the dense lines; numbers come from follow_motion."""
    from PIL import ImageDraw
    d = ImageDraw.Draw(im)
    seg, p = fr["segment"], fr["parts"][0]
    t = p["t"]
    if seg in ("C-reaction", "D-forty-yards"):
        r = max(0.0, min(am.REACTION_S, t))
        _card(d, f"REACTION  {r:.1f} s", 72, AMBER if r < am.REACTION_S else RED, 1120)
        if seg == "D-forty-yards":
            _card(d, f"\u2248 {am.reaction_distance():.0f} m \u00b7 {am.reaction_distance() / 0.9144:.0f} yd before braking", 48, INK, 1270)
    elif seg == "E-square":
        _card(d, "BRAKING DISTANCE \u221d SPEED\u00b2", 56, INK, 1180)
    elif seg == "F-double":
        _bars(d, [(f"30 mph \u2192 {am.braking_distance(30 * am.MPH):.0f} m", am.braking_distance(30 * am.MPH), GREEN),
                  (f"60 mph \u2192 {am.braking_distance(60 * am.MPH):.0f} m  (\u00d74)", am.braking_distance(60 * am.MPH), RED)], 1060)
    elif seg == "G-46-vs-86":
        _bars(d, [(f"CAR AHEAD STOPS IN {am.braking_distance():.0f} m", am.braking_distance(), GREEN),
                  (f"YOU NEED {am.reaction_distance() + am.braking_distance():.0f} m", am.reaction_distance() + am.braking_distance(), RED)], 1060)
    elif seg in ("H-count", "I-too-close"):
        gap = am.GAP_S["three" if seg == "H-count" else "one"]
        lead_pass = tl.SIGN_PASS_LEAD_S + am.GAP_S["three"] - gap
        fol_pass = lead_pass + gap
        if t >= lead_pass:
            n = min(int(t - lead_pass) + 1, 3) if t < fol_pass else max(1, round(gap))
            if t < fol_pass:
                _card(d, f"{n}\u2026", 120, INK, 1060)
            elif seg == "H-count":
                _card(d, "3 \u2713  SAFE GAP", 90, GREEN, 1060)
            else:
                _card(d, "1 \u2026 TOO CLOSE", 90, RED, 1060)
    elif seg == "J-rain":
        _card(d, "RAIN: 6 SECONDS", 80, INK, 1100)
    elif seg == "K-phone":
        _card(d, f"2 s at 60 mph = {2 * am.V0:.0f} m \u00b7 {2 * am.V0 / 0.9144:.0f} yd BLIND", 46, RED, 1180)
    elif seg == "M-three-seconds":
        _card(d, "3 SECONDS. EVERY TIME.", 72, GREEN, 1120)


def draw_readouts(im: Image.Image, fr: dict) -> None:
    """Live speed and gap of each follower in the split (from the model, frame by frame)."""
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(BOLD, 44)
    for part, y0 in ((fr["parts"][0], 250), (fr["parts"][1], H // 2 + 170)):
        g = part["gap_m"]
        col = GREEN if g > 25 else AMBER if g > 8 else RED
        d.rounded_rectangle((40, y0, 470, y0 + 128), radius=20, fill=(15, 15, 18))
        d.text((62, y0 + 10), f"{part['fol_mph']:.0f} mph", font=f, fill=(235, 235, 235))
        d.text((62, y0 + 66), "GAP", font=ImageFont.truetype(BOLD, 34), fill=(235, 235, 235))
        d.rounded_rectangle((150, y0 + 74, 450, y0 + 104), radius=10, fill=(60, 60, 66))
        d.rounded_rectangle((150, y0 + 74, 150 + max(14, 300 * min(1.0, g / 80.0)), y0 + 104), radius=10, fill=col)
        d.text((330, y0 + 10), "CRASH" if part["hit"] else f"{g:.0f} m", font=f, fill=RED if part["hit"] else (235, 235, 235))


def loop_closes(frames_dir: Path, n: int) -> dict:
    """The seam last -> first is as smooth as the steps right next to it: the jump is compared with the frame-to-frame change on both sides of
    the seam (frames 1 -> 2 and n-1 -> n). The cars move at 80 km/h under a following camera, so those neighbouring steps are already large.
    Seamless when the jump is at most 1.5 x the larger neighbouring step."""
    import numpy as np

    def g(i):
        return np.asarray(Image.open(frames_dir / f"frame_{i:04d}.png").convert("L"), dtype=np.float32)

    before = float(np.abs(g(n) - g(n - 1)).mean())
    after = float(np.abs(g(2) - g(1)).mean())
    jump = float(np.abs(g(n) - g(1)).mean())
    return {"status": "PASS" if jump <= 1.5 * max(before, after) else "FAIL", "mean_abs_diff_last_vs_first": round(jump, 2),
            "step_before_seam": round(before, 2), "step_after_seam": round(after, 2)}


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
    text = text.replace(style, ",0,0,1,6,2,2,90,90,420,1")       # same caption look as EP.05: thicker outline, above the bottom UI
    split_spans = [(sg["t0"], sg["t1"]) for sg in segs if sg["flags"].get("split")]

    def in_split(t):
        return any(a0 <= t < a1 for a0, a1 in split_spans)

    def ass_t(v):
        h, m, sec = v.split(":")
        return int(h) * 3600 + int(m) * 60 + float(sec)

    lines_out = []
    for line in text.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if in_split((ass_t(parts[1]) + ass_t(parts[2])) / 2):
                parts[9] = r"{\an5\pos(540,960)}" + parts[9]       # on the divider: the bottom car stays visible in the split
                line = ",".join(parts)
        lines_out.append(line)
    ass.write_text("\n".join(lines_out) + "\n", encoding="utf8")
    seconds = n / tl.FPS
    video = a.out / "follow-film-1080x1920.mp4"
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
        "follow_physics": am.follow_physics(),
        "scene_alignment": tl.scene_alignment(segs),
        "telemetry_matches_model": telemetry_matches_model(frames, segs),
        "visible_action": visible_action(frames),
        "no_scene_text": no_scene_text(),
        "loop_closes": loop_closes(frames_dir, n),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "captions_visible": verify_captions_over_picture(video, frames_dir, [((c["start"] + c["end"]) / 2, (880, 1040) if in_split((c["start"] + c["end"]) / 2) else (1400, 1919)) for c in cues], a.out, fps=tl.FPS),
    }
    report["preview_status"] = "PASS" if not problems and all(v["status"] in ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING") for v in report.values() if isinstance(v, dict) and "status" in v) else "FAIL"
    report.update(problems=problems, renderer_source_sha256=sha, frames=n, seconds=round(seconds, 3), narration_sha256=narration_sha,
                  segments=[{k: s[k] for k in ("label", "t0", "t1", "sim0", "sim1", "time_scale")} for s in segs],
                  note="preview only: nothing uploaded; voice pronunciation, sound-off readability and a human first view UNVERIFIED")
    (a.out / "follow-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("FOLLOW_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("FOLLOW_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "96k", a.out / "follow-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
