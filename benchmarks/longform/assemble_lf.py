"""Long-form assembly: composes the rendered shots of every episode onto the long film's timeline (16:9, 1920x1080), lays the
narration blocks end to end, places each episode's own sound design under its shots (each sound module run on the episode's virtual
timeline), mixes for long-form (-14 LUFS), writes the film, an .srt of the narration and the chapter list, and runs the gates. No text
on the picture (captions go in the .srt). Never uploads.
Usage: PYTHONPATH=$PWD python3 benchmarks/longform/assemble_lf.py --film lf01 --panels DIR --out DIR [--frames-dir DIR]
(DIR holds every episode's rendered frames and frame logs, in any sub-folders)."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.guardrail_end.terminal_sfx import SR, db, limit, lufs, read_wav, write_wav
from benchmarks.longform import lf_timeline as lt
from benchmarks.road_safety.episode2_film import probe, run

W, H = lt.FRAME


def compose(film, lay: dict, panels: Path, out: Path, step: int = 1) -> dict:
    """Every final frame from its episode's rendered virtual frame (hashes checked; one renderer version per episode). With step > 1
    (local preview: every step-th virtual frame rendered) a missing frame holds the last rendered one of its shot. Frames are written
    as high-quality JPEG (a long film's PNGs would not fit on a runner's disk)."""
    out.mkdir(parents=True, exist_ok=True)
    got, shas = {}, {}
    for key in lay["episodes"]:
        prefix = lt.EPISODES[key][4]
        vframes = {}
        for js in sorted(panels.rglob(f"{prefix}*.json")):
            rec = json.loads(js.read_text())
            sha = rec["renderer_source_sha256"]
            if shas.setdefault(key, sha) != sha:
                raise SystemExit(f"{key}: mixed renderer versions across shards")
            for fr in rec["frames"]:
                path = js.parent / f"frame_{fr['frame']:05d}.png"
                if hashlib.sha256(path.read_bytes()).hexdigest() != fr["parts"][0]["sha256"]:
                    raise SystemExit(f"hash mismatch {path}")
                vframes[fr["frame"]] = (path, fr)
        need = sum(s["frames"] for s in lay["episodes"][key])
        if step == 1 and sorted(vframes) != list(range(need)):
            raise SystemExit(f"{key}: rendered {len(vframes)} of {need} virtual frames")
        if step > 1 and not set(range(0, need, step)) <= set(vframes):
            raise SystemExit(f"{key}: preview frames missing")
        got[key] = vframes
    telemetry = []
    for sh in lay["shots"]:
        last = None
        for i in range(sh["frames"]):
            v = sh["v0"] + i
            if v in got[sh["episode"]]:
                last = got[sh["episode"]][v]
            elif last is None:
                last = got[sh["episode"]][max(k for k in got[sh["episode"]] if k <= v)]
            path, fr = last
            im = Image.open(path).convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            im.save(out / f"frame_{sh['f0'] + i + 1:05d}.jpg", quality=95)
            if i == 0:
                telemetry.append({"shot": sh["row"], "episode": sh["episode"], "f0": sh["f0"], "segment_rendered": fr["segment"]})
    return {"renderer_source_sha256": shas, "first_frames": telemetry}


def narration_track(film, lay: dict) -> tuple[np.ndarray, list]:
    n = int(round(lay["frames"] / lt.FPS * SR))
    track = np.zeros(n)
    cues = []
    for b in lay["blocks"]:
        d = film.AUDIO_ROOT / b["id"]
        wav = read_wav(d / "narration.wav")
        a = json.loads((d / "audio-validation.json").read_text())
        if hashlib.sha256((d / "narration.wav").read_bytes()).hexdigest() != a["narration_sha256"]:
            raise SystemExit(f"{b['id']}: narration.wav differs from the frozen audio")
        i0 = int(round(b["t0"] * SR))
        m = min(len(wav), n - i0)
        track[i0:i0 + m] += wav[:m]
        cues += [{"start": b["t0"] + c["start"], "end": b["t0"] + c["end"], "text": c["text"]} for c in a["cues"]]
    return track, cues


def effects_track(film, lay: dict) -> tuple[np.ndarray, list]:
    """Each episode's own sound design, run on its virtual timeline, cut per shot and laid under that shot on the long film."""
    n = int(round(lay["frames"] / lt.FPS * SR))
    track = np.zeros(n)
    events = []
    for key, shots in lay["episodes"].items():
        tl = film.episode_timeline(key, lay)
        sfx = lt.fresh_module(lt.EPISODES[key][2])
        sfx.tl = tl
        nv = int(round(tl.frame_count() / lt.FPS * SR))
        fx, ev = sfx.render_sfx(nv, None)
        events += [dict(e, episode=key) for e in ev]
        for sh in [s for s in lay["shots"] if s["episode"] == key]:
            a0, a1 = int(round(sh["v0"] / lt.FPS * SR)), int(round((sh["v0"] + sh["frames"]) / lt.FPS * SR))
            b0 = int(round(sh["f0"] / lt.FPS * SR))
            seg = fx[a0:a1]
            m = min(len(seg), n - b0)
            fade = np.ones(m)
            k = min(int(0.01 * SR), m // 2)
            if k > 0:
                fade[:k] = np.linspace(0, 1, k)
                fade[-k:] = np.linspace(1, 0, k)
            track[b0:b0 + m] += seg[:m] * fade
    return track, events


def mix(narr: np.ndarray, fx: np.ndarray, out: Path, lay: dict, sfx_gain_db: float = -4.0, target_lufs: float = -14.0) -> dict:
    e = np.sqrt(np.convolve(narr ** 2, np.ones(1440) / 1440, mode="same"))
    e = np.convolve(e, np.ones(9600) / 9600, mode="same")
    duck = 1.0 - 0.6 * np.clip(e / 0.03, 0, 1)
    fx = fx * duck
    peak = np.max(np.abs(fx)) + 1e-9
    if peak > db(-3):
        fx *= db(-3) / peak
    m = limit(narr + db(sfx_gain_db) * fx, ceiling_db=-2.0)
    write_wav(out / "mix.wav", m)
    for _ in range(3):
        i_lufs, _tp = lufs(out / "mix.wav")
        if abs(i_lufs - target_lufs) < 0.3:
            break
        m = limit(m * db(target_lufs - i_lufs), ceiling_db=-2.0)          # inter-sample peaks read up to ~1 dB over the ceiling
        write_wav(out / "mix.wav", m)
    i_lufs, tp = lufs(out / "mix.wav")
    worst = 99.0
    for b in lay["blocks"]:
        i0, i1 = int(b["t0"] * SR), int((b["t0"] + b["speech_seconds"]) * SR)
        r_n = np.sqrt(np.mean(narr[i0:i1] ** 2)) + 1e-9
        r_s = np.sqrt(np.mean((db(sfx_gain_db) * fx[i0:i1]) ** 2)) + 1e-9
        worst = min(worst, 20 * math.log10(r_n / r_s))
    return {"mix_lufs": i_lufs, "mix_true_peak_dbfs": tp, "speech_over_effects_db_min": round(worst, 1)}


def srt(cues: list[dict], path: Path):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    lines = []
    for i, c in enumerate(cues, 1):
        lines += [str(i), f"{ts(c['start'])} --> {ts(c['end'])}", c["text"], ""]
    path.write_text("\n".join(lines), encoding="utf8")


def chapters(film, lay: dict) -> list[str]:
    names = getattr(film, "CHAPTER_NAMES", {})
    out = []
    for b in lay["blocks"]:
        s = int(b["t0"])
        out.append(f"{s // 60}:{s % 60:02d} {names.get(b['id'], b['id'])}")
    return out


def no_scene_text(lay: dict) -> dict:
    problems = []
    for key in lay["episodes"]:
        mod = importlib.util.find_spec(lt.EPISODES[key][1])
        src = Path(mod.origin).read_text()
        problems += [f"{key} renderer creates scene text ({b})" for b in ('"FONT"', "'FONT'", "body_text", "text_add") if b in src]
    me = Path(__file__).read_text()
    problems += [f"assembly draws text ({b})" for b in ("ImageDraw", "ImageFont") if me.count(b) > 1]
    return {"status": "FAIL" if problems else "PASS", "problems": problems}


def episode_physics(lay: dict) -> dict:
    rows, problems = {}, []
    for key in lay["episodes"]:
        mod = importlib.import_module(lt.EPISODES[key][5])
        r = getattr(mod, lt.EPISODES[key][6])()
        rows[key] = r["status"]
        if r["status"] != "PASS":
            problems.append(f"{key}: {r.get('problems')}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "episodes": rows}


def lines_shown(film, lay: dict) -> dict:
    """Every narration line starts on a shot chosen for that line (the show-what-is-said table)."""
    problems, table = [], []
    for b in film.BLOCKS:
        blk = next(x for x in lay["blocks"] if x["id"] == b["id"])
        a = json.loads((film.AUDIO_ROOT / b["id"] / "audio-validation.json").read_text())
        for i, bt in enumerate(a["beats"]):
            t = blk["t0"] + bt["start"] + 0.05
            sh = next((s for s in lay["shots"] if s["t0"] <= t < s["t1"]), None)
            want = [r for _, r, _ in b["lines"][i]]
            table.append({"block": b["id"], "line": i + 1, "text": bt["narration_en"], "shots": want})
            if sh is None or sh["row"] != want[0] or sh["line"] != i + 1:
                problems.append(f"{b['id']} line {i + 1} starts on {sh['row'] if sh else 'nothing'}, planned {want[0]}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": table}


def black_frames(frames_dir: Path, n: int) -> dict:
    dark = []
    for i in range(1, n + 1, 6):
        g = np.asarray(Image.open(frames_dir / f"frame_{i:05d}.jpg").convert("L").resize((96, 54)), dtype=np.float32)
        if g.mean() < 10.0:
            dark.append(i)
    return {"status": "FAIL" if dark else "PASS", "dark_frames": dark[:20]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--film", required=True)
    p.add_argument("--panels", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames-dir", type=Path, default=None)
    p.add_argument("--step", type=int, default=1, help="local preview: every step-th virtual frame was rendered")
    a = p.parse_args()
    film = importlib.import_module(f"benchmarks.longform.{a.film}")
    a.out.mkdir(parents=True, exist_ok=True)
    frames_dir = a.frames_dir or (a.out / "frames")
    lay = film.layout()
    comp = compose(film, lay, a.panels, frames_dir, a.step)
    narr, cues = narration_track(film, lay)
    fx, events = effects_track(film, lay)
    levels = mix(narr, fx, a.out, lay)
    (a.out / "sfx-events.json").write_text(json.dumps(events, indent=1))
    srt(cues, a.out / f"{a.film}.srt")
    chap = chapters(film, lay)
    (a.out / f"{a.film}-chapters.txt").write_text("\n".join(chap) + "\n")
    seconds = lay["frames"] / lt.FPS
    video = a.out / f"{a.film}-1920x1080.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(lt.FPS), "-i", str(frames_dir / "frame_%05d.jpg"), "-i", str(a.out / "mix.wav"),
         "-af", "apad", "-map", "0:v:0", "-map", "1:a:0", "-t", f"{seconds}", "-r", str(lt.FPS), "-c:v", "libx264", "-preset", "fast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", video])
    if shutil.which("ffprobe"):
        vs = next(s for s in probe(video)["streams"] if s["codec_type"] == "video")
        size_ok = (vs["width"], vs["height"], int(vs["nb_read_frames"])) == (W, H, lay["frames"])
    else:
        size_ok = True
    report = {
        "frames_complete": {"status": "PASS" if size_ok else "FAIL", "frames": lay["frames"], "seconds": round(seconds, 2)},
        "episode_physics": episode_physics(lay),
        "lines_shown": lines_shown(film, lay),
        "no_scene_text": no_scene_text(lay),
        "black_frames": black_frames(frames_dir, lay["frames"]),
        "smoothness": gates.smoothness(gray_diffs(video)) if a.step == 1 else {"status": "SKIPPED_PREVIEW", "step": a.step},
        "length": {"status": "PASS" if 240 <= seconds <= 600 else "FAIL", "seconds": round(seconds, 1)},
        "audio_mix": {"status": "PASS" if (-15.0 <= levels["mix_lufs"] <= -13.0 and levels["mix_true_peak_dbfs"] <= -1.0
                                           and levels["speech_over_effects_db_min"] >= 8.0) else "FAIL", **levels},
    }
    ok = ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING") + (("SKIPPED_PREVIEW",) if a.step > 1 else ())
    report["preview_status"] = "PASS" if all(v["status"] in ok for v in report.values() if isinstance(v, dict) and "status" in v) else "FAIL"
    report.update(renderer_source_sha256=comp["renderer_source_sha256"], chapters=chap, shots=len(lay["shots"]),
                  note="preview only: nothing uploaded; the sound mix and voice are not human-checked; a human first view UNVERIFIED")
    (a.out / f"{a.film}-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("LF_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items()
                                      if k not in ("chapters", "renderer_source_sha256")}, default=str), flush=True)
    print("LF_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}, default=str)[:3000], flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=960:540", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k",
         a.out / f"{a.film}-960x540-review.mp4"])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
