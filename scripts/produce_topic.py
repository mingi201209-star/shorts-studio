#!/usr/bin/env python3
"""Produce one Short from a topic spec, end to end, against a wall clock.

    python scripts/produce_topic.py topics/<topic>.json --out build/topics/<topic>

Stages (each timed into ``production_report.json``):

  build      pinned downloads, FFmpeg clip preparation, callout overlays, hook judge, manifest
  validate   the unchanged ``shorts_studio validate`` contracts
  prescreen  the renderer's own CLIP provider on every prepared picture, before the render
  render     the unchanged ``shorts_studio render`` with SHORTS_REQUIRE_SEMANTIC_QA=1
  inspect    contact sheets of the real frames, audio measurements, ASR read-back of the narration

The clock starts at ``--clock-file`` (created on first use), so research and writing the
spec count toward the budget when the file is created before that work starts. A missed
budget or a failed gate is reported as such; nothing here can turn it into a pass.

The prescreen and the inspection are aids. Neither replaces a gate, and neither is a
verdict on how the narration sounds to a person.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shorts_studio.topic_builder import BOX_H, BOX_W, StageTimer, build_topic, load_topic  # noqa: E402

# Media box rows in the composed 1080x1920 frame (shorts_studio.render IMAGE_TOP_Y / IMAGE_BOX_HEIGHT).
FRAME_W, MEDIA_TOP, MEDIA_H = 1080, 280, 950
PRESCREEN_RISKY_MARGIN = 0.05


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _frame(video: Path, seconds: float, out: Path) -> Path:
    r = _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, seconds):.3f}", "-i", str(video),
              "-frames:v", "1", "-q:v", "2", str(out)])
    if r.returncode != 0 or not out.is_file():
        raise RuntimeError(f"could not read a frame at {seconds:.2f}s from {video}: {r.stderr[-300:]}")
    return out


def _duration(path: Path) -> float:
    r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], check=True)
    return float(r.stdout.strip())


CUT_MIN_SCORE = 0.12
CUT_ISOLATION = 4.0


def source_cuts(asset: Path, seconds: float) -> list[float]:
    """Times of hard cuts inside the part of a prepared clip that will be on screen.

    Stock and agency footage is often an edited compilation. A cut to another
    shot in the middle of a beat puts a picture on screen that nobody chose,
    and a callout then points at nothing.

    A cut is one isolated spike in FFmpeg's scene-change score. Calibrated on
    real clips: hard cuts in dark orbital footage score 0.21-0.41 against a
    next-highest 0.01-0.04; continuous fast change (aurora timelapse 0.12 vs
    0.06, a solar flare flash 0.22 vs 0.22) is not isolated and is not a cut."""
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-t", f"{seconds:.3f}", "-i", str(asset), "-vf",
              "select='gte(scene,0)',metadata=print", "-f", "null", "-"])
    scores = [(float(t), float(s)) for t, s in
              re.findall(r"pts_time:(\d+(?:\.\d+)?)\s*\n\[[^\]]*\] lavfi\.scene_score=(\d+(?:\.\d+)?)", r.stderr)]
    cuts = []
    for i, (when, score) in enumerate(scores):
        others = [s for j, (_, s) in enumerate(scores) if abs(j - i) > 2]
        if score >= CUT_MIN_SCORE and score >= CUT_ISOLATION * max(others, default=0.0):
            cuts.append(round(when, 2))
    return cuts


# visual_change.verify_observed_changes fails a beat whose rendered media box
# differs from its pinned source by more than this mean absolute error.
RENDERED_STATE_MAX_ERROR = 8.0


def _gate_canvas(picture):
    """A prepared picture placed in the media box the way that gate compares it."""
    import cv2
    import numpy as np
    canvas = np.zeros((MEDIA_H, FRAME_W, 3), np.uint8)
    h, w = picture.shape[:2]
    canvas[(MEDIA_H - h) // 2:(MEDIA_H - h) // 2 + h, (FRAME_W - w) // 2:(FRAME_W - w) // 2 + w] = picture
    return cv2.resize(canvas, (256, 256)).astype(float)


def opening_motion(asset: Path, hold: float) -> dict:
    """How far the frames on screen near the gate's sampling time differ from
    the frame the render-integrity gate takes as the pinned source.

    The gate samples the source with OpenCV's millisecond seek at
    min(0.25 s, hold/2), which returns the frame *after* the one on screen at
    that moment, and a beat whose start falls late on the frame grid shows
    the frame before that. On steady footage those frames are nearly equal;
    on fast or handheld high-texture footage the difference alone exceeds the
    gate's threshold, so the beat fails after a full render. Calibrated on 15
    rendered beats: this predicts each measured gate error to within 0.6."""
    import cv2
    import numpy as np
    offset = min(0.25, max(0.0, hold / 2))
    cap = cv2.VideoCapture(str(asset))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.set(cv2.CAP_PROP_POS_MSEC, offset * 1000.0)
        ok, sampled = cap.read()
        if not ok:
            raise RuntimeError(f"cannot decode {asset.name} at {offset:.2f}s")
        reference = _gate_canvas(sampled)
        shown = int(offset * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, shown - 1))
        errors = []
        for _ in range(2):
            ok, frame = cap.read()
            if ok:
                errors.append(round(float(np.abs(_gate_canvas(frame) - reference).mean()), 2))
    finally:
        cap.release()
    worst = max(errors, default=0.0)
    return {"worst_error": worst, "errors": errors, "risky": worst > RENDERED_STATE_MAX_ERROR}


def gate_frame(asset: Path, hold: float):
    """The picture the meaningful-visual-changes gate observes for a beat, placed
    in the media box: a still as the renderer fits it, a video at min(0.25 s, hold/2)."""
    import cv2
    import numpy as np
    if asset.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        picture = cv2.imread(str(asset))
        h, w = picture.shape[:2]
        scale = min(BOX_W / w, BOX_H / h)
        picture = cv2.resize(picture, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        cap = cv2.VideoCapture(str(asset))
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(min(0.25, max(0.0, hold / 2)) * (cap.get(cv2.CAP_PROP_FPS) or 30.0)))
            ok, picture = cap.read()
        finally:
            cap.release()
        if not ok:
            raise RuntimeError(f"cannot decode {asset.name}")
    canvas = np.zeros((MEDIA_H, FRAME_W, 3), np.uint8)
    h, w = picture.shape[:2]
    canvas[(MEDIA_H - h) // 2:(MEDIA_H - h) // 2 + h, (FRAME_W - w) // 2:(FRAME_W - w) // 2 + w] = picture
    return canvas


def _frame_at(asset: Path, seconds: float):
    import cv2
    if asset.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        return gate_frame(asset, 0.0)
    cap = cv2.VideoCapture(str(asset))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        last = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1) - 1
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(last, int(seconds * fps))))
        ok, picture = cap.read()
    finally:
        cap.release()
    if not ok:
        raise RuntimeError(f"cannot decode {asset.name} at {seconds:.2f}s")
    import numpy as np
    canvas = np.zeros((MEDIA_H, FRAME_W, 3), np.uint8)
    h, w = picture.shape[:2]
    canvas[(MEDIA_H - h) // 2:(MEDIA_H - h) // 2 + h, (FRAME_W - w) // 2:(FRAME_W - w) // 2 + w] = picture
    return canvas


def steadier_starts(source: Path, clip, window: float = 8.0, keep: int = 3) -> list[float]:
    """Start times near ``clip.start`` whose opening frames would pass
    ``opening_motion``, steadiest first.

    The source is decoded once, cropped and scaled as the clip will be, and
    resampled to the prepared clip's 30 fps; each candidate start is scored
    exactly like ``opening_motion`` scores a prepared clip."""
    import cv2
    import numpy as np
    from shorts_studio.topic_builder import _probe_video, _resolved_crop
    info = _probe_video(source)
    w, h, x, y = (int(v) for v in _resolved_crop(clip, info["width"], info["height"]).split(":"))
    lo, hi = max(0.0, clip.start - window), clip.start + window + 1.0
    cap = cv2.VideoCapture(str(source))
    times, frames = [], []
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, lo * 1000.0)
        while True:
            ok, frame = cap.read()
            when = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if not ok or when > hi:
                break
            times.append(when)
            frames.append(_gate_canvas(cv2.resize(frame[y:y + h, x:x + w], (BOX_W, BOX_H))))
    finally:
        cap.release()
    times = np.array(times)
    if len(times) < 10:
        return []

    def at(seconds):
        return frames[int(np.abs(times - seconds).argmin())]
    scored = []
    for start in np.arange(lo, min(hi, times[-1] - clip.seconds / clip.slowmo) + 1e-6, 0.1):
        shown = int(0.25 * 30)
        reference = at(start + (shown + 1) / 30 / clip.slowmo)
        worst = max(float(np.abs(at(start + k / 30 / clip.slowmo) - reference).mean()) for k in (shown - 1, shown))
        if worst <= RENDERED_STATE_MAX_ERROR - 1.0:
            scored.append((worst, round(float(start), 1)))
    picked = []
    for _, start in sorted(scored):
        if all(abs(start - other) >= 1.0 for other in picked):
            picked.append(start)
        if len(picked) == keep:
            break
    return picked


def static_runs(beats: list[tuple[str, Path, float]], max_static_seconds: float = 5.0, margin: float = 0.5) -> list[str]:
    """Stretches the real-activity gate would read as one static picture.

    final_video_qa.measure_visual_activity counts a change only where two
    media-box samples differ by VISUAL_CHANGE_THRESHOLD; a cut between two
    windows of the same slow timelapse, or between near-identical pictures,
    stays under it, and the beats on either side add up to one long hold
    (5.5 s for two sunset-timelapse windows 3 s apart). This compares each
    beat's last frame with the next beat's first frame using that threshold
    and reports runs longer than the gate's limit less a sampling margin.
    Changes inside a beat are not credited, so a reported run may still pass."""
    import numpy as np
    from shorts_studio.final_video_qa import VISUAL_CHANGE_THRESHOLD
    edges = []
    for (_, asset, hold), (_, following, _) in zip(beats, beats[1:]):
        a, b = _frame_at(asset, max(0.0, hold - 0.05)), _frame_at(following, 0.0)
        edges.append(float(np.abs(a.astype(int) - b.astype(int)).mean()) >= VISUAL_CHANGE_THRESHOLD)
    found, run, names = [], beats[0][2] if beats else 0.0, [beats[0][0]] if beats else []
    for cut, (name, _, hold) in zip(edges + [True], beats[1:] + [("", None, 0.0)]):
        if cut:
            if run > max_static_seconds - margin and len(names) > 1:
                found.append(f"{' + '.join(names)} read as one {run:.1f}s picture")
            run, names = hold, [name]
        else:
            run, names = run + hold, names + [name]
    return found


def replayed_pictures(beats: list[tuple[str, str, object]]) -> list[str]:
    """Beats the gate would call an equivalent crop/zoom or a replay, found with
    the gate's own ``equivalent_framing`` before anything is rendered.

    ``beats`` is (name, source attribution, gate frame) in screen order. Like the
    gate, each beat is compared with the one before it and with every earlier
    one; earlier beats from another source are skipped, because a crop or zoom
    of one source cannot be registered onto a different one and the gate's
    SIFT comparison is the slow part of its check."""
    from shorts_studio.visual_change import equivalent_framing
    found = []
    for i, (name, source, frame) in enumerate(beats):
        earlier = [(j, other) for j, (_, other_source, other) in enumerate(beats[:i])
                   if j == i - 1 or other_source == source]
        hit = next((beats[j][0] for j, other in earlier if equivalent_framing(other, frame)), None)
        if hit:
            found.append(f"{name} repeats the picture of {hit}")
    return found


def prescreen(manifest: dict, work: Path, holds: list[float]) -> dict:
    """Judge every prepared picture with the renderer's own composite vision provider
    (clarity, provenance hash, CLIP subject) -- the same object the render gate uses --
    on the frame the gate will sample: the middle of the beat's measured time on screen.

    Each picture is placed on black exactly as the media box holds it. A failing
    or narrow result here costs seconds; the same result after a render costs
    minutes. A source-internal cut inside the beat also fails here."""
    from PIL import Image
    from shorts_studio.visual_qa import default_vision_provider
    work.mkdir(parents=True, exist_ok=True)
    rows, strips = [], []
    beats = [(scene, index, beat) for scene in manifest["scenes"] for index, beat in enumerate(scene["visual_beats"])]
    if len(holds) != len(beats):
        raise ValueError(f"{len(holds)} measured beat lengths for {len(beats)} beats")
    # Cheap, decisive check first: a beat this gate is bound to fail is
    # reported before the vision model is even loaded.
    motion = {}
    for (scene, index, beat), hold in zip(beats, holds):
        asset = Path(beat["asset"])
        if asset.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            motion[(scene["id"], index)] = opening_motion(asset, hold)
    unsteady = [f"{sid}[{i}] {Path(next(b['asset'] for s in manifest['scenes'] if s['id'] == sid for b in [s['visual_beats'][i]])).name}"
                f" ({m['worst_error']:.1f})" for (sid, i), m in motion.items() if m["risky"]]
    replays = replayed_pictures([(f"{scene['id']}[{index}] {Path(beat['asset']).name}", beat.get("attribution", ""),
                                  gate_frame(Path(beat["asset"]), hold))
                                 for (scene, index, beat), hold in zip(beats, holds)])
    merged = static_runs([(f"{scene['id']}[{index}] {Path(beat['asset']).name}", Path(beat["asset"]), hold)
                          for (scene, index, beat), hold in zip(beats, holds)])
    if merged:
        return {"status": "FAIL", "beats": [], "sheet": None,
                "reason": "the real-activity gate would see no cut between these beats (same-looking pictures back to back); "
                          "separate them with a different shot: " + "; ".join(merged)}
    if replays:
        return {"status": "FAIL", "beats": [], "sheet": None,
                "reason": "the meaningful-visual-changes gate would reject a repeated picture (crop, zoom or replay "
                          "of an earlier beat); use a different shot: " + "; ".join(replays)}
    if unsteady:
        return {"status": "FAIL", "beats": [], "sheet": None,
                "reason": f"opening frames move more than the render-integrity gate tolerates (>{RENDERED_STATE_MAX_ERROR:.0f}); "
                          f"choose a steadier start or shot: {', '.join(unsteady)}",
                "opening_motion": {f"{sid}[{i}]": m for (sid, i), m in motion.items()}}
    provider = default_vision_provider()
    for (scene, index, beat), hold in zip(beats, holds):
        asset = Path(beat["asset"])
        still = asset.suffix.lower() in {".jpg", ".jpeg", ".png"}
        name = f"{scene['id']}_{index:02d}"
        if not still and _duration(asset) < hold - 0.05:
            raise ValueError(f"{asset.name} is {_duration(asset):.2f}s but its beat is on screen for {hold:.2f}s")
        times = [0.0, hold / 2, max(0.0, hold - 0.1)]
        frames = []
        for n, seconds in enumerate(times):
            picture = Image.open(asset if still else _frame(asset, seconds, work / f"{name}_raw{n}.jpg")).convert("RGB")
            frames.append(picture.resize((BOX_W, BOX_H), Image.LANCZOS))
        canvas = Image.new("RGB", (FRAME_W, MEDIA_H), (0, 0, 0))
        canvas.paste(frames[1], ((FRAME_W - BOX_W) // 2, (MEDIA_H - BOX_H) // 2))
        boxed = work / f"{name}_box.jpg"
        canvas.save(boxed, quality=92)
        verdict = provider.evaluate(boxed, beat["visual_qa_requirements"],
                                    positive_labels=beat["visual_qa_labels"],
                                    negative_labels=beat["visual_qa_negative_labels"],
                                    expected_asset_sha256=beat["visual_qa_expected_sha256"], asset_path=asset,
                                    media_box_applied=True)
        subs = {s.get("provider"): s for s in verdict.get("sub_results", [])}
        margin = subs.get("ClipSemanticVisionProvider", {}).get("margin")
        sharpness = subs.get("ClarityVisionProvider", {}).get("sharpness")
        failed = [f"{provider_name}: {s.get('reason')}" for provider_name, s in subs.items() if s.get("status") == "FAIL"]
        cuts = [] if still else source_cuts(asset, hold)
        if cuts:
            failed.append(f"the source cuts to another shot at {cuts}s inside this {hold:.2f}s beat")
        status = "FAIL" if cuts else verdict["status"]
        rows.append({"beat": f"{scene['id']}[{index}]", "asset": asset.name, "status": status,
                     "seconds_on_screen": round(hold, 2),
                     "opening_motion": (motion.get((scene["id"], index)) or {}).get("worst_error"),
                     "margin": None if margin is None else round(margin, 4),
                     "sharpness": None if sharpness is None else round(sharpness, 1),
                     "risky": status != "PASS" or (margin is not None and margin < PRESCREEN_RISKY_MARGIN),
                     "reason": "; ".join(failed) or verdict.get("reason")})
        strips.append((f"{scene['id']}[{index}] {asset.name} {hold:.1f}s", frames))
    status = "PASS" if all(r["status"] == "PASS" for r in rows) else "FAIL"
    return {"status": status, "beats": rows, "sheet": str(picture_sheet(strips, work))}


def picture_sheet(strips: list, work: Path) -> Path:
    """One row per beat: its first, middle and last frame on screen, with a 100 px grid
    in picture coordinates on the middle frame.

    This is what the author looks at before rendering and reads callout positions
    from; it is an authoring aid, not evidence."""
    from PIL import Image, ImageDraw
    tile_w, tile_h = BOX_W // 2, BOX_H // 2
    rows_per_column = -(-len(strips) // 2)
    sheet = Image.new("RGB", (tile_w * 6 + 20, rows_per_column * (tile_h + 6)), (0, 0, 0))
    for i, (label, frames) in enumerate(strips):
        x0 = (i // rows_per_column) * (tile_w * 3 + 20)
        y0 = (i % rows_per_column) * (tile_h + 6)
        for n, frame in enumerate(frames):
            tile = frame.copy()
            draw = ImageDraw.Draw(tile)
            if n == 1:
                for x in range(100, BOX_W, 100):
                    draw.line((x, 0, x, BOX_H), fill=(255, 255, 0), width=1)
                    draw.text((x + 3, 2), str(x), fill=(255, 255, 0))
                for y in range(100, BOX_H, 100):
                    draw.line((0, y, BOX_W, y), fill=(255, 255, 0), width=1)
                    draw.text((3, y + 2), str(y), fill=(255, 255, 0))
            if n == 0:
                draw.rectangle((0, BOX_H - 34, 620, BOX_H), fill=(0, 0, 0))
                draw.text((8, BOX_H - 26), label[:80], fill=(255, 255, 255))
            sheet.paste(tile.resize((tile_w, tile_h)), (x0 + n * tile_w, y0))
    out = work / "pictures.jpg"
    sheet.save(out, quality=88)
    return out


def contact_sheets(video: Path, out_dir: Path, beat_starts: list[float]) -> dict:
    """Real frames from the final MP4: the first five seconds, and one frame per visual beat."""
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = _duration(video)

    def sheet(times: list[float], name: str, columns: int) -> str:
        frames = [_frame(video, min(t, duration - 0.05), out_dir / f"{name}_{i:02d}.jpg") for i, t in enumerate(times)]
        rows = -(-len(frames) // columns)
        inputs = [x for f in frames for x in ("-i", str(f))]
        # Keep title, picture and caption rows; drop the empty band below the captions.
        scaled = "".join(f"[{i}:v]crop=1080:1500:0:0,scale=432:600[s{i}];" for i in range(len(frames)))
        layout = "|".join(f"{(i % columns) * 432}_{(i // columns) * 600}" for i in range(len(frames)))
        joined = "".join(f"[s{i}]" for i in range(len(frames)))
        target = out_dir / f"{name}.jpg"
        r = _run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex",
                  f"{scaled}{joined}xstack=inputs={len(frames)}:layout={layout}:fill=black[v]", "-map", "[v]",
                  "-frames:v", "1", "-q:v", "3", str(target)])
        if r.returncode != 0:
            raise RuntimeError(f"contact sheet {name} failed: {r.stderr[-300:]} (rows={rows})")
        return str(target)

    first5 = sheet([0.15, 1.0, 2.0, 3.0, 4.0, 5.0], "first5s", 3)
    beats = sheet([t + 0.9 for t in beat_starts][:16], "beats", 4)
    return {"first5s": first5, "beats": beats, "duration": round(duration, 3)}


def audio_measurements(video: Path) -> dict:
    """What can be measured without ears: loudness, peak, and pauses inside the narration."""
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-map", "0:a:0", "-af",
              "ebur128=peak=true,silencedetect=noise=-38dB:d=0.7", "-f", "null", "-"])
    text = r.stderr
    loudness = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", text)
    peak = re.findall(r"Peak:\s+(-?\d+(?:\.\d+)?) dBFS", text)
    silences = [(float(a), float(b)) for a, b in re.findall(r"silence_end: (\d+(?:\.\d+)?) \| silence_duration: (\d+(?:\.\d+)?)", text)]
    return {"integrated_lufs": float(loudness[-1]) if loudness else None,
            "true_peak_dbfs": float(peak[-1]) if peak else None,
            "pauses_over_0_7s": [{"ends_at": round(a, 2), "seconds": round(b, 2)} for a, b in silences]}


def _plain(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text)


def asr_readback(video: Path, script: str, work: Path, model_name: str) -> dict:
    """Transcribe the final audio with faster-whisper and compare it with the script.

    This finds words a recogniser hears differently (a pronunciation or a cut
    worth a human listen). It does not measure naturalness, and a clean result
    is not approval of the voice."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"status": "NOT_EVALUATED", "reason": "faster-whisper is not installed"}
    wav = work / "narration_16k.wav"
    r = _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-map", "0:a:0", "-ac", "1", "-ar", "16000",
              "-c:a", "pcm_s16le", str(wav)])
    if r.returncode != 0:
        return {"status": "NOT_EVALUATED", "reason": f"could not decode audio: {r.stderr[-200:]}"}
    try:
        import numpy as np
        import wave
        with wave.open(str(wav), "rb") as handle:
            samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        # Decoded samples are passed in: faster-whisper's own file decoding
        # fails on this host's PyAV build.
        segments, _ = model.transcribe(samples, language="ko", beam_size=5, vad_filter=False)
        heard = " ".join(s.text.strip() for s in segments)
    except Exception as exc:  # a missing model download must not fail a finished production
        return {"status": "NOT_EVALUATED", "reason": f"ASR failed: {exc}"}
    a, b = _plain(script), _plain(heard)
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    differences = [{"script": a[i1:i2], "heard": b[j1:j2]} for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]
    return {"status": "EVALUATED", "model": model_name, "character_match": round(matcher.ratio(), 4),
            "heard": heard, "differences": differences[:20]}


