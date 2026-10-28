"""Run the owned-wheel Premium/Fast proof through clean assembly and review packaging."""

from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import signal
from pathlib import Path

from . import dual_mode
from .asset_library import sha
from .dual_mode_benchmark import benchmark, write_json
from .dual_mode_compose import compose
from .dual_mode_preview import manifest, resolve


def marker_centroid(path):
    import numpy as np
    from PIL import Image

    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=float)
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mask = (red > 90) & (red > green * 1.2) & (red > blue * 1.4)
    ys, xs = np.nonzero(mask)
    if len(xs) < 20:
        raise ValueError("rendered orange motion tracer is not visible")
    return float(xs.mean()), float(ys.mean()), len(xs)


def visible_motion_difference(rolling, locked, frames):
    a = marker_centroid(rolling / f"frame_{frames:04}.png")
    b = marker_centroid(locked / f"frame_{frames:04}.png")
    distance = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
    if distance < 10:
        raise ValueError("rendered rolling and locked tracer positions are indistinguishable")
    return {
        "tracer_displacement_pixels": distance,
        "rolling_orange_pixels": a[2],
        "locked_orange_pixels": b[2],
        "scope": "owned colored-tracer rig only; not a general semantic video judge",
    }


def contact_sheet(rolling, locked, frames, output):
    from PIL import Image, ImageDraw, ImageFont

    sheet = Image.new("RGB", (720, 1340), "#101722")
    draw = ImageDraw.Draw(sheet)
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = (
        ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default()
    )
    for index, (root, label, frame) in enumerate(
        [
            (rolling, "Rolling", 1),
            (rolling, "Rolling", frames),
            (locked, "Locked", 1),
            (locked, "Locked", frames),
        ]
    ):
        x, y = (index % 2) * 360, (index // 2) * 670
        draw.text(
            (x + 10, y + 5), f"{label} - native frame {frame}/{frames}", fill="white", font=font
        )
        with Image.open(root / f"frame_{frame:04}.png") as source:
            sheet.paste(source.convert("RGB").resize((360, 640)), (x, y + 30))
    sheet.save(output, quality=88)


def execute(args):
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.with_suffix(".pipeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("this native pipeline is already active") from error
        comparison = benchmark(args, dual_mode)
        if args.receipt.exists():
            original = json.loads(args.receipt.read_text())
            for name in ("premium_cold", "fast_same_scene", "fast_new_scene"):
                if original[name]["clip_sha256"] != comparison[name]["clip_sha256"]:
                    raise ValueError("existing comparison identity differs")
            comparison = original
        else:
            write_json(args.receipt, comparison)
        cold, new = comparison["premium_cold"], comparison["fast_new_scene"]
        rolling, locked = Path(cold["clip_path"]).parent, Path(new["clip_path"]).parent
        visibility = visible_motion_difference(rolling, locked, args.frames)
        specification = {
            "parts": [
                {"key": cold["key"], "start": 1, "end": args.frames},
                {"key": new["key"], "start": 2, "end": args.frames},
            ]
        }
        sequence_path = args.receipt.with_name(args.receipt.stem + "-sequence.json")
        if sequence_path.exists() and json.loads(sequence_path.read_text()) != specification:
            raise ValueError("existing source cut specification differs")
        if not sequence_path.exists():
            write_json(sequence_path, specification)
        assembled = args.receipt.with_name(args.receipt.stem + "-assembled")
        if assembled.exists():
            bundle = json.loads((assembled / "manifest.json").read_text())
            for name, digest in bundle["outputs"].items():
                if Path(name).name != name or sha(assembled / name) != digest:
                    raise ValueError("existing composition changed")
            assembly = json.loads((assembled / "sequence-report.json").read_text())
            expected = [(cold["key"], frame) for frame in range(1, args.frames + 1)]
            expected += [(new["key"], frame) for frame in range(2, args.frames + 1)]
            actual = [
                (item["scene_key"], item["source_frame"]) for item in assembly["source_mapping"]
            ]
            if actual != expected:
                raise ValueError("existing composition uses different native sources")
        else:
            assembly = compose(args.cache, specification, assembled)
        if args.review.exists():
            document = manifest(args.review)
            if document["comparison_sha256"] != sha(args.receipt):
                raise ValueError("existing review represents another comparison")
            for name in document["files"]:
                resolve(args.review, name, document)
            return {"review": str(args.review), "status": "existing verified review"}
        args.review.parent.mkdir(parents=True, exist_ok=True)
        with dual_mode.staging(args.review.parent, ".review-") as temporary:
            review = temporary / "result"
            review.mkdir()
            items = [
                (
                    "rolling.mp4",
                    Path(cold["clip_path"]),
                    "Premium / Fast identical scene",
                    args.frames,
                ),
                (
                    "locked.mp4",
                    Path(new["clip_path"]),
                    "Fast newly rendered locked scene",
                    args.frames,
                ),
                (
                    "sequence.mp4",
                    assembled / "sequence.mp4",
                    "Native clean assembly",
                    assembly["native_frames"],
                ),
            ]
            files = {}
            for name, source, title, frames in items:
                target = review / name
                shutil.copyfile(source, target)
                if sha(target) != sha(source):
                    raise ValueError("review copy changed")
                files[name] = {
                    "bytes": target.stat().st_size,
                    "sha256": sha(target),
                    "mime": "video/mp4",
                    "title": title,
                    "frames": frames,
                }
            contact_sheet(rolling, locked, args.frames, review / "contact-sheet.jpg")
            write_json(
                review / "report.json",
                {
                    "comparison": comparison,
                    "visible_motion": visibility,
                    "assembly": assembly,
                    "physics_validated": False,
                    "production_approved": False,
                    "note": "Short native technical proof; narration and final Short review remain required.",
                },
            )
            for name, mime, title in [
                ("contact-sheet.jpg", "image/jpeg", "Actual native pose frames"),
                ("report.json", "application/json", "Measured report"),
            ]:
                path = review / name
                files[name] = {
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                    "mime": mime,
                    "title": title,
                }
            write_json(
                review / "manifest.json",
                {
                    "files": files,
                    "comparison_sha256": sha(args.receipt),
                    "timings": {
                        "Premium cold build + render": cold["wall_seconds"],
                        "Fast same-scene reuse + QA": comparison["fast_same_scene"]["wall_seconds"],
                        "Fast new scene + QA": new["wall_seconds"],
                    },
                },
            )
            review.rename(args.review)
        return {
            "review": str(args.review),
            "native_sequence_frames": assembly["native_frames"],
            "visible_motion": visibility,
            "production_approved": False,
        }


def main():
    def stop(signum, frame):
        raise KeyboardInterrupt("cancelled")

    signal.signal(signal.SIGTERM, stop)
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("library", "cache", "blender", "receipt", "review"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(execute(args), indent=2))


if __name__ == "__main__":
    main()
