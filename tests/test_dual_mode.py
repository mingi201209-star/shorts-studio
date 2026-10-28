import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from shorts_studio import dual_mode
from shorts_studio.asset_library import register
from shorts_studio.dual_mode import validate_motion


def motion_data(motion="rolling", count=4):
    data = {
        **dual_mode.PROFILE,
        "motion": motion,
        "simulation": "kinematic",
        "radius": 0.95,
        "speed": 0.6,
        "start_x": -0.3,
        "frames": count,
        "blender_version": "5.0.1",
        "frames_data": [],
    }
    for i in range(count):
        angle = data["speed"] * i / 30 / data["radius"] if motion == "rolling" else 0
        x = data["start_x"] + data["speed"] * i / 30
        data["frames_data"].append(
            {
                "frame": i + 1,
                "x": x,
                "z": 0.95,
                "angle": angle,
                "marker_x": x + 0.86 * math.cos(angle),
                "marker_z": 0.95 - 0.86 * math.sin(angle),
                "camera": [1.0] * 16,
                "bbox": [0.2, 0.3, 0.8, 0.7],
            }
        )
    return data


@pytest.mark.parametrize("motion", ["rolling", "locked"])
def test_native_motion_contract_does_not_claim_physics_or_final_qa(motion):
    result = validate_motion(motion_data(motion))
    assert result["status"] == "PASS_KINEMATIC_NATIVE"
    assert result["native_frames"] == 4
    assert not result["physics_simulation_validated"]
    assert not result["production_approved"]


@pytest.mark.parametrize(
    "attack", ["spin", "contact", "translation", "camera", "clipping", "missing", "profile", "nan"]
)
def test_motion_mismatch_cannot_pass(attack):
    data = motion_data()
    row = data["frames_data"][-1]
    if attack == "spin":
        row["marker_z"] = row["z"]
    elif attack == "contact":
        row["z"] += 0.1
    elif attack == "translation":
        row["x"] += 0.1
    elif attack == "camera":
        row["camera"] = [2.0] * 16
    elif attack == "clipping":
        row["bbox"][0] = -0.01
    elif attack == "missing":
        data["frames_data"].pop()
    elif attack == "profile":
        data["samples"] = 7
    else:
        row["angle"] = float("nan")
    with pytest.raises(ValueError):
        validate_motion(data)


def test_rolling_and_locked_are_different_measured_phenomena():
    data = motion_data("rolling")
    data["motion"] = "locked"
    with pytest.raises(ValueError):
        validate_motion(data)


def test_cache_tampering_fails_before_decode(tmp_path, monkeypatch):
    specification = {"motion": "rolling", "frames": 4}
    key = dual_mode.fingerprint(specification)
    root = tmp_path / key
    root.mkdir()
    names = ("clip.mp4", "scene.blend", "motion.json")
    for name in names:
        (root / name).write_bytes(b"original")
    (root / "proof.json").write_text(
        json.dumps(
            {
                "key": key,
                "specification": specification,
                "outputs": {name: hashlib.sha256(b"original").hexdigest() for name in names},
            }
        )
    )
    (root / "clip.mp4").write_bytes(b"changed")

    def forbidden(*args):
        raise AssertionError("must reject byte mismatch before any decode")

    monkeypatch.setattr(dual_mode, "validate_clip", forbidden)
    with pytest.raises(ValueError, match="cached output changed"):
        dual_mode.validate_cached(root, key, "ffmpeg", "ffprobe")


