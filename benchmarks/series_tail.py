"""Series tail: a short teaser of the next part after a Short's last frame, so a viewer who liked the Short has a reason to subscribe
(owner plan 2026-11-26, after "the views are high but almost nobody subscribes"). The tail is the next episode's opening shot (its
clean rendered frames, without captions) with its own effects ducked under one spoken line, for example "Subscribe for part two: what
stops a giant ship.", captioned in the channel's style. The Short's loop is given up for the teaser (accepted by the owner).

The finished film is re-encoded once with the tail appended. Its picture and its mix are not changed, apart from short fades at the
cut and one overall loudness trim of the whole new mix.

Gates:
- length and frame count;
- the film part unchanged (PSNR against the input film; its sound against the input mix);
- the tail frames are the next episode's rendered frames (hash-checked against its frame records);
- captions on the picture, saying exactly the spoken line;
- loudness, true peak, and the line above the effects;
- no frozen frame and no black opening.
Never uploads.

usage: python3 -m benchmarks.series_tail --film FILM.mp4 --film-dir DIR --narration narration.wav --next-panels DIR \
           --next-sfx sfx.wav --cta DIR --out OUT [--frames 84] [--voice-at 0.25]
- FILM-DIR holds the film's final mix.wav, sfx.wav and film.ass (the CI final job's outputs next to FILM.mp4).
- NEXT-PANELS holds the next episode's rendered frames and their frame records (its CI panel shards).
- CTA is a frozen spoken line: cta.wav (48 kHz mono) and cta.json (text and measured word timings)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.assemble_crumple_preview import gray_diffs
from benchmarks.guardrail_end.terminal_sfx import SR, db, limit, lufs, read_wav, write_wav
from benchmarks.road_safety.episode2_film import probe, run, stamp
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.factory.rumble_episode2 import caption_groups
from shorts_studio.final_video_qa import verify_no_black_opening

W, H, FPS = 1080, 1920, 24
CAPTION_BAND = (1400, 1919)
SFX_GAIN_DB = -2.0           # effects sit 2 dB under the narration before the film's loudness normalisation (every film's build())
DUCK_DB = -6.0               # the next episode's effects under the spoken line
RAMP_S = 0.08
FADE_S = 0.008               # either side of the cut, so neither sound clicks
END_FADE_S = 0.04
TARGET_LUFS = -15.0
MAX_SECONDS = 40.0
MIN_FILM_PSNR_DB = 38.0


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cta(cta_dir: Path) -> tuple[dict, np.ndarray]:
    rec = json.loads((cta_dir / "cta.json").read_text())
    if sha256(cta_dir / "cta.wav") != rec["wav_sha256"]:
        raise SystemExit("cta.wav differs from the frozen line")
    if len(rec["words"]) != len(rec["text"].split()):
        raise SystemExit("one measured timing per spoken word (no invented timing)")
    return rec, read_wav(cta_dir / "cta.wav")


def voice_span(cta: dict, voice_at: float) -> tuple[float, float]:
    """Tail time of the first word's onset and of the last word's end, with the line placed so its first word starts at voice_at."""
    w = cta["words"]
    return voice_at, voice_at + w[-1]["end"] - w[0]["start"]


def cues(cta: dict, offset: float, voice_at: float, tail_s: float) -> list[dict]:
    """Caption cues of the spoken line, in film time: grouped like every film's captions (caption_groups) and timed from the measured
    word timings. The last cue stays up to the tail's last frame (the video ends on it)."""
    words, tokens = cta["words"], cta["text"].split()
    shift = offset + voice_at - words[0]["start"]
    out = []
    for j, k in caption_groups(cta["text"]):
        text = " ".join(tokens[j:k])
        if len(text) > 24:                                   # the films' rule: long groups go on two lines
            parts = text.split()
            text = " ".join(parts[:len(parts) // 2]) + r"\N" + " ".join(parts[len(parts) // 2:])
        out.append({"start": shift + words[j]["start"], "end": shift + words[k - 1]["end"], "text": text})
    out[-1]["end"] = offset + tail_s
    return out


def duck(n: int, spans: list[tuple[float, float]], depth_db: float = DUCK_DB, ramp_s: float = RAMP_S) -> np.ndarray:
    """Gain curve for the effects: 1 outside the spoken spans, depth_db inside, raised-cosine ramps of ramp_s before and after."""
    t = np.arange(n) / SR
    g = np.ones(n)
    lo = db(depth_db)
    for a, b in spans:
        w = ((t >= a) & (t <= b)).astype(float)
        up = (t > a - ramp_s) & (t < a)
        w[up] = 0.5 - 0.5 * np.cos(np.pi * (t[up] - (a - ramp_s)) / ramp_s)
        down = (t > b) & (t < b + ramp_s)
        w[down] = 0.5 + 0.5 * np.cos(np.pi * (t[down] - b) / ramp_s)
        g = np.minimum(g, 1.0 - w * (1.0 - lo))
    return g


def rms_db(x: np.ndarray) -> float:
    return 20 * math.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-12)


def build_audio(film_dir: Path, narration_wav: Path, next_sfx_wav: Path, cta: dict, voice: np.ndarray, voice_at: float, tail_s: float,
                out: Path) -> dict:
    """The film's mix, then the tail: the spoken line at the film narration's loudness over the next episode's effects (ducked under
    the line), both scaled by the film's own normalisation gain so the tail sits at the film's level. One overall trim to -15 LUFS."""
    mix = read_wav(film_dir / "mix.wav")
    n = len(mix)
    narr = np.pad(read_wav(narration_wav), (0, n))[:n]
    fx = np.pad(read_wav(film_dir / "sfx.wav"), (0, n))[:n]
    pre = narr + db(SFX_GAIN_DB) * fx
    g_film = float(np.dot(mix, pre) / np.dot(pre, pre))       # least squares: the film's limiter only touched a few peaks
    fit = rms_db(mix - g_film * pre) - rms_db(mix)
    if fit > -12.0:
        raise SystemExit(f"the film's mix is not its narration + effects (residual {fit:.1f} dB): wrong files?")
    lv = out / "_levels"
    lv.mkdir(parents=True, exist_ok=True)
    write_wav(lv / "narration.wav", narr)
    write_wav(lv / "line.wav", voice)
    l_narr, _ = lufs(lv / "narration.wav")
    l_line, _ = lufs(lv / "line.wav")
    m = int(round(tail_s * SR))
    placed = np.zeros(m)
    i0 = int(round((voice_at - cta["words"][0]["start"]) * SR))
    src = voice[max(0, -i0):] * db(l_narr - l_line)
    src = src[:m - max(0, i0)]
    placed[max(0, i0):max(0, i0) + len(src)] = src
    nfx = np.pad(read_wav(next_sfx_wav), (0, m))[:m]
    span = voice_span(cta, voice_at)
    under = db(SFX_GAIN_DB) * nfx * duck(m, [span])
    tail = (placed + under) * g_film
    f = int(FADE_S * SR)
    head = mix.copy()
    head[-f:] *= np.linspace(1.0, 0.0, f)
    tail[:f] *= np.linspace(0.0, 1.0, f)
    e = int(END_FADE_S * SR)
    tail[-e:] *= np.linspace(1.0, 0.0, e)
    full = limit(np.concatenate([head, tail]), ceiling_db=-2.0)
    write_wav(out / "mix.wav", full)
    trim_db = 0.0
    for _ in range(3):
        i_lufs, _tp = lufs(out / "mix.wav")
        if abs(i_lufs - TARGET_LUFS) < 0.3:
            break
        trim_db += TARGET_LUFS - i_lufs
        full = limit(full * db(TARGET_LUFS - i_lufs), ceiling_db=-2.0)
        write_wav(out / "mix.wav", full)
    i_lufs, tp = lufs(out / "mix.wav")
    write_wav(out / "tail-line.wav", placed * g_film)
    write_wav(out / "tail-effects.wav", under * g_film)
    a0, a1 = int(span[0] * SR), int(span[1] * SR)
    film_part = full[:n]
    gain = float(np.dot(film_part, mix) / np.dot(mix, mix))
    return {"mix_lufs": i_lufs, "mix_true_peak_dbfs": tp, "speech_over_effects_db_min": round(rms_db(placed[a0:a1]) - rms_db(under[a0:a1]), 1),
            "film_gain_fit": round(g_film, 4), "film_fit_residual_db": round(fit, 1), "line_gain_db": round(l_narr - l_line, 2),
            "overall_trim_db": round(trim_db, 2), "film_mix_gain_db": round(20 * math.log10(gain), 2),
            "film_mix_residual_db": round(rms_db(film_part[:-f] - gain * mix[:-f]) - rms_db(mix), 1), "film_samples": n, "tail_samples": m}


def tail_frames(next_panels: Path, count: int, out_dir: Path, first_number: int) -> dict:
    """The next episode's rendered frames 0..count-1, hash-checked against its frame records, scaled to 1080x1920 like every film's
    compose(), saved with the new film's 1-based frame numbers (first_number onward)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    recs = {}
    for js in sorted(next_panels.rglob("*-frames-*.json")):
        rec = json.loads(js.read_text())
        for fr in rec["frames"]:
            recs[fr["frame"]] = (js.parent, fr, rec["renderer_source_sha256"])
    missing = [k for k in range(count) if k not in recs]
    if missing:
        raise SystemExit(f"next episode frames missing: {missing[:5]}")
    shas = {recs[k][2] for k in range(count)}
    if len(shas) != 1:
        raise SystemExit("mixed renderer versions in the next episode's frames")
    segments = []
    for k in range(count):
        d, fr, _ = recs[k]
        path = d / f"frame_{k:05d}.png"
        if sha256(path) != fr["parts"][0]["sha256"]:
            raise SystemExit(f"hash mismatch {path}")
        im = Image.open(path).convert("RGB")
        if im.size != (W, H):
            im = im.resize((W, H), Image.LANCZOS)
        im.save(out_dir / f"frame_{first_number + k:04d}.png")
        if not segments or segments[-1] != fr["segment"]:
            segments.append(fr["segment"])
    return {"status": "PASS", "frames": count, "renderer_source_sha256": shas.pop(), "segments": segments}


def write_ass(style_ass: Path, out: Path, events: list[dict]) -> None:
    """The film's own caption header and style (its final film.ass), with only the tail's cues."""
    lines = style_ass.read_text(encoding="utf8").splitlines()
    k = next(i for i, ln in enumerate(lines) if ln.startswith("Format: Layer"))
    body = [f"Dialogue: 0,{stamp(c['start'])},{stamp(c['end'])},Caption,,0,0,0,,{c['text']}" for c in events]
    out.write_text("\n".join(lines[:k + 1] + body) + "\n", encoding="utf8")


def film_part_unchanged(video: Path, film: Path, n: int) -> dict:
    """The film's frames in the new video against the input film: one re-encode only (average PSNR)."""
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(video), "-i", str(film), "-filter_complex",
                          f"[0:v]trim=end_frame={n},setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]psnr", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"average:(inf|[0-9.]+)", err)
    psnr = float("inf") if m and m.group(1) == "inf" else float(m.group(1)) if m else 0.0
    return {"status": "PASS" if psnr >= MIN_FILM_PSNR_DB else "FAIL", "psnr_db": round(psnr, 2), "min_db": MIN_FILM_PSNR_DB}


