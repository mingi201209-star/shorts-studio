"""EP.11: composes the rendered speed film frames (split halves stacked: top = 30 mph, bottom = 40 mph), draws labels, live readouts and fact
cards, muxes the frozen narration (examples/episodes/ep11-audio) with burned-in captions and runs every gate that can be decided from the clip.
Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from benchmarks.speed_energy import speed_motion as sm
from benchmarks.speed_energy import speed_timeline as tl
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep11-audio"
W, H = 1080, 1920
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GREEN, RED, INK, AMBER = (40, 170, 70), (200, 45, 40), (20, 20, 24), (230, 150, 30)
COL = {"slow": GREEN, "fast": RED}
NAME = {"slow": "30 MPH", "fast": "40 MPH"}


def no_scene_text() -> dict:
    """No text inside the 3D scene. Labels, live readouts and fact cards are 2D overlays added in assembly."""
    src = (Path(__file__).resolve().parent / "render_speed_3d.py").read_text()
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


def label_split(im: Image.Image, segment: str) -> None:
    d = ImageDraw.Draw(im)
    big = _font(64)
    for kind, y0 in (("slow", 120), ("fast", H // 2 + 40)):
        text = NAME[kind]
        w = d.textlength(text, font=big)
        d.rounded_rectangle((40, y0, 40 + w + 56, y0 + 96), radius=24, fill=COL[kind])
        d.text((40 + 28, y0 + 14), text, font=big, fill=(255, 255, 255))
    cond = "SAME DRIVER \u00b7 SAME BRAKES" if segment == "K-braking" else "SAME CAR \u00b7 SAME WALL"
    small = _font(36)
    w = d.textlength(cond, font=small)
    d.rounded_rectangle(((W - w) / 2 - 24, 30, (W + w) / 2 + 24, 92), radius=18, fill=(15, 15, 18))
    d.text(((W - w) / 2, 40), cond, font=small, fill=(235, 235, 235))


def _card(d, text, size, colour, y, x_centre=0.5):
    f = _font(size)
    while d.textlength(text, font=f) > W - 120:
        size -= 2
        f = _font(size)
    w = d.textlength(text, font=f)
    x = W * x_centre - w / 2
    d.rounded_rectangle((x - 28, y, x + w + 28, y + size + 40), radius=26, fill=colour)
    d.text((x, y + 18), text, font=f, fill=(255, 255, 255))


def draw_readouts(im: Image.Image, fr: dict) -> None:
    """Live speed and crush depth (or energy, or braking state) of each car in the split, from the model frame by frame."""
    d = ImageDraw.Draw(im)
    f, f2 = _font(44), _font(34)
    for part, y0 in ((fr["parts"][0], 250), (fr["parts"][1], H // 2 + 170)):
        kind = part["variant"]
        d.rounded_rectangle((40, y0, 500, y0 + 128), radius=20, fill=(15, 15, 18))
        d.text((62, y0 + 10), f"{part['mph']:.0f} mph", font=f, fill=(235, 235, 235))
        if fr["segment"] == "D-energy":
            e = sm.energy_kj(kind)
            d.text((62, y0 + 70), "ENERGY", font=f2, fill=(235, 235, 235))
            d.rounded_rectangle((210, y0 + 76, 480, y0 + 106), radius=10, fill=(60, 60, 66))
            d.rounded_rectangle((210, y0 + 76, 210 + 270 * e / sm.energy_kj("fast"), y0 + 106), radius=10, fill=COL[kind])
            d.text((290, y0 + 10), f"{e:.0f} kJ", font=f, fill=COL[kind] if kind == "fast" else (235, 235, 235))
        elif fr["segment"] == "K-braking":
            d.text((62, y0 + 70), "BRAKING" if part["braking"] else "REACTING", font=f2, fill=RED if part["braking"] else AMBER)
        else:
            c = part["crush_cm"]
            d.text((62, y0 + 70), "CRUSH", font=f2, fill=(235, 235, 235))
            d.rounded_rectangle((200, y0 + 76, 480, y0 + 106), radius=10, fill=(60, 60, 66))
            d.rounded_rectangle((200, y0 + 76, 200 + max(12, 280 * c / 75.0), y0 + 106), radius=10, fill=COL[kind])
            d.text((300, y0 + 10), f"{c:.0f} cm", font=f, fill=(235, 235, 235))


def draw_bracket(d, marks, kind):
    """'Crumple zone left' bracket between the wall face and the front of the cabin (both projected by the renderer)."""
    (x0, y0), (x1, y1) = marks["wall"], marks["cabin"]
    a, b = (x0 * W, y0 * H), (x1 * W, y1 * H)
    col = COL[kind]
    d.line((a, b), fill=col, width=12)
    for p in (a, b):
        d.line((p[0], p[1] - 40, p[0], p[1] + 40), fill=col, width=10)
    f = _font(40)
    txt = f"{marks['zone_left_cm']:.0f} cm LEFT"
    mx, my = (a[0] + b[0]) / 2, min(a[1], b[1]) - 80
    w = d.textlength(txt, font=f)
    d.rounded_rectangle((mx - w / 2 - 18, my - 8, mx + w / 2 + 18, my + 52), radius=16, fill=(15, 15, 18))
    d.text((mx - w / 2, my), txt, font=f, fill=(255, 255, 255))


def draw_overlays(im: Image.Image, fr: dict) -> None:
    """Fact cards for the dense lines; every number comes from speed_motion."""
    d = ImageDraw.Draw(im)
    seg, p = fr["segment"], fr["parts"][0]
    pct = round(100 * (sm.energy_kj("fast") / sm.energy_kj("slow") - 1))
    if seg == "C-square":
        _card(d, "CRASH ENERGY \u221d SPEED\u00b2", 60, INK, 170)
    elif seg == "D-energy":
        _card(d, f"+{pct}% ENERGY", 84, RED, H // 2 + 330)
    elif seg == "E-somewhere":
        _card(d, f"{sm.energy_kj('fast'):.0f} kJ HAS TO GO SOMEWHERE", 52, INK, 170)
    elif seg == "F-rails":
        _card(d, "CRUSH RAILS FOLD", 64, AMBER, 170)
        _card(d, f"CRUSH {p['crush_cm']:.0f} cm", 56, INK, 300)
    elif seg in ("G-thirty", "H-forty"):
        k = p["variant"]
        cm_ = 100 * sm.crush_m(k)
        _card(d, f"{sm.SPEEDS[k]:.0f} mph \u2192 {cm_:.0f} cm \u00b7 {cm_ / 2.54:.0f} in CRUSHED", 52, COL[k], 170)
        if seg == "H-forty":
            _card(d, "ALMOST TO THE CABIN", 56, INK, 300)
        if p.get("marks") and p["crush_cm"] > 5:
            draw_bracket(d, p["marks"], k)
    elif seg in ("I-three-story", "J-five-story"):
        k = p["variant"]
        h = sm.fall_height_m(k)
        _card(d, f"{sm.SPEEDS[k]:.0f} mph = {h:.0f} m FALL \u00b7 {sm.storeys(k)} STORIES", 56, COL[k], 170)
        if p["drop_h_m"] is not None:
            _card(d, f"{p['mph']:.0f} mph", 52, INK, 300)
    elif seg == "K-braking":
        slow, fast = fr["parts"][0], fr["parts"][1]
        if fast["travel_m"] >= sm.stop_distance("slow"):
            _card(d, f"WHERE 30 STOPS, 40 STILL DOES {sm.fast_speed_where_slow_stops_mph():.0f} mph", 46, RED, H // 2 + 330)
    elif seg == "L-driver":
        _card(d, f"SAME DRIVER \u00b7 +{pct}% ENERGY", 56, RED, 170)
    elif seg == "M-twice":
        _card(d, "+10 mph \u2248 2\u00d7 THE CRASH", 64, RED, H // 2 + 330)


def compose(panels: Path, out: Path, n: int) -> tuple[list[dict], str]:
    out.mkdir(parents=True, exist_ok=True)
    frames, sha = {}, None
    for js in sorted(panels.rglob("speed-frames-*.json")):
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
                label_split(im, fr["segment"])
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
    """Every rendered part was drawn from the model state of its frame (same simulated time, crush, speed)."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        for part in fr["parts"]:
            if abs(part["t"] - round(sh["t"], 5)) > 1e-5:
                problems.append(f"frame {fr['frame']}: simulated time differs")
            elif sh.get("brake"):
                m = sm.brake_state(part["variant"], sh["t"])
                if abs(part["travel_m"] - m["x"]) > 2e-3:
                    problems.append(f"frame {fr['frame']} ({part['variant']}): braking position differs from the model")
            elif not sh.get("drop") or sh["t"] >= 0:
                m = sm.crash_state(part["variant"], sh["t"])
                if abs(part["crush_cm"] - 100 * m["s"]) > 0.02:
                    problems.append(f"frame {fr['frame']} ({part['variant']}): crush differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Both cars hit the wall inside the first second of the opening; by the end of the opening the 40 mph car has crushed more than the 30 mph
    car by the model's ratio; in the braking scene the 40 mph car passes the cone (where the 30 mph car stops) at about 35 mph."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr)
    problems = []
    a = by.get("A-split", [])
    hit_s = next((fr["frame"] / tl.FPS for fr in a if fr["parts"][0]["crush_cm"] > 0 and fr["parts"][1]["crush_cm"] > 0), None)
    if hit_s is None or hit_s > 1.0:
        problems.append(f"the crash does not land inside the first second ({hit_s})")
    if a:
        s0, s1 = a[-1]["parts"][0]["crush_cm"], a[-1]["parts"][1]["crush_cm"]
        if not (s1 > s0 + 15):
            problems.append(f"at the end of the opening the 40 mph car crushed {s1:.0f} cm vs {s0:.0f} cm")
    k = by.get("K-braking", [])
    passed = [fr["parts"][1]["mph"] for fr in k if fr["parts"][1]["travel_m"] >= sm.stop_distance("slow")]
    if not passed or abs(passed[0] - 35) > 1.5:
        problems.append(f"the 40 mph car does not pass the cone at about 35 mph ({passed[:1]})")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "hit_film_s": hit_s}


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
    video = a.out / "speed-film-1080x1920.mp4"
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
        "speed_physics": sm.speed_physics(),
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
    (a.out / "speed-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("SPEED_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("SPEED_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "96k", a.out / "speed-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