def test_fast_never_silently_creates_a_missing_asset(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()

    def forbidden(*args):
        raise AssertionError("Fast cannot build an unknown asset")

    monkeypatch.setattr(dual_mode, "command", forbidden)
    with pytest.raises(ValueError, match="Premium first"):
        dual_mode.owned_asset(
            "fast", tmp_path / "library", cache, Path("blender"), {"runtime": "fixture"}
        )


def test_timeout_preserves_log_and_stops_process(tmp_path):
    log = tmp_path / "timeout.log"
    with pytest.raises(subprocess.TimeoutExpired):
        dual_mode.command(
            [sys.executable, "-u", "-c", "import time; print('started'); time.sleep(30)"], log, 0.3
        )
    assert "started" in log.read_text()


def test_owned_bundle_has_traced_source_but_no_production_approval(tmp_path):
    source = tmp_path / "bundle"
    source.mkdir()
    (source / "asset.blend").write_bytes(b"fixture; not Blender QA")
    (source / "frame.png").write_bytes(b"fixture; not image QA")
    (source / "builder_source.py").write_text("# fixture owned builder")
    source_hash = hashlib.sha256((source / "builder_source.py").read_bytes()).hexdigest()
    (source / "asset.json").write_text(
        json.dumps(
            {
                "asset": "wheel",
                "view": "side",
                "motion": "static_object_view",
                "source_sha256": source_hash,
                "blend_sha256": hashlib.sha256((source / "asset.blend").read_bytes()).hexdigest(),
                "image_sha256": hashlib.sha256((source / "frame.png").read_bytes()).hexdigest(),
                "editorial_approved": False,
                "interaction_physics_validated": False,
            }
        )
    )
    provenance = {
        "license": "OWNED",
        "creator": "Shorts Studio procedural builder",
        "external_assets": [],
        "builder_source_sha256": source_hash,
        "blender_version": "5.0.1",
    }
    (source / "provenance.json").write_text(json.dumps(provenance))
    names = ("asset.blend", "frame.png", "asset.json", "builder_source.py", "provenance.json")
    outputs = {
        name: {
            "bytes": (source / name).stat().st_size,
            "sha256": hashlib.sha256((source / name).read_bytes()).hexdigest(),
        }
        for name in names
    }
    (source / "manifest.json").write_text(json.dumps({"outputs": outputs}))
    record = register(source, tmp_path / "library")
    assert record["license_status"] == "declared_owned"
    assert record["production_approved"] is False
    assert record["physics_validated"] is False
    fresh_cache = tmp_path / "fresh-cache"
    fresh_cache.mkdir()
    found, built = dual_mode.owned_asset(
        "fast",
        tmp_path / "library",
        fresh_cache,
        Path("not-executed"),
        {"builder_sha256": source_hash},
    )
    assert found["id"] == record["id"]
    assert built is False
    (source / "builder_source.py").write_text("# different builder")
    outputs["builder_source.py"] = {
        "bytes": (source / "builder_source.py").stat().st_size,
        "sha256": hashlib.sha256((source / "builder_source.py").read_bytes()).hexdigest(),
    }
    (source / "manifest.json").write_text(json.dumps({"outputs": outputs}))
    with pytest.raises(ValueError, match="provenance mismatch"):
        register(source, tmp_path / "library")


def test_failed_stage_keeps_evidence_and_is_not_a_valid_scene(tmp_path):
    with (
        pytest.raises(RuntimeError, match="evidence retained"),
        dual_mode.staging(tmp_path, ".scene-") as directory,
    ):
        (directory / "render.log").write_text("real diagnostic")
        raise ValueError("render failed")
    failed = list(tmp_path.glob(".failed-*"))
    assert len(failed) == 1
    assert (failed[0] / "render.log").read_text() == "real diagnostic"


def test_benchmark_resumes_completed_stages_without_replaying_them(tmp_path, monkeypatch):
    """Synthetic orchestration receipts are not actual render/quality evidence."""
    from types import SimpleNamespace

    from shorts_studio.dual_mode_benchmark import benchmark

    args = SimpleNamespace(
        library=tmp_path / "library",
        cache=tmp_path / "cache",
        blender=tmp_path / "blender",
        receipt=tmp_path / "result.json",
        frames=4,
        resume=False,
    )
    monkeypatch.setattr(
        "shorts_studio.dual_mode_benchmark.shutil.which", lambda name: "/fixture/" + name
    )
    monkeypatch.setattr(dual_mode, "runtime", lambda *a: {"fixture": True})
    monkeypatch.setattr(dual_mode, "validate_cached", lambda *a: {"fixture": True})
    calls = []
    interrupted = [False]

    def fake_run(mode, motion, library, cache, blender, frames):
        calls.append((mode, motion))
        if motion == "locked" and not interrupted[0]:
            interrupted[0] = True
            raise RuntimeError("fixture interruption before new scene starts")
        key = dual_mode.fingerprint({"motion": motion})
        root = cache / "scenes" / key
        root.mkdir(parents=True, exist_ok=True)
        clip = root / "clip.mp4"
        clip.write_bytes(("fixture " + motion).encode())
        return {
            "key": key,
            "mode": mode,
            "motion": motion,
            "asset_id": "fixture-model",
            "asset_built": mode == "premium",
            "visual_cache_hit": mode == "fast" and motion == "rolling",
            "wall_seconds": 10 if mode == "premium" else 1,
            "clip_path": str(clip),
            "clip_sha256": dual_mode.sha(clip),
        }

    monkeypatch.setattr(dual_mode, "run", fake_run)
    with pytest.raises(RuntimeError, match="fixture interruption"):
        benchmark(args, dual_mode)
    args.resume = True
    result = benchmark(args, dual_mode)
    assert result["same_scene_bit_identical"]
    assert calls == [
        ("premium", "rolling"),
        ("fast", "rolling"),
        ("fast", "locked"),
        ("fast", "locked"),
    ]
    assert result["premium_cold"]["wall_seconds"] == 10


def test_benchmark_missing_media_tools_fails_before_any_work(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from shorts_studio.dual_mode_benchmark import benchmark

    monkeypatch.setattr("shorts_studio.dual_mode_benchmark.shutil.which", lambda name: None)
    args = SimpleNamespace(receipt=tmp_path / "result.json")
    with pytest.raises(ValueError, match="ffmpeg and ffprobe"):
        benchmark(args, dual_mode)
    assert not args.receipt.with_suffix(".phases").exists()
