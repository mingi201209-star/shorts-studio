"""EP.12: composes the rendered headrest film frames (split halves stacked: top = headrest up, bottom = headrest low), draws labels, live
neck-angle readouts and fact cards, muxes the frozen narration (examples/episodes/ep12-audio) with burned-in captions and runs every gate that can be decided from the clip.
Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from benchmarks.headrest import head_motion as hm
from benchmarks.headrest import head_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep12-audio"
W, H = 1080, 1920
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GREEN, RED, INK, AMBER = (40, 170, 70), (200, 45, 40), (20, 20, 24), (230, 150, 30)
COL = {"high": GREEN, "low": RED}
NAME = {"high": "HEADREST UP", "low": "HEADREST LOW"}


def no_scene_text() -> dict:
    """No text inside the 3D scene. Labels, live readouts and fact cards are 2D overlays added in assembly."""
    src = (Path(__file__).resolve().parent / "render_head_3d.py").read_text()
    hits = [b for b in ('"FONT"', "'FONT'", "body_text", "text_add") if b in src]
    return {"status": "FAIL" if hits else "PASS", "problems": [f"renderer creates scene text ({h})" for h in hits]}


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


def _font(size):
    return ImageFont.truetype(BOLD, size)


def label_split(im: Image.Image, fr: dict) -> None:
    """First frame rule (EP.09/EP.10 data): one short label per half; the test condition joins only after 1.5 s."""
    d = ImageDraw.Draw(im)
    big = _font(64)
    for kind, y0 in (("high", 40), ("low", H // 2 + 40)):
        text = NAME[kind]
        w = d.textlength(text, font=big)
        d.rounded_rectangle((40, y0, 40 + w + 56, y0 + 96), radius=24, fill=COL[kind])
        d.text((40 + 28, y0 + 14), text, font=big, fill=(255, 255, 255))


def _angle_col(deg):
    return GREEN if deg < 20 else AMBER if deg < hm.WHIPLASH_DEG else RED


def draw_readouts(im: Image.Image, fr: dict) -> None:
    """Live neck angle of each driver in the split (from head_motion, frame by frame)."""
    d = ImageDraw.Draw(im)
    f = _font(44)
    for part, y0 in ((fr["parts"][0], 160), (fr["parts"][1], H // 2 + 160)):
        deg = max(0.0, part["deg"])
        d.rounded_rectangle((40, y0, 470, y0 + 76), radius=20, fill=(15, 15, 18))
        d.text((62, y0 + 12), f"NECK {deg:.0f}\u00b0", font=f, fill=(235, 235, 235))
        d.rounded_rectangle((290, y0 + 26, 450, y0 + 52), radius=10, fill=(60, 60, 66))
        d.rounded_rectangle((290, y0 + 26, 290 + max(10, 160 * min(1.0, deg / 60.0)), y0 + 52), radius=10, fill=_angle_col(deg))


def _card(d, text, size, colour, y, x_centre=0.5):
    f = _font(size)
    while d.textlength(text, font=f) > W - 120:
        size -= 2
        f = _font(size)
    w = d.textlength(text, font=f)
    x = W * x_centre - w / 2
    d.rounded_rectangle((x - 28, y, x + w + 28, y + size + 40), radius=26, fill=colour)
    d.text((x, y + 18), text, font=f, fill=(255, 255, 255))


def draw_overlays(im: Image.Image, fr: dict) -> None:
    """One card per line, naming the step of the chain; every number comes from head_motion."""
    d = ImageDraw.Draw(im)
    seg, p = fr["segment"], fr["parts"][0]
    deg = max(0.0, p["deg"])
    if seg in ("D-neck-bends", "E-whip", "F-tenth", "G-whiplash", "I-caught"):
        _card(d, f"NECK BENT BACK {deg:.0f}\u00b0", 60, _angle_col(deg), 300)
    if seg == "B-shove":
        _card(d, "HIT FROM BEHIND AT 20 mph", 60, INK, 170)
    elif seg == "C-head-stays":
        _card(d, "THE HEAD STAYS BEHIND", 64, INK, 170)
    elif seg == "D-neck-bends":
        _card(d, "THE NECK BENDS BACK", 64, INK, 170)
    elif seg == "E-whip":
        _card(d, "HEADREST LOW: NOTHING STOPS IT", 56, RED, 170)
    elif seg == "F-tenth":
        _card(d, f"{max(0.0, p['t']):.2f} s AFTER THE HIT", 60, INK, 170)
    elif seg == "G-whiplash":
        _card(d, "WHIPLASH", 80, RED, 160)
    elif seg == "H-two-inches":
        _card(d, f"GAP {100 * hm.BACKSET:.0f} cm \u00b7 {100 * hm.BACKSET / 2.54:.1f} in", 64, GREEN, 170)
    elif seg == "I-caught":
        _card(d, "CAUGHT" if p["caught"] else "HEADREST UP", 72, GREEN, 170)
    elif seg == "J-three-times":
        lo, hi = hm.peak("low")[0], hm.peak("high")[0]
        _card(d, f"{lo:.0f}\u00b0 vs {hi:.0f}\u00b0: \u00d7{lo / hi:.0f}", 64, INK, H // 2 + 280)
    elif seg == "K-height":
        _card(d, "TOP OF HEADREST = TOP OF HEAD", 54, GREEN, 170)
    elif seg == "L-close":
        _card(d, "A COUPLE OF INCHES BEHIND, AT MOST", 50, GREEN, 170)
    elif seg == "M-caught":
        _card(d, "UP AND CLOSE", 72, GREEN, H // 2 + 280)


def compose(panels: Path, out: Path, n: int) -> tuple[list[dict], str]:
    out.mkdir(parents=True, exist_ok=True)
    frames, sha = {}, None
    for js in sorted(panels.rglob("head-frames-*.json")):
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
                label_split(im, fr)
                if fr["segment"] not in ("A-split", "N-loop-run-in") or (fr["segment"] == "A-split" and fr["frame"] / tl.FPS >= 1.5):      # the loop run-in looks like the first frame
                    draw_readouts(im, fr)
            else:
                im = ims[0].resize((W, H), Image.LANCZOS) if ims[0].size != (W, H) else ims[0]
            draw_overlays(im, fr)
            im.save(out / f"frame_{f + 1:04d}.png")
            frames[f] = fr
    if sorted(frames) != list(range(n)):
        raise SystemExit(f"rendered {len(frames)} frames, expected exactly frames 0..{n - 1}")
    return [frames[i] for i in range(n)], sha


def telemetry_matches_model(frames: list[dict], segs: list[dict]) -> dict:
    """Every rendered part was drawn from the model state of its frame (same simulated time, neck angle, car position)."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        for part in fr["parts"]:
            m = hm.at("high" if part["variant"] == "high" else "low", sh["t"])
            if abs(part["t"] - round(sh["t"], 5)) > 1e-5 or abs(part["deg"] - m["deg"]) > 0.02 or abs(part["car_x"] - m["car_x"]) > 2e-4:
                problems.append(f"frame {fr['frame']} ({part['variant']}): renderer state differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """The low-headrest head whips back past 45 deg inside the opening's first 2 s while the high-headrest head never passes 22 deg; the
    high headrest catches the head in I."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr)
    problems = []
    a = by.get("A-split", [])
    whip_s = next((fr["frame"] / tl.FPS for fr in a if fr["parts"][1]["deg"] > 45), None)
    if whip_s is None or whip_s > 2.0:
        problems.append(f"the low-headrest whip is not visible in the first 2 s ({whip_s})")
    if any(fr["parts"][0]["deg"] > 22 for fr in a):
        problems.append("the high-headrest neck bends past 22 deg in the opening")
    if not any(p["caught"] for fr in by.get("I-caught", []) for p in fr["parts"]):
        problems.append("the headrest never catches the head in I")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "whip_film_s": whip_s}


def loop_closes(frames_dir: Path, n: int) -> dict:
    """The seam last -> first is as smooth as the steps right next to it: the jump is compared with the frame-to-frame change on both sides of
    the seam (frames 1 -> 2 and n-1 -> n). 
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
    video = a.out / "head-film-1080x1920.mp4"
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
        "head_physics": hm.head_physics(),
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
    (a.out / "head-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("HEAD_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("HEAD_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "96k", a.out / "head-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
