"""Opt-in Premium/Fast native asset and clean-clip pipeline; no publishing."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from .asset_library import inspect_bundle, register, search, sha

PROFILE = {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "samples": 32,
    "seed": 42,
    "renderer": "CYCLES",
}
MOTIONS = ("rolling", "locked")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def command(argv, log, timeout):
    with log.open("w") as stream:
        process = subprocess.Popen(
            argv, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
        if code:
            raise RuntimeError(f"command failed ({code}); inspect {log}")


@contextmanager
def staging(parent, prefix):
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    try:
        yield directory
    except BaseException as error:
        failed = parent / (".failed-" + directory.name.lstrip("."))
        directory.rename(failed)
        raise RuntimeError(f"stage failed; evidence retained at {failed}") from error
    else:
        shutil.rmtree(directory, ignore_errors=True)


def linked_dependencies(binary):
    output = subprocess.check_output(["ldd", str(binary)], text=True, timeout=30)
    if "not found" in output:
        raise ValueError("missing renderer shared library")
    paths = set()
    for line in output.splitlines():
        for token in line.split():
            if token.startswith("/") and Path(token).is_file():
                paths.add(Path(token))
    return {str(path): sha(path) for path in sorted(paths)}


def validate_motion(data):
    if data["simulation"] != "kinematic" or data["motion"] not in MOTIONS:
        raise ValueError("unsupported motion model")
    if any(data[key] != value for key, value in PROFILE.items()):
        raise ValueError("native profile mismatch")
    if data["blender_version"] != "5.0.1":
        raise ValueError("Blender version mismatch")
    count = data["frames"]
    rows = data["frames_data"]
    if type(count) is not int or not 2 <= count <= 300 or len(rows) != count:
        raise ValueError("native frame count mismatch")
    radius, speed = data["radius"], data["speed"]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in (radius, speed)):
        raise ValueError("invalid motion parameters")
    camera = rows[0]["camera"]
    if len(camera) != 16 or not all(math.isfinite(v) for v in camera):
        raise ValueError("invalid camera")
    errors = []
    for index, row in enumerate(rows):
        elapsed = index / PROFILE["fps"]
        expected_x = data["start_x"] + speed * elapsed
        expected_angle = speed * elapsed / radius if data["motion"] == "rolling" else 0
        values = [row["x"], row["z"], row["angle"], row["marker_x"], row["marker_z"]]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("non-finite native transform")
        measured_angle = math.atan2(-(row["marker_z"] - row["z"]), row["marker_x"] - row["x"])
        angle_error = abs(
            math.atan2(
                math.sin(measured_angle - expected_angle), math.cos(measured_angle - expected_angle)
            )
        )
        error = max(
            abs(row["x"] - expected_x),
            abs(row["z"] - radius),
            abs(row["angle"] - expected_angle),
            angle_error,
        )
        errors.append(error)
        if row["frame"] != index + 1 or error > 1e-5:
            raise ValueError("rolling/contact/locked-wheel motion mismatch")
        if row["camera"] != camera:
            raise ValueError("camera moved within shot")
        x0, y0, x1, y1 = row["bbox"]
        if not all(math.isfinite(v) for v in row["bbox"]) or not (
            0.03 < x0 < x1 < 0.97 and 0.03 < y0 < y1 < 0.97
        ):
            raise ValueError("wheel clipped or off camera")
    return {
        "status": "PASS_KINEMATIC_NATIVE",
        "max_transform_error": max(errors),
        "native_frames": count,
        "motion": data["motion"],
        "physics_simulation_validated": False,
        "production_approved": False,
    }


def validate_clip(root, ffmpeg, ffprobe):
    import numpy as np
    from PIL import Image

    data = json.loads((root / "motion.json").read_text())
    result = validate_motion(data)
    frames = sorted(root.glob("frame_*.png"))
    expected = [f"frame_{i:04}.png" for i in range(1, data["frames"] + 1)]
    if [p.name for p in frames] != expected:
        raise ValueError("missing or extra native source frames")
    hashes = []
    for path in frames:
        with Image.open(path) as image:
            image.load()
            if image.size != (1080, 1920):
                raise ValueError("source frame resolution mismatch")
            pixels = np.asarray(image.convert("RGB"))
            if not 3 < float(pixels.mean()) < 250 or float(pixels.std()) < 5:
                raise ValueError("blank native frame")
        hashes.append(sha(path))
    if len(set(hashes)) != len(hashes):
        raise ValueError("duplicate native source frames")
    probe = json.loads(
        subprocess.check_output(
            [
                ffprobe,
                "-v",
                "error",
                "-count_frames",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate,nb_read_frames",
                "-of",
                "json",
                str(root / "clip.mp4"),
            ],
            text=True,
            timeout=60,
        )
    )
    streams = probe["streams"]
    if len(streams) != 1 or any(
        streams[0].get(k) != v
        for k, v in {
            "width": 1080,
            "height": 1920,
            "r_frame_rate": "30/1",
            "nb_read_frames": str(data["frames"]),
        }.items()
    ):
        raise ValueError("encoded native profile mismatch")
    with tempfile.TemporaryDirectory(prefix=".decode-", dir=root.parent) as temporary:
        directory = Path(temporary)
        command(
            [
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(root / "clip.mp4"),
                "-vsync",
                "0",
                str(directory / "%04d.png"),
            ],
            directory / "decode.log",
            120,
        )
        decoded = sorted(directory.glob("*.png"))
        if len(decoded) != data["frames"] or len({sha(p) for p in decoded}) != len(decoded):
            raise ValueError("missing/duplicated decoded frames")
    result["decoded_unique_frames"] = len(decoded)
    result["source_frame_sha256"] = hashes
    return result


def validate_cached(root, expected_key, ffmpeg, ffprobe):
    if root.is_symlink() or (root / "proof.json").is_symlink():
        raise ValueError("symlinked scene cache")
    proof = json.loads((root / "proof.json").read_text())
    if fingerprint(proof["specification"]) != expected_key:
        raise ValueError("cache specification mismatch")
    if proof["key"] != expected_key or root.name != expected_key:
        raise ValueError("cache key mismatch")
    outputs = proof["outputs"]
    mandatory = {"clip.mp4", "scene.blend", "motion.json"}
    if not mandatory <= outputs.keys() or any(Path(name).name != name for name in outputs):
        raise ValueError("unsafe or incomplete cached output list")
    for name, digest in outputs.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or sha(path) != digest:
            raise ValueError(f"cached output changed: {name}")
    result = validate_clip(root, ffmpeg, ffprobe)
    if (
        result["motion"] != proof["specification"]["motion"]
        or result["native_frames"] != proof["specification"]["frames"]
    ):
        raise ValueError("cached scene semantics mismatch")
    expected_names = {f"frame_{i:04}.png" for i in range(1, result["native_frames"] + 1)}
    if not expected_names <= outputs.keys():
        raise ValueError("source frames not bound to cache proof")
    return result


def runtime(blender, ffmpeg, ffprobe):
    import numpy as np
    import PIL

    builder = Path(__file__).with_name("dual_mode_blender.py")
    return {
        "blender_binary_sha256": sha(blender),
        "linked_dependencies": {
            str(tool): linked_dependencies(tool) for tool in (blender, ffmpeg, ffprobe)
        },
        "pillow": PIL.__version__,
        "numpy": np.__version__,
        "blender_version": subprocess.check_output(
            [str(blender), "--version"], text=True, timeout=30
        ).splitlines()[0],
        "ffmpeg_sha256": sha(ffmpeg),
        "ffprobe_sha256": sha(ffprobe),
        "builder_sha256": sha(builder),
        "validator_sha256": sha(Path(__file__)),
        "registry_sha256": sha(Path(__file__).with_name("asset_library.py")),
        "python": sys.version,
        "platform": platform.platform(),
        "profile": PROFILE,
    }


def owned_asset(mode, library, cache, blender, identity):
    from PIL import Image

    builder = Path(__file__).with_name("dual_mode_blender.py")
    source_key = fingerprint({"runtime": identity, "asset": "owned-wheel-v1"})
    source = cache / "asset-sources" / source_key
    source.parent.mkdir(exist_ok=True)
    built = False
    if not source.exists():
        if mode != "premium":
            for candidate in search(library, "wheel", "side"):
                bundle = Path(candidate["blend_path"]).parent
                metadata, _outputs = inspect_bundle(bundle)
                if candidate["license_status"] != "declared_owned":
                    continue
                provenance = json.loads((bundle / "provenance.json").read_text())
                if (
                    metadata["source_sha256"] == identity["builder_sha256"]
                    and provenance.get("blender_version") == "5.0.1"
                ):
                    return candidate, False
            raise ValueError("no matching owned asset; run Premium first")
        with staging(source.parent, ".asset-") as temporary:
            staged = Path(temporary) / "bundle"
            request = Path(temporary) / "request.json"
            request.write_text(json.dumps({"action": "asset", "output": str(staged)}))
            command(
                [
                    str(blender),
                    "-b",
                    "--factory-startup",
                    "--disable-autoexec",
                    "-P",
                    str(builder),
                    "--",
                    str(request),
                ],
                Path(temporary) / "builder.log",
                900,
            )
            inspect_bundle(staged)
            with Image.open(staged / "frame.png") as image:
                image.load()
                box = image.getchannel("A").getbbox()
                if (
                    image.size != (1080, 1920)
                    or not box
                    or not (0 < box[0] < box[2] < 1080 and 0 < box[1] < box[3] < 1920)
                ):
                    raise ValueError("owned asset thumbnail clipped or empty")
            staged.rename(source)
        built = True
    inspect_bundle(source)
    record = register(source, library)
    if record["source_sha256"] != identity["builder_sha256"]:
        raise ValueError("builder source changed while producing asset")
    found = [r for r in search(library, "wheel", "side") if r["id"] == record["id"]]
    if len(found) != 1 or found[0]["license_status"] != "declared_owned":
        raise ValueError("registered owned asset unavailable")
    return found[0], built


def run(mode, motion, library, cache, blender, frames=30, reuse_visuals=True):
    if mode not in ("premium", "fast") or motion not in MOTIONS:
        raise ValueError("unsupported mode or motion")
    if type(frames) is not int or not 2 <= frames <= 300:
        raise ValueError("frames must be 2..300 at 30fps")
    blender = blender.resolve()
    ffmpeg = Path(shutil.which("ffmpeg") or "").resolve()
    ffprobe = Path(shutil.which("ffprobe") or "").resolve()
    if not blender.is_file() or not ffmpeg.is_file() or not ffprobe.is_file():
        raise ValueError("renderer and ffmpeg tools required")
    cache.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with (cache / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        identity = runtime(blender, ffmpeg, ffprobe)
        asset_started = time.monotonic()
        asset, built = owned_asset(mode, library, cache, blender, identity)
        asset_seconds = time.monotonic() - asset_started
        specification = {
            "runtime": identity,
            "asset_id": asset["id"],
            "motion": motion,
            "frames": frames,
            "profile": PROFILE,
        }
        key = fingerprint(specification)
        scenes = cache / "scenes"
        scenes.mkdir(exist_ok=True)
        destination = scenes / key
        if destination.exists() and reuse_visuals:
            qa = validate_cached(destination, key, str(ffmpeg), str(ffprobe))
            hit = True
        else:
            if destination.exists():
                raise ValueError("existing render retained; choose a new cache for a cold run")
            with staging(scenes, ".scene-") as temporary:
                staged = Path(temporary) / "render"
                staged.mkdir()
                request = Path(temporary) / "request.json"
                request.write_text(
                    json.dumps(
                        {
                            "action": "scene",
                            "output": str(staged),
                            "blend_path": asset["blend_path"],
                            "motion": motion,
                            "frames": frames,
                        }
                    )
                )
                command(
                    [
                        str(blender),
                        "-b",
                        "--factory-startup",
                        "--disable-autoexec",
                        "-P",
                        str(Path(__file__).with_name("dual_mode_blender.py")),
                        "--",
                        str(request),
                    ],
                    staged / "render.log",
                    max(1800, frames * 240),
                )
                command(
                    [
                        str(ffmpeg),
                        "-y",
                        "-v",
                        "error",
                        "-framerate",
                        "30",
                        "-i",
                        str(staged / "frame_%04d.png"),
                        "-c:v",
                        "libx264",
                        "-preset",
                        "medium",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        str(staged / "clip.mp4"),
                    ],
                    staged / "encode.log",
                    180,
                )
                qa = validate_clip(staged, str(ffmpeg), str(ffprobe))
                names = ["clip.mp4", "scene.blend", "motion.json"] + [
                    p.name for p in sorted(staged.glob("frame_*.png"))
                ]
                if runtime(blender, ffmpeg, ffprobe) != identity:
                    raise ValueError("runtime dependencies changed during rendering")
                proof = {
                    "key": key,
                    "specification": specification,
                    "outputs": {name: sha(staged / name) for name in names},
                    "qa": qa,
                    "asset": asset,
                    "physics_validated": False,
                    "production_approved": False,
                }
                (staged / "proof.json").write_text(json.dumps(proof, indent=2))
                staged.rename(destination)
            hit = False
        if runtime(blender, ffmpeg, ffprobe) != identity:
            raise ValueError("runtime dependencies changed during validation")
        result = {
            "mode": mode,
            "motion": motion,
            "key": key,
            "asset_id": asset["id"],
            "asset_built": built,
            "visual_cache_hit": hit,
            "asset_seconds": asset_seconds,
            "wall_seconds": time.monotonic() - started,
            "qa": qa,
            "clip_path": str(destination / "clip.mp4"),
            "clip_sha256": sha(destination / "clip.mp4"),
            "scene_path": str(destination / "scene.blend"),
            "physics_validated": False,
            "production_approved": False,
        }
        return result


def list_scenes(cache, motion=None):
    result = []
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    for root in sorted((cache / "scenes").glob("*")):
        if not root.is_dir() or root.name.startswith("."):
            continue
        try:
            proof = json.loads((root / "proof.json").read_text())
            if motion and proof["specification"]["motion"] != motion:
                continue
            validate_cached(root, root.name, ffmpeg, ffprobe)
            result.append(
                {
                    "key": root.name,
                    "motion": proof["specification"]["motion"],
                    "scene_path": str(root / "scene.blend"),
                    "clip_path": str(root / "clip.mp4"),
                    "physics_validated": False,
                    "production_approved": False,
                }
            )
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            continue
    return result


def main():
    def stop(signum, frame):
        raise KeyboardInterrupt("cancelled")

    signal.signal(signal.SIGTERM, stop)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("action", choices=("premium", "fast", "benchmark", "list-scenes"))
    parser.add_argument("--motion", choices=MOTIONS, default="rolling")
    args = parser.parse_args()
    if args.resume and args.action != "benchmark":
        parser.error("--resume applies to checkpointed benchmarks only")
    if args.receipt.exists():
        parser.error("receipt already exists; reconcile the existing run instead of overwriting")
    if args.action == "list-scenes":
        result = list_scenes(args.cache, args.motion)
    elif args.action == "benchmark":
        from .dual_mode_benchmark import benchmark

        result = benchmark(args, sys.modules[__name__])
    else:
        result = run(args.action, args.motion, args.library, args.cache, args.blender, args.frames)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