def no_scene_text() -> dict:
    """The tail draws nothing: its only words are the burned-in captions of the spoken line."""
    me = Path(__file__).read_text()
    bad = [b for b in ("ImageDraw", "ImageFont", "drawtext") if me.count(b) > 1]           # once here, in this list
    return {"status": "FAIL" if bad else "PASS", "problems": [f"draws text ({b})" for b in bad]}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--film", type=Path, required=True)
    p.add_argument("--film-dir", type=Path, required=True)
    p.add_argument("--narration", type=Path, required=True)
    p.add_argument("--next-panels", type=Path, required=True)
    p.add_argument("--next-sfx", type=Path, required=True)
    p.add_argument("--cta", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames", type=int, default=84)
    p.add_argument("--voice-at", type=float, default=0.25)
    p.add_argument("--name", default="film-with-tail")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    info = probe(a.film)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    n = int(vs.get("nb_read_frames") or vs["nb_frames"])
    if (vs["width"], vs["height"]) != (W, H) or vs["r_frame_rate"] != f"{FPS}/1":
        raise SystemExit(f"film is {vs['width']}x{vs['height']} at {vs['r_frame_rate']}, expected {W}x{H} at {FPS}")
    film_s = n / FPS
    tail_s = a.frames / FPS
    cta, voice = load_cta(a.cta)
    if voice_span(cta, a.voice_at)[1] > tail_s - 0.2:
        raise SystemExit("the spoken line does not fit the tail with a breath after it: more frames or an earlier start")
    frames_dir = a.out / "tail-frames"
    frames_rec = tail_frames(a.next_panels, a.frames, frames_dir, n + 1)
    levels = build_audio(a.film_dir, a.narration, a.next_sfx, cta, voice, a.voice_at, tail_s, a.out)
    events = cues(cta, film_s, a.voice_at, tail_s)
    ass = a.out / "tail.ass"
    write_ass(a.film_dir / "film.ass", ass, events)
    total_s = film_s + tail_s
    video = a.out / f"{a.name}-1080x1920.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(a.film), "-framerate", str(FPS), "-start_number", str(n + 1), "-i", str(frames_dir / "frame_%04d.png"),
         "-i", str(a.out / "mix.wav"), "-filter_complex",
         f"[0:v]setsar=1[a];[1:v]format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1:a=0,setpts=N/({FPS}*TB),ass={ass}[v]",
         "-map", "[v]", "-map", "2:a:0", "-t", f"{total_s}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(video)])
    vi = next(s for s in probe(video)["streams"] if s["codec_type"] == "video")
    problems = []
    if (vi["width"], vi["height"], int(vi["nb_read_frames"])) != (W, H, n + a.frames):
        problems.append(f"video is {vi['width']}x{vi['height']} with {vi['nb_read_frames']} frames, expected {n + a.frames}")
    if total_s > MAX_SECONDS:
        problems.append(f"{total_s:.2f} s is over {MAX_SECONDS} s")
    said = " ".join(c["text"].replace(r"\N", " ") for c in events)
    audio_problems = []
    if not -16.5 <= levels["mix_lufs"] <= -13.5:
        audio_problems.append(f"mix loudness {levels['mix_lufs']} LUFS outside -16.5..-13.5")
    if levels["mix_true_peak_dbfs"] > -1.0:
        audio_problems.append(f"true peak {levels['mix_true_peak_dbfs']} dBFS above -1")
    if levels["speech_over_effects_db_min"] < 8.0:
        audio_problems.append(f"the line is only {levels['speech_over_effects_db_min']} dB above the effects")
    if abs(levels["film_mix_gain_db"] - levels["overall_trim_db"]) > 0.3 or levels["film_mix_residual_db"] > -30.0:
        audio_problems.append("the film's own sound changed beyond the overall trim")
    report = {
        "length": {"status": "FAIL" if problems else "PASS", "problems": problems, "film_frames": n, "tail_frames": a.frames,
                   "seconds": round(total_s, 3), "film_seconds": round(film_s, 3), "tail_seconds": round(tail_s, 3)},
        "film_part_unchanged": film_part_unchanged(video, a.film, n),
        "tail_is_next_episode": frames_rec,
        "captions_say_the_line": {"status": "PASS" if said == cta["text"] else "FAIL", "captions": said, "spoken": cta["text"]},
        "captions_visible": verify_captions_over_picture(video, frames_dir, [((c["start"] + c["end"]) / 2, CAPTION_BAND) for c in events], a.out, fps=FPS),
        "no_scene_text": no_scene_text(),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "audio_mix": {"status": "FAIL" if audio_problems else "PASS", "problems": audio_problems, **levels},
    }
    report["status"] = "PASS" if all(v["status"] in ("PASS", "AUTO_PASS_HUMAN_REVIEW_PENDING") for v in report.values()) else "FAIL"
    report.update(cues=events, film_sha256=sha256(a.film), cta_wav_sha256=cta["wav_sha256"], voice_at_s=a.voice_at,
                  loop="given up for the next-episode teaser (owner plan 2026-11-26)",
                  note="nothing uploaded; the sound and the voice are not human-checked")
    (a.out / f"{a.name}-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("SERIES_TAIL " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k != "cues"}, default=str), flush=True)
    bad = {k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") not in ("PASS", None)}
    if bad:
        print("SERIES_TAIL_DETAIL " + json.dumps(bad, default=str), flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "128k",
         str(a.out / f"{a.name}-540x960-review.mp4")])
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
