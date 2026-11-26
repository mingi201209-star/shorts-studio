"""EP.34: composes the rendered arrester-net film frames, builds the sound mix (frozen narration + effects placed from the model,
net_sfx, with the channel's signature reveal sting), burns in the narration captions and runs every gate that can be decided from
the clip (physics, pace, opening hook, line alignment, telemetry, visible action, no scene text, loop, smoothness, black opening,
captions, audio). No text on the picture other than the captions. Never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil

import numpy as np
from pathlib import Path

from PIL import Image

from benchmarks import hook_gate
from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from benchmarks.truck_net import net_motion as m
from benchmarks.truck_net import net_sfx as sfx
from benchmarks.truck_net import net_timeline as tl
from shorts_studio.final_video_qa import verify_no_black_opening

ROOT = Path(__file__).resolve().parents[2]
AUDIO_DIR = ROOT / "examples/episodes/ep34-audio"
W, H = 1080, 1920
CAPTION_BAND = (1400, 1919)


def no_scene_text() -> dict:
    """No text in the 3D scene and none drawn in assembly: the only words on screen are the burned-in narration captions."""
    problems = []
    src = (Path(__file__).resolve().parent / "render_net_3d.py").read_text()
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
    for js in sorted(panels.rglob("net-frames-*.json")):
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
    """Every frame was drawn from the model state of its simulated time: the truck's front, the nets it has picked up and every net's
    tape payout (the reset shot: the nets hung again, no truck)."""
    problems = []
    for fr in frames:
        sh = tl.frame_state(fr["frame"], segs)
        p = fr["parts"][0]
        t, v = sh["t"], sh["variant"]
        if abs(p["t"] - round(t, 6)) > 1e-6 or p["variant"] != v:
            problems.append(f"frame {fr['frame']}: simulated time or variant differs")
            continue
        if v == "reset":
            if p["engaged"] != 0 or any(x > 0 for x in p["payout"]):
                problems.append(f"frame {fr['frame']}: the reset shot shows a net still pulled out")
        else:
            st = m.truck_state(t, v == "rating")
            if abs(p["front_y"] - st["front_y"]) > 1e-3 or p["engaged"] != st["engaged"]:
                problems.append(f"frame {fr['frame']}: the truck or the nets it has picked up differ from the model")
            if any(abs(a - b) > 1e-3 for a, b in zip(p["payout"], st["payout"])):
                problems.append(f"frame {fr['frame']}: a tape's payout differs from the model")
        if len(problems) > 5:
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def visible_action(frames: list[dict]) -> dict:
    """Frame 1 is the semi already in net 1 with tape pulled out; the truck is seen coming off the mountain highway into the nets; the
    nets are seen hung one after another; the wall is cut open on the absorbers (tape coiled inside) before the hit; net 2 is seen
    picked up and then its tape dragged through the pins in the cut-away; more nets are picked up one after another; the cab is seen
    as the truck comes to a stop; the 90 mph tanker is stopped by every net; the crew refills an open absorber; the loop runs into the
    opening's moment."""
    by = {}
    for fr in frames:
        by.setdefault(fr["segment"], []).append(fr["parts"][0])
    problems = []
    p0 = frames[0]["parts"][0]
    if not (p0["variant"] == "truck" and p0["engaged"] >= 1 and p0["payout"][0] > 0.3):
        problems.append(f"the first frame is not the semi already in net 1 with tape pulled out ({p0})")
    b = by.get("B-mountain", [])
    if not b or b[0]["engaged"] != 0 or b[-1]["engaged"] < 1:
        problems.append("the truck is not seen coming off the highway into the nets")
    c = by.get("C-nets-in-a-row", [])
    if not c or any(max(p["payout"]) > 0 for p in c):
        problems.append("the nets are not seen hung, waiting")
    d = by.get("D1-tied-to-tape", []) + by.get("D2-coiled", [])
    if not d or not all(p["cut"] for p in d) or any(max(p["payout"]) > 0 for p in d):
        problems.append("the wall is not cut open on the coiled tape before the hit")
    e1 = by.get("E1-truck-hits", [])
    if not e1 or e1[0]["payout"][1] > 0 or e1[-1]["payout"][1] <= 0:
        problems.append("the truck is not seen hitting net 2")
    e2 = by.get("E2-pins", [])
    if not e2 or not all(p["cut"] for p in e2) or e2[-1]["payout"][1] < e2[0]["payout"][1] + 2.0:
        problems.append("net 2's tape is not seen dragged through the pins in the cut-away")
    f = by.get("F-net-after-net", [])
    if not f or f[-1]["engaged"] - f[0]["engaged"] < 2:
        problems.append("the nets are not seen picked up one after another")
    g = by.get("G-driver", [])
    if not g or not all(p["driver"] for p in g) or g[-1]["speed"] > 0.0 or g[0]["speed"] <= 0.0:
        problems.append("the cab is not seen as the truck comes to a stop")
    h = by.get("H-ninety", [])
    if not h or h[0]["variant"] != "rating" or h[0]["speed"] < 35.0 or h[-1]["engaged"] != m.N_NETS or h[-1]["speed"] > 0.0:
        problems.append("the 90 mph tanker is not seen stopped by every net")
    i = by.get("I-fresh-tape", [])
    if not i or not all(p["open"] and p["variant"] == "reset" for p in i):
        problems.append("the crew is not seen at an open absorber")
    last = frames[-1]["parts"][0]
    if not (last["variant"] == "truck" and 0 < last["t"] <= p0["t"] + 1e-9):
        problems.append("the loop does not run into the opening's moment")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_frame": p0}


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
    video = a.out / "net-film-1080x1920.mp4"
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
        "net_physics": m.net_physics(),
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
    (a.out / "net-film-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("NET_FILM_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "segments"}, default=str), flush=True)
    print("NET_FILM_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", a.out / "net-film-540x960-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
