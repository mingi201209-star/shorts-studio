"""EP.04: the ONE low-cost contiguous preview of the whole film (26 s = TOTAL_FRAMES, low resolution): composes the rendered panels, muxes the narration with the burned-in captions,
and runs every gate that can be decided from this clip. Never a deliverable for publishing; never uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from benchmarks.crumple_zone import crumple_gates as gates
from benchmarks.crumple_zone.capabilities import CAPABILITIES
from benchmarks.crumple_zone import crumple_motion as cm
from benchmarks.crumple_zone import evidence_sim as es
from benchmarks.road_safety.episode2_film import probe, run
from benchmarks.speed_bump.assemble_speed_bump import verify_captions_over_picture
from shorts_studio.final_video_qa import verify_no_black_opening
from shorts_studio.scene_spec import evaluate_episode, full_render_allowed, load_spec, update_registry
from shorts_studio.scene_spec import validate as validate_spec

ROOT = Path(__file__).resolve().parents[2]
W, H = 1080, 1920
PLACE = {"full": {"crumple": (0, 0, 1080, 1920)}, "stack": {"crumple": (0, 0, 1080, 960), "rigid": (0, 960, 1080, 960)}, "sequential": {"crumple": (0, 0, 1080, 1920), "rigid": (0, 0, 1080, 1920)}}


def compose(panels: Path, out: Path):
    proofs = sorted(panels.rglob("crumple-proof.json"))
    if not proofs:
        raise SystemExit("no shards")
    index, telemetry, sha, evidence = {}, [], None, {}
    for pp in proofs:
        proof = json.loads(pp.read_text())
        if not proof.get("all_3d") or proof.get("overlays") != "none":
            raise SystemExit("shard was not produced by the overlay-free 3D renderer")
        if sha is None:
            sha = proof["renderer_source_sha256"]
        elif proof["renderer_source_sha256"] != sha:
            raise SystemExit("mixed renderer versions across shards")
        telemetry += proof["telemetry"]
        evidence.update({int(k): v for k, v in proof["evidence"].items()})
        for c in proof["checksums"]:
            path = pp.parent / f"frame_{c['frame']:04d}_{c['panel']}.png"
            if hashlib.sha256(path.read_bytes()).hexdigest() != c["sha256"]:
                raise SystemExit(f"hash mismatch {path}")
            index[(c["frame"], c["panel"])] = path
    telemetry.sort(key=lambda t: t["frame"])
    out.mkdir(parents=True, exist_ok=True)
    for f in range(1, cm.TOTAL_FRAMES + 1):
        seg = cm.segment_at(f)
        img = Image.new("RGB", (W, H), (0, 0, 0))
        for panel in cm.visible_panels(f):
            x, y, w, h = PLACE[seg["layout"]][panel]
            im = Image.open(index[(f, panel)]).convert("RGB")
            if im.size != (w, h):
                im = im.resize((w, h), Image.LANCZOS)
            img.paste(im, (x, y))
        img.save(out / f"frame_{f:04d}.png")
    return telemetry, sha, evidence


def gray_diffs(video: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "scale=135:240,format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, 240, 135).astype(float)
    return np.abs(np.diff(a, axis=0)).mean((1, 2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--panels", type=Path, required=True)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames-dir", type=Path, default=None)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    frames = a.frames_dir or (a.out / "frames")
    telemetry, sha, evidence = compose(a.panels, frames)
    audio_report = json.loads((a.audio / "audio-validation.json").read_text())
    frozen = json.loads((ROOT / "examples/experiments/crumple-zone-real-cues.json").read_text())
    narration_sha = hashlib.sha256((a.audio / "narration.wav").read_bytes()).hexdigest()
    if narration_sha != frozen["narration_sha256"] or audio_report["cues"] != frozen["cues"]:
        raise SystemExit("preview audio or measured cue timing differs from the frozen narration")
    for name in ("narration.wav", "film.ass"):
        (a.out / name).write_bytes((a.audio / name).read_bytes())
    ass = a.out / "film.ass"
    text = ass.read_text(encoding="utf8")
    style = ",0,0,1,3,0,2,90,90,210,1"
    if text.count(style) != 1:
        raise SystemExit("caption style line not in the expected form")
    ass.write_text(text.replace(style, ",0,0,1,6,2,2,90,90,420,1"), encoding="utf8")
    seconds = cm.TOTAL_FRAMES / cm.FPS
    video = a.out / "crumple-preview-1080x1920.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(cm.FPS), "-i", str(frames / "frame_%04d.png"), "-i", str(a.out / "narration.wav"),
         "-vf", f"setpts=N/({cm.FPS}*TB),ass={a.out / 'film.ass'}", "-map", "0:v:0", "-map", "1:a:0", "-t", f"{seconds}", "-c:v", "libx264", "-preset", "fast", "-crf", "17",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", video])
    info = probe(video)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    problems = []
    if (vs["width"], vs["height"], int(vs["nb_read_frames"])) != (W, H, cm.TOTAL_FRAMES):
        problems.append(f"video is {vs['width']}x{vs['height']} with {vs['nb_read_frames']} frames")

    def load(n):
        return np.array(Image.open(frames / f"frame_{n:04d}.png").convert("RGB"))

    cues = [c for c in audio_report["cues"] if c["end"] <= seconds - 0.1]
    recs = {k: cm.simulate(k) for k in cm.PROFILES}
    report = {
        "same_conditions": gates.same_conditions(recs),
        "energy_and_claims": gates.energy_and_claims(recs),
        "crush_map_keeps_the_cell": gates.crush_map_keeps_the_cell(),
        "telemetry_geometry": gates.telemetry_geometry(telemetry),
        "deformation_visible_by_2s": gates.deformation_visible_by(telemetry),
        "xray_against_road": gates.xray_against_road(es.Car(es.load_fixture()), range(1, cm.TOTAL_FRAMES + 1)),
        "labels_visible": gates.labels_visible(load, telemetry),
        "text_safe_area": gates.text_safe_area(),
        "smoothness": gates.smoothness(gray_diffs(video)),
        "sync_to_speech": gates.sync_to_speech(audio_report["cues"]),
        "black_opening": verify_no_black_opening(video, (0, 1440), a.out),
        "captions_visible": verify_captions_over_picture(video, frames, [((c["start"] + c["end"]) / 2, (1400, 1919)) for c in cues], a.out),
    }
    spec = load_spec(ROOT / "examples/episodes/ep04-crumple-zone-scene-spec.json")
    plan = json.loads((ROOT / "examples/experiments/crumple-zone-speech-plan.json").read_text())
    beats = [b["narration_en"] for b in plan["variants"][0]["beats"]]
    spec_problems = validate_spec(spec, beats)
    alignment = evaluate_episode(spec, audio_report["cues"], float(audio_report.get("target_seconds", cm.TOTAL_FRAMES / cm.FPS)), evidence)
    (a.out / "scene-alignment-report.json").write_text(json.dumps(alignment, indent=1))
    registry = update_registry(a.out / "scene-registry.json", spec.episode, a.out.name, alignment)
    allowed, reasons = full_render_allowed(spec, registry, CAPABILITIES, beats)
    report["scene_spec"] = {"status": "FAIL" if spec_problems else "PASS", "problems": spec_problems, "scenes": len(spec.scenes)}
    report["narration_visual_alignment"] = {"status": "FAIL" if alignment["overall"] == "FAIL" else alignment["overall"], "problems": [
        f"{sid}: {r['check']} {r.get('reason') or ''} {r.get('measured', '')} {r.get('delta_s', '')}" for sid, sc in alignment["scenes"].items() for r in sc["checks"] if r["status"] == "FAIL"],
        "verdicts": {sid: sc["verdict"] for sid, sc in alignment["scenes"].items()}, "covered_seconds": alignment["covered_seconds"]}
    report["full_render_allowed"] = {"status": "PASS" if allowed else "BLOCKED", "reasons": reasons}
    ok_status = ("PASS", "PENDING_MORE_FRAMES", "AUTO_PASS_HUMAN_REVIEW_PENDING", "BLOCKED")
    report["preview_status"] = "PASS" if not problems and all(v["status"] in ok_status for k, v in report.items() if isinstance(v, dict) and "status" in v) else "FAIL"
    report["problems"] = problems
    report["renderer_source_sha256"] = sha
    report["caption_cues_in_clip"] = [(round(c["start"], 2), round(c["end"], 2), c["text"]) for c in cues]
    report["note"] = "preview only: not a deliverable, no upload; voice pronunciation and human first view UNVERIFIED"
    (a.out / "crumple-preview-report.json").write_text(json.dumps(report, indent=1, default=str))
    print("CRUMPLE_PREVIEW_REPORT " + json.dumps({k: (v["status"] if isinstance(v, dict) and "status" in v else v) for k, v in report.items() if k not in ("caption_cues_in_clip",)}, default=str), flush=True)
    print("CRUMPLE_PREVIEW_DETAIL " + json.dumps({k: v for k, v in report.items() if isinstance(v, dict) and v.get("status") != "PASS"}, default=str), flush=True)
    print("SCENE_ALIGNMENT " + json.dumps(report["narration_visual_alignment"]), flush=True)
    print("FULL_RENDER_GATE " + json.dumps(report["full_render_allowed"]), flush=True)
    print("CRUMPLE_AUDIO_CUES " + json.dumps(report["caption_cues_in_clip"]), flush=True)
    video_review = a.out / "crumple-preview-540x960-review.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", "scale=540:960", "-c:v", "libx264", "-crf", "26", "-preset", "fast", "-c:a", "aac", "-b:a", "96k", video_review])
    if report["preview_status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
