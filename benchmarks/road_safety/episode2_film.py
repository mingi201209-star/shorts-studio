"""Episode-specific glue for existing native QA, measured speech and FFmpeg.

Speech/caption layout reuses the audited guardrail English review conventions.
No production engine/default changes; technical PASS never approves publishing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageFont, ImageStat

from shorts_studio.factory.rumble_episode2 import (
    caption_groups,
    load_episode,
    shot_for_frame,
    travel_x,
)
from shorts_studio.factory.rumble_native_shard_qa import verify
from shorts_studio.timing import WordTiming, validate_timings

ROOT = Path(__file__).resolve().parent
MANIFEST = Path("examples/factory/rumble-episode2-30s.json")
RENDERER = ROOT / "render_rumble_episode2.py"
# Lower captions sit on solid black below the native picture (rows 0..1399).
CAPTION_GUTTER_TOP = 1400


def run(args):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True, text=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-count_frames", "-show_streams",
                           "-show_format", "-of", "json", path]).stdout)


def stamp(t):
    n = round(t * 100)
    return f"{n // 360000}:{n // 6000 % 60:02}:{n // 100 % 60:02}.{n % 100:02}"


def silence(path):
    result = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
                  "silencedetect=noise=-35dB:d=0.3", "-vn", "-f", "null", "-"])
    gaps = [float(n) for n in re.findall(r"silence_duration:\s*([0-9.]+)", result.stderr)]
    assert max(gaps, default=0) <= .9, ("LONG_DEAD_AIR", gaps)
    assert sum(gaps) <= 5, ("EXCESSIVE_TOTAL_SILENCE", gaps)
    return gaps


def speech(out):
    episode = load_episode(MANIFEST)
    capture = ROOT / "episode2_narration"
    provenance = json.loads((capture / "capture.json").read_text())
    assert (provenance["voice"], provenance["rate"]) == ("en-US-AndrewNeural", "+5%")
    assert len(provenance["shots"]) == 6
    cues, pieces, reports = [], [], []
    normalize = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    for i, (shot, rec) in enumerate(zip(episode["shots"], provenance["shots"]), 1):
        assert rec["id"] == i and rec["text"] == shot["narration_en"]
        for key in ("audio", "raw_audio", "timing"):
            assert digest(capture / rec[key]) == rec[key + "_sha256"], key
        metadata = json.loads((capture / rec["timing"]).read_text())
        assert metadata["voice"] == provenance["voice"] and metadata["rate"] == provenance["rate"]
        words = [WordTiming(**w) for w in metadata["words"]]
        assert normalize(" ".join(w.text for w in words)) == normalize(rec["text"])
        duration = float(probe(capture / rec["audio"])["format"]["duration"])
        validate_timings(words, duration)
        assert 0 < duration <= 4.75 and max(w.end for w in words) + .1 <= duration
        offset = (i - 1) * 5 + .1
        tokens = rec["text"].split()
        assert [normalize(t) for t in tokens] == [normalize(w.text) for w in words]
        for j, k in caption_groups(rec["text"]):
            group = words[j:k]
            cues.append({"start": offset + group[0].start, "end": offset + group[-1].end,
                         "text": " ".join(w.text for w in group), "shot": shot["id"]})
        wav = out / f"voice_{i:02}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", capture / rec["audio"], "-af",
             "adelay=100,apad=whole_dur=5", "-t", "5", "-ar", "48000", "-ac", "1", wav])
        pieces.append(wav)
        reports.append({"shot": shot["id"], "duration": duration, "words": metadata["words"]})
    concat = out / "voice-concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in pieces))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat,
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=9", "-ar", "48000", "-ac", "1", out / "narration.wav"])
    assert abs(float(probe(out / "narration.wav")["format"]["duration"]) - 30) < .02
    run(["ffmpeg", "-v", "error", "-y", "-i", out / "narration.wav", "-c:a", "aac",
         "-b:a", "192k", out / "audio-preflight.m4a"])
    gaps = silence(out / "audio-preflight.m4a")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 62)
    events = []
    assert all(a["end"] <= b["start"] for a, b in pairwise(cues))
    for cue in cues:
        assert 0 <= cue["start"] < cue["end"] <= 30
        text = cue["text"]
        assert len(text) <= 31, text
        if len(text) > 24:
            tokens = text.split()
            text = " ".join(tokens[:len(tokens) // 2]) + r"\N" + " ".join(tokens[len(tokens) // 2:])
        assert all(font.getlength(line) <= 900 for line in text.split(r"\N")), text
        events.append(f"Dialogue: 0,{stamp(cue['start'])},{stamp(cue['end'])},Caption,,0,0,0,,{text}")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,62,&H00FFFFFF,&H00FFFFFF,&H00130F0B,&H80130F0B,0,0,0,0,100,100,0,0,1,4,1,2,90,90,325,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    (out / "film.ass").write_text(header + "\n".join(events) + "\n")
    (out / "captions.srt").write_text("\n\n".join(
        f"{i}\n0{stamp(c['start']).replace('.', ',')}0 --> 0{stamp(c['end']).replace('.', ',')}0\n{c['text']}"
        for i, c in enumerate(cues, 1)) + "\n")
    (out / "narration_validation.json").write_text(json.dumps({
        "status": "PASS", "voice": provenance["voice"], "rate": provenance["rate"],
        "timing_source": "provider-word-boundaries", "shots": reports, "cues": cues,
        "silence_seconds": gaps, "upper_overlays": False, "human_approved": False}, indent=2))
    print("MEASURED_ENGLISH_SPEECH_PASS", len(cues), gaps, flush=True)


def shard(out):
    qa = verify(out, MANIFEST, RENDERER)
    proof = json.loads((out / "episode-proof.json").read_text())
    first, count = proof["first_frame"], proof["frames"]
    assert count in (10, 30) and first in range(1, 901, 10)
    clip = out / "native-lossless.mkv"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", "30", "-start_number", first,
         "-i", out / "frame_%04d.png", "-frames:v", count, "-c:v", "ffv1", "-level", "3",
         "-g", "1", "-slicecrc", "1", "-pix_fmt", "bgr0", clip])
    # FFV1 transports every exact decoded RGB pixel, avoiding intermediate lossy compression.
    for i, rec in enumerate(proof["original_frame_records"]):
        rec["rgb_sha256"] = hashlib.sha256(run_rgb(out / f"frame_{first + i:04d}.png")).hexdigest()
    decoded = run(["ffmpeg", "-v", "error", "-i", clip, "-pix_fmt", "rgb24", "-f", "framehash",
                   "-hash", "sha256", "-"]).stdout
    hashes = [line.split(",")[-1].strip() for line in decoded.splitlines() if not line.startswith("#")]
    assert hashes == [r["rgb_sha256"] for r in proof["original_frame_records"]]
    proof["lossless_clip_sha256"] = digest(clip)
    proof["native_qa"] = qa
    (out / "episode-proof.json").write_text(json.dumps(proof, indent=2))
    print("LOSSLESS_NATIVE_SHARD_PASS", first, count, flush=True)


def caption_filter(out):
    return (f"setpts=N/(30*TB),drawbox=x=0:y={CAPTION_GUTTER_TOP}:w=1080:"
            f"h={1920 - CAPTION_GUTTER_TOP}:color=black:t=fill,ass={out / 'film.ass'}")


def run_rgb(path):
    with Image.open(path) as image:
        return image.convert("RGB").tobytes()


def validate_shard_layout(proofs):
    """Allow exact old30/new10 spans, while preserving the complete900-frame gate."""
    expected = 1
    for proof in proofs:
        first, last, count = proof["first_frame"], proof["last_frame"], proof["frames"]
        assert type(first) is type(last) is type(count) is int
        assert first == expected and first in range(1, 901, 10), "GAP_OR_OVERLAP"
        assert count in (10, 30) and last == first + count - 1 and last <= 900
        assert proof["frame_numbers"] == list(range(first, last + 1))
        assert [r["frame"] for r in proof["original_frame_records"]] == proof["frame_numbers"]
        expected = last + 1
    assert expected == 901, "MISSING_NATIVE_FRAMES"


def assemble(out, chunks):
    episode = load_episode(MANIFEST)
    records, files, cameras, durations = [], [], {}, []
    dirs = sorted(chunks.glob("rumble-native-*"), key=lambda p: int(p.name.rsplit("-", 1)[-1]))
    proofs = [json.loads((directory / "episode-proof.json").read_text()) for directory in dirs]
    validate_shard_layout(proofs)
    reused_starts = set(json.loads(os.environ.get("RUMBLE_CACHE_STARTS", "[]")))
    assert reused_starts <= {p["first_frame"] for p in proofs}
    reused_frames = sum(p["frames"] for p in proofs if p["first_frame"] in reused_starts)
    for directory, proof in zip(dirs, proofs):
        count = proof["frames"]
        clip = directory / "native-lossless.mkv"
        assert proof["renderer_source_sha256"] == digest(RENDERER)
        assert proof["source_sha256"] == episode["source_scene_sha256"]
        assert proof["resolution"] == [1080, 1920] and proof["cycles_samples"] == 32
        assert proof["renderer"] == "CYCLES" and proof["fps"] == 30 and not proof["preview_only"]
        assert proof["native_qa"]["status"] == "PASS_NATIVE_ORIGINAL_SHARD"
        assert proof["native_qa"]["frames"] == count
        assert proof["car_mesh_parts"] >= 65 and proof["rotating_wheel_pivots"] == 4
        assert proof["physically_calibrated"] is False and proof["upload_ready"] is False
        assert proof["lossless_clip_sha256"] == digest(clip)
        video = next(s for s in probe(clip)["streams"] if s["codec_type"] == "video")
        assert (video["width"], video["height"], video["r_frame_rate"],
                int(video["nb_read_frames"]), video["codec_name"]) == (1080, 1920, "30/1", count, "ffv1")
        hashes = run(["ffmpeg", "-v", "error", "-i", clip, "-pix_fmt", "rgb24", "-f",
                      "framehash", "-hash", "sha256", "-"]).stdout
        hashes = [s.split(",")[-1].strip() for s in hashes.splitlines() if not s.startswith("#")]
        assert hashes == [r["rgb_sha256"] for r in proof["original_frame_records"]]
        for shot_id, camera in proof["camera_by_shot"].items():
            assert shot_id not in cameras or cameras[shot_id] == camera, "CAMERA_RESET_AT_SHARD"
            cameras[shot_id] = camera
        records.extend(proof["original_frame_records"])
        durations.extend(proof["render_seconds"])
        files.append(clip)
    assert [r["frame"] for r in records] == list(range(1, 901))
    assert len({r["sha256"] for r in records}) == len({r["rgb_sha256"] for r in records}) == 900
    assert set(cameras) == {s["id"] for s in episode["shots"]}
    for rec in records:
        assert rec["shot_id"] == shot_for_frame(episode, rec["frame"])["id"]
        assert abs(rec["absolute_x_m"] - travel_x(rec["frame"])) < .000001
    speech(out)
    concat = out / "native-concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in files))
    final = out / "rumble-strips-english-30s-1080p.mp4"
    start = time.perf_counter()
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat,
         "-i", out / "narration.wav", "-vf", caption_filter(out), "-map", "0:v:0",
         "-map", "1:a:0", "-t", "30", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final])
    elapsed = time.perf_counter() - start
    info = probe(final)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (video["width"], video["height"], video["r_frame_rate"], int(video["nb_read_frames"]),
            video["codec_name"], video["pix_fmt"]) == (1080, 1920, "30/1", 900, "h264", "yuv420p")
    assert audio["codec_name"] == "aac" and audio["sample_rate"] == "48000" and audio["channels"] == 1
    assert abs(float(info["format"]["duration"]) - 30) < .04
    run(["ffmpeg", "-v", "error", "-i", final, "-f", "null", "-"])
    md5 = run(["ffmpeg", "-v", "error", "-i", final, "-map", "0:v:0", "-f", "framemd5", "-"]).stdout
    hashes = [s.split(",")[-1].strip() for s in md5.splitlines() if not s.startswith("#")]
    assert len(hashes) == len(set(hashes)) == 900, "HELD_OR_DUPLICATED_VIDEO_FRAME"
    (out / "decoded-video.framemd5").write_text(md5)
    black = run(["ffmpeg", "-hide_banner", "-i", final, "-vf",
                 "blackdetect=d=0.15:pix_th=0.06", "-an", "-f", "null", "-"]).stderr
    assert "black_start:" not in black, "BLACK_FRAME_RUN"
    gaps = silence(final)
    for i, second in enumerate([.5, 4.4, 5.5, 9.4, 10.5, 14.4, 15.5, 19.4, 20.5, 24.4, 25.5, 29.4]):
        run(["ffmpeg", "-v", "error", "-y", "-ss", second, "-i", final, "-frames:v", "1",
             out / f"review_{i:02d}.jpg"])
        with Image.open(out / f"review_{i:02d}.jpg") as review:
            gutter = review.convert("L").crop((0, CAPTION_GUTTER_TOP, 1080, CAPTION_GUTTER_TOP + 40))
            picture = review.convert("L").crop((0, 0, 1080, CAPTION_GUTTER_TOP))
            assert max(gutter.getextrema()) <= 24, "CAPTION_GUTTER_NOT_BLACK"
            assert ImageStat.Stat(picture).mean[0] >= 25, "PICTURE_ABOVE_GUTTER_BLACK"
    report = {"technical_status": "PASS", "frames": 900, "duration": 30,
              "resolution": [1080, 1920], "samples": 32, "native_frames": records,
              "source_sha256": episode["source_scene_sha256"], "camera_by_shot": cameras,
              "lossless_intermediate": True, "decoded_unique_video_frames": len(set(hashes)),
              "reused_native_frames": reused_frames, "new_native_frames": 900 - reused_frames,
              "cache_source_run_id": os.environ.get("RUMBLE_CACHE_RUN_ID"),
              "silence_seconds": gaps, "maximum_silence_seconds": max(gaps, default=0),
              "total_silence_seconds": sum(gaps), "upper_overlays": False,
              "render_frame_seconds": durations, "sum_native_render_seconds": sum(durations),
              "encode_seconds": elapsed, "sha256": digest(final), "physics_validated": False,
              "editorial_status": "REQUIRES_HUMAN_REVIEW", "upload_authorized": False}
    (out / "film_validation.json").write_text(json.dumps(report, indent=2))
    (out / "script-en.txt").write_text("\n\n".join(s["narration_en"] for s in episode["shots"]) + "\n")
    print("EPISODE2_30S_900_NATIVE_TECHNICAL_PASS", report["sha256"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("speech", "shard", "assemble"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chunks", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.mode == "assemble":
        assemble(args.out, args.chunks)
    else:
        {"speech": speech, "shard": shard}[args.mode](args.out)