def render_in_process(manifest_path: Path, out: Path, log: Path) -> int:
    """The unchanged ``shorts_studio render`` with SHORTS_REQUIRE_SEMANTIC_QA=1, in this process.

    Same function the CLI calls, same working directory, same flag. Run here
    rather than as ``python -m shorts_studio render`` because on this host
    importing torch/open_clip costs about 70 s per process and the prescreen
    has already paid it and loaded the CLIP model the render's gates use.
    The render's output goes to ``render.log``; its JSON result to
    ``render-result.json``, as the CLI would print it."""
    import contextlib
    import traceback
    from shorts_studio.render import render
    previous_cwd, previous_flag = Path.cwd(), os.environ.get("SHORTS_REQUIRE_SEMANTIC_QA")
    os.environ["SHORTS_REQUIRE_SEMANTIC_QA"] = "1"
    os.chdir(out)
    try:
        with log.open("w", encoding="utf-8") as handle, contextlib.redirect_stdout(handle), contextlib.redirect_stderr(handle):
            try:
                result = render(str(manifest_path))
            except Exception:  # the CLI would exit non-zero with this traceback
                traceback.print_exc()
                return 1
        (out / "render-result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return 0
    finally:
        os.chdir(previous_cwd)
        if previous_flag is None:
            os.environ.pop("SHORTS_REQUIRE_SEMANTIC_QA", None)
        else:
            os.environ["SHORTS_REQUIRE_SEMANTIC_QA"] = previous_flag


def gate_failures(qa: dict, log: Path) -> list[str]:
    """Name each failed gate with its own reason, so the fix is obvious without reading the log."""
    found = []
    for name, check in (qa.get("final_video_qa", {}).get("checks") or {}).items():
        if check.get("status") != "PASS":
            found.append(f"{name}: {check.get('reason')} {str(check.get('failures') or '')[:300]}".strip())
    for scene in (qa.get("semantic_visual_qa", {}).get("results") or []):
        for beat in scene.get("beat_results", [scene]):
            if beat.get("status") != "PASS":
                found.append(f"{beat.get('scene')}: {beat.get('status')} {beat.get('reason')}")
    for sub in qa.get("subtitle_reports") or []:
        if sub.get("status") != "PASS":
            found.append(f"subtitles {sub.get('scene')}: {sub}")
    if not found:
        tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:] if log.is_file() else []
        found.append("no gate result was written; last log line: " + (tail[0][-400:] if tail else "none"))
    return found


