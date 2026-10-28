"""Explicit, hash-checked reuse of unchanged narration; no new TTS request."""
import hashlib
import json
import re
import shutil
from pathlib import Path

from .project import load_project
from .qa import subtitle_qa
from .subtitles import segment
from .timing import WordTiming, validate_timings


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identity(scene):
    return {"narration": scene.narration,
            "narration_plan": [p.model_dump(mode="json") for p in scene.narration_plan]}

def export_cache(manifest, source_build, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("narration cache already exists")
    project = load_project(str(manifest))
    destination.mkdir(parents=True)
    source = destination / "source-manifest.json"
    shutil.copyfile(manifest, source)
    entries = {}
    for scene in project.scenes:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", scene.id):
            raise ValueError("unsafe scene id")
        record = {"identity": identity(scene), "files": {}}
        for suffix in (".mp3", ".timing.json"):
            name = scene.id + suffix
            target = destination / name
            shutil.copyfile(Path(source_build) / name, target)
            record["files"][name] = digest(target)
        entries[scene.id] = record
    (destination / "manifest.json").write_text(json.dumps({
        "source_manifest_sha256": digest(source), "scenes": entries
    }, ensure_ascii=False, indent=2), encoding="utf-8")

def reuse_scene_audio(scene, build, cache):
    from .render import write_srt
    cache, build = Path(cache), Path(build)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", scene.id):
        raise ValueError("unsafe scene id")
    document = json.loads((cache / "manifest.json").read_text())
    if digest(cache / "source-manifest.json") != document["source_manifest_sha256"]:
        raise ValueError("narration cache source manifest changed")
    original = load_project(str(cache / "source-manifest.json"))
    original_scene = next(s for s in original.scenes if s.id == scene.id)
    record = document["scenes"][scene.id]
    if identity(scene) != identity(original_scene) or record["identity"] != identity(scene):
        raise ValueError("cached narration does not match current text and plan")
    expected = {scene.id + ".mp3", scene.id + ".timing.json"}
    if set(record["files"]) != expected:
        raise ValueError("unexpected narration cache files")
    for name, expected_hash in record["files"].items():
        path = cache / name
        if path.is_symlink() or digest(path) != expected_hash:
            raise ValueError("cached narration bytes changed")
    timing = json.loads((cache / (scene.id + ".timing.json")).read_text())
    words = [WordTiming(**word) for word in timing["words"]]
    if not words:
        raise ValueError("cached narration has no word timings")
    duration = max(w.end for w in words) + .08
    validate_timings(words, duration)
    caps = segment(words, duration)
    qa = subtitle_qa(caps, words, duration)
    if qa["status"] != "PASS":
        raise ValueError("cached narration caption coverage failed")
    build.mkdir(parents=True, exist_ok=True)
    for name in expected:
        shutil.copyfile(cache / name, build / name)
    srt = build / (scene.id + ".srt")
    write_srt(srt, caps)
    print("[narration-cache] verified original audio:", scene.id, flush=True)
    return build / (scene.id + ".mp3"), duration, srt, {"scene": scene.id, **qa}, caps, timing.get("units", [])
