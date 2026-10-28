"""Compose verified native scenes into a clean sequence without frame interpolation."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

from .asset_library import sha
from .dual_mode import PROFILE, command, staging, validate_cached


def select_frames(cache, parts, validate):
    """Resolve explicit cuts. Repeating an identical original frame is rejected."""
    if not isinstance(parts, list) or not parts:
        raise ValueError("nonempty parts list required")
    result, seen = [], set()
    for part in parts:
        key = part["key"]
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("invalid scene key")
        root = cache / "scenes" / key
        report = validate(root, key)
        count = report["native_frames"]
        start, end = part.get("start", 1), part.get("end", count)
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= count:
            raise ValueError("invalid native cut range")
        proof = json.loads((root / "proof.json").read_text())
        for number in range(start, end + 1):
            name = f"frame_{number:04}.png"
            expected = proof["outputs"][name]
            if expected in seen:
                raise ValueError(
                    "duplicate native source frame; provide an explicit nonduplicate cut"
                )
            seen.add(expected)
            result.append(
                {
                    "scene_key": key,
                    "source_frame": number,
                    "source_path": str(root / name),
                    "source_sha256": expected,
                    "motion": proof["specification"]["motion"],
                }
            )
    return result


def validate_sequence_video(root, count, ffmpeg, ffprobe):
    import subprocess

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
                str(root / "sequence.mp4"),
            ],
            text=True,
            timeout=60,
        )
    )
    streams = probe["streams"]
    if len(streams) != 1 or any(
        streams[0].get(key) != value
        for key, value in {
            "width": 1080,
            "height": 1920,
            "r_frame_rate": "30/1",
            "nb_read_frames": str(count),
        }.items()
    ):
        raise ValueError("composed native profile mismatch")
    with tempfile.TemporaryDirectory(prefix=".decode-", dir=root.parent) as temporary:
        temporary = Path(temporary)
        command(
            [
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(root / "sequence.mp4"),
                "-vsync",
                "0",
                str(temporary / "%04d.png"),
            ],
            temporary / "decode.log",
            120,
        )
        frames = sorted(temporary.glob("*.png"))
        if len(frames) != count or len({sha(path) for path in frames}) != count:
            raise ValueError("composition duplicated or lost decoded native frames")


def compose(cache, specification, output):
    if output.exists():
        raise ValueError("output exists; reconcile it instead of overwriting")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("ffmpeg and ffprobe required")
    producer_hash = sha(Path(__file__))

    def validate(root, key):
        return validate_cached(root, key, ffmpeg, ffprobe)

    selected = select_frames(cache, specification["parts"], validate)
    output.parent.mkdir(parents=True, exist_ok=True)
    with staging(output.parent, ".compose-") as temporary:
        root = temporary / "result"
        root.mkdir()
        for index, source in enumerate(selected, 1):
            path = Path(source["source_path"])
            if path.is_symlink() or not path.is_file():
                raise ValueError("source frame became unsafe")
            target = root / f"frame_{index:04}.png"
            shutil.copyfile(path, target, follow_symlinks=False)
            if sha(target) != source["source_sha256"]:
                raise ValueError("source changed during composition")
        command(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-framerate",
                "30",
                "-i",
                str(root / "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(root / "sequence.mp4"),
            ],
            root / "encode.log",
            180,
        )
        validate_sequence_video(root, len(selected), ffmpeg, ffprobe)
        for key in {source["scene_key"] for source in selected}:
            validate(cache / "scenes" / key, key)
        if producer_hash != sha(Path(__file__)):
            raise ValueError("composition producer changed")
        report = {
            "status": "PASS_NATIVE_CLEAN_SEQUENCE",
            "native_frames": len(selected),
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "duration_seconds": len(selected) / 30,
            "profile": PROFILE,
            "producer_sha256": producer_hash,
            "source_mapping": selected,
            "video_sha256": sha(root / "sequence.mp4"),
            "physics_validated": False,
            "production_approved": False,
            "audio_subtitle_qa": "NOT_APPLICABLE_CLEAN_CLIP",
            "note": "Technical motion asset sequence; narration and final Short approval are still required.",
        }
        (root / "sequence-report.json").write_text(json.dumps(report, indent=2) + "\n")
        names = ["sequence.mp4", "sequence-report.json"] + [
            path.name for path in sorted(root.glob("frame_*.png"))
        ]
        (root / "manifest.json").write_text(
            json.dumps({"outputs": {name: sha(root / name) for name in names}}, indent=2) + "\n"
        )
        root.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--sequence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compose(args.cache, json.loads(args.sequence.read_text()), args.output)
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "source_mapping"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