def beat_starts_from_report(report: dict) -> list[float]:
    checks = report.get("final_video_qa", {}).get("checks", {})
    timeline = (checks.get("visual_production_v2") or {}).get("evidence", {}).get("timeline") or []
    return [float(s["start"]) for s in timeline]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--font", default=None)
    ap.add_argument("--budget-minutes", type=float, default=30.0)
    ap.add_argument("--clock-file", type=Path, default=None,
                    help="file holding the UNIX start time of this production (created now if absent)")
    ap.add_argument("--cache", type=Path, default=REPO / "build" / "footage_cache",
                    help="shared download cache (files fetched while previewing are not requested twice)")
    ap.add_argument("--asr-model", default="large-v3-turbo")
    ap.add_argument("--skip-render", action="store_true", help="stop after the prescreen (authoring loop)")
    args = ap.parse_args()

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    clock_file = args.clock_file or out / "clock"
    if not clock_file.is_file():
        clock_file.parent.mkdir(parents=True, exist_ok=True)
        clock_file.write_text(f"{time.time():.2f}\n")
    clock_started = float(clock_file.read_text().strip())

    spec = load_topic(args.spec)
    timer = StageTimer()
    report: dict = {"topic": spec.topic_id, "clock_started_unix": clock_started,
                    "authoring_seconds_before_this_run": round(timer.started - clock_started, 2),
                    "budget_minutes": args.budget_minutes}

    def finish(status: str, reason: str | None = None) -> int:
        elapsed = time.time() - clock_started
        report.update({"status": status, "reason": reason, "timing": timer.report(),
                       "wall_clock_seconds": round(elapsed, 2),
                       "within_budget": elapsed <= args.budget_minutes * 60})
        (out / "production_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[production] {status} in {elapsed / 60:.1f} min of {args.budget_minutes:.0f} "
              f"(within budget: {report['within_budget']})" + (f" -- {reason}" if reason else ""), flush=True)
        return 0 if status == "PASS" and report["within_budget"] else 1

    built = build_topic(spec, out, font_path=args.font, timer=timer, cache_dir=args.cache)
    manifest_path: Path = built["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report["hook"] = {"strategy": built["hook"].strategy, "text": built["hook"].text}
    report["narration_timing"] = built["narration_timing"]

    env = {**os.environ, "PYTHONPATH": str(REPO) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    validated = timer.run("validate", _run, [sys.executable, "-m", "shorts_studio", "validate", str(manifest_path)], cwd=out, env=env)
    report["validate"] = (validated.stdout.strip() or validated.stderr.strip())[-2000:]
    if validated.returncode != 0:
        return finish("FAIL", "manifest failed the validate contracts")

    report["prescreen"] = timer.run("prescreen", prescreen, manifest, out / "work" / "prescreen",
                                    [b["seconds"] for b in built["narration_timing"]["beats"]])
    for row in report["prescreen"]["beats"]:
        if row["risky"]:
            print(f"[prescreen] {row['beat']} {row['asset']}: {row['status']} margin={row['margin']} "
                  f"sharpness={row['sharpness']} {row['reason'] or ''}", flush=True)
    unsteady = [key for key, m in (report["prescreen"].get("opening_motion") or {}).items() if m["risky"]]
    if unsteady:
        # Name a steadier start for each failing clip, so the fix is one edit.
        by_beat = {f"{scene.id}[{i}]": beat.asset for scene in spec.scenes for i, beat in enumerate(scene.beats)}
        hints = {}
        for name in unsteady:
            key = by_beat[name]
            key = spec.overlays[key].base if key in spec.overlays else key
            clip = spec.clips[key]
            source = next((out / "assets" / spec.topic_id / "sources").glob(f"{clip.source}.*"))
            hints[key] = timer.run(f"steadier_starts:{key}", steadier_starts, source, clip)
        report["prescreen"]["steadier_starts"] = hints
        report["prescreen"]["reason"] += " | steadier starts (seconds): " + ", ".join(f"{k}: {v or 'none within 8 s'}" for k, v in hints.items())
    if report["prescreen"]["status"] != "PASS":
        return finish("FAIL", report["prescreen"].get("reason")
                      or "a prepared picture does not pass the vision provider; fix the picture or its label before rendering")
    if args.skip_render:
        return finish("NOT_RENDERED", "stopped after the prescreen by --skip-render")

    returncode = timer.run("render", render_in_process, manifest_path, out, out / "render.log")
    qa_path = out / "dist" / "qa_report.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.is_file() else {}
    failed = sorted(k for k, v in (qa.get("final_video_qa", {}).get("checks") or {}).items() if v.get("status") != "PASS")
    report["render"] = {"returncode": returncode, "qa_status": qa.get("status"),
                        "semantic_required": qa.get("semantic_required"), "final_video_checks_not_pass": failed}
    video = out / "dist" / "final.mp4"
    if returncode != 0 or qa.get("status") != "PASS" or not video.is_file():
        return finish("FAIL", "render or QA gate failed: " + "; ".join(gate_failures(qa, out / "render.log")))

    script = " ".join(scene["narration"] for scene in manifest["scenes"])
    inspection = out / "inspection"
    inspection.mkdir(parents=True, exist_ok=True)
    # Independent reads of the finished file: the recogniser is the long one,
    # so the frame sheets and loudness run beside it instead of before it.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        heard = pool.submit(timer.run, "asr_readback", asr_readback, video, script, inspection, args.asr_model)
        sheets = pool.submit(timer.run, "contact_sheets", contact_sheets, video, inspection, beat_starts_from_report(qa))
        audio = pool.submit(timer.run, "audio_measurements", audio_measurements, video)
    report["inspection"] = {
        "sheets": sheets.result(),
        "audio": audio.result(),
        "asr_readback": heard.result(),
        "human_listening_verdict": "pending",
        "silent_interest_review": manifest["silent_interest_review"],
    }
    return finish("PASS")


if __name__ == "__main__":
    raise SystemExit(main())
