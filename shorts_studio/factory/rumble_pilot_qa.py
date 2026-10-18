"""Fail-closed checks for authored rumble pilot frames, not a release-quality sign-off."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def verify(directory: Path, expected: int, preview: bool) -> dict:
    if not 2 <= expected <= 90:
        raise ValueError("pilot must contain 2-90 real rendered frames")
    proof_path = directory / "preview-proof.json"
    if not proof_path.is_file():
        raise ValueError("missing renderer proof")
    proof = json.loads(proof_path.read_text(encoding="utf8"))
    required = {
        "frames": expected,
        "preview_only": preview,
        "resolution": [450, 800] if preview else [1080, 1920],
        "cycles_samples": 7 if preview else 32,
        "car_mesh_parts": 72,
        "rotating_wheel_pivots": 4,
        "physically_calibrated": False,
        "upload_ready": False,
    }
    for name, expected_value in required.items():
        if proof.get(name) != expected_value:
            raise ValueError(f"invalid renderer proof field: {name}")
    if proof.get("source_sha256") != (
        "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877"
    ):
        raise ValueError("wrong audited CC0 source identity")
    if proof.get("view") not in ("hero", "contact"):
        raise ValueError("unknown camera proof")
    files = sorted(directory.glob("frame_*.png"))
    required_names = [f"frame_{i:04d}.png" for i in range(1, expected + 1)]
    if [p.name for p in files] != required_names:
        raise ValueError("missing, extra, or renumbered authored frame")
    hashes = []
    last = None
    changes = []
    for frame_path in files:
        hashes.append(hashlib.sha256(frame_path.read_bytes()).hexdigest())
        with Image.open(frame_path) as source:
            source.load()
            if source.size != tuple(required["resolution"]) or source.mode != "RGB":
                raise ValueError(f"wrong decoded pixel profile: {frame_path.name}")
            im = source.copy()
        if sum(ImageStat.Stat(im.resize((30, 50))).mean) < 25:
            raise ValueError(f"black or empty visual: {frame_path.name}")
        if last is not None:
            diff = ImageChops.difference(last, im)
            bbox = diff.getbbox()
            if bbox is None:
                raise ValueError(f"identical consecutive visual: {frame_path.name}")
            changes.append(bbox)
        last = im
    if len(set(hashes)) != expected:
        raise ValueError("reused or duplicated visual frames")
    render_times = proof.get("render_seconds")
    if (not isinstance(render_times, list) or len(render_times) != expected
            or any(type(x) not in (int, float) or x <= 0 for x in render_times)):
        raise ValueError("missing true render time evidence")
    result = {
        "status": "PASS_TECHNICAL_PREVIEW" if preview else "PASS_TECHNICAL_NATIVE_SHOTS",
        "frame_count": expected,
        "unique_frames": len(set(hashes)),
        "pixel_size": required["resolution"],
        "cycles_samples": required["cycles_samples"],
        "view": proof["view"],
        "render_seconds_total": round(sum(render_times), 3),
        "source_sha256": proof["source_sha256"],
        "upload_authorized": False,
        "limitations": (
            "Checks 3D image integrity and source identity only; "
            "does not establish realistic suspension physics, editorial quality, "
            "audio, captions, finished Short, or publish approval."
        ),
    }
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--frames-dir", type=Path, required=True)
    p.add_argument("--frames", type=int, required=True)
    p.add_argument("--native", action="store_true")
    args = p.parse_args()
    result = verify(args.frames_dir, args.frames, preview=not args.native)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
