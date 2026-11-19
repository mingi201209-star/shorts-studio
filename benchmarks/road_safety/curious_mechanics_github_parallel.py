"""GitHub-only native shard helpers for Curious Mechanics production."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / "benchmarks/road_safety/render_curious_mechanics.py"
NATIVE_QA = ROOT / "shorts_studio/factory/curious_mechanics_native_qa.py"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shard_range(shard: int) -> tuple[int, int]:
    if type(shard) is not int or not 1 <= shard <= 30:
        raise ValueError("shard must be an integer from 1 through 30")
    return (shard - 1) * 30 + 1, shard * 30


def aligned_contact_start(frame: int) -> int:
    if type(frame) is not int or not 1 <= frame <= 900:
        raise ValueError("contact frame must be in 1..900")
    return ((frame - 1 + 29) // 30) * 30 + 1


def contact_range(variant: str) -> tuple[int, int]:
    if variant not in ("A", "B", "C"):
        raise ValueError("variant must be A, B or C")
    from shorts_studio.factory import curious_mechanics_timeline as timeline
    manifest = ROOT / f"examples/experiments/curious-mechanics-{variant}.json"
    episode = timeline.load_episode(manifest)
    candidates = sorted(
        (shot for shot in episode["shots"]
         if timeline.detail_stage(shot["id"]) == "rolling_contact" and shot["start"] > 150),
        key=lambda shot: shot["start"],
    )
    if not candidates:
        raise ValueError(f"no late rolling-contact shot for {variant}")
    # B has two late contact beats; choose the first one deterministically so the
    # pilot is anchored to the earliest post-context contact rather than failing.
    shot = candidates[0]
    start = aligned_contact_start(shot["start"])
    end = start + 29
    if end > shot["end"] or end > 900:
        raise ValueError(f"aligned contact shard {start}-{end} is outside shot {shot['id']}")
    return start, end


def find_shard(root: Path, variant: str, first: int, last: int) -> Path:
    expected_id = f"curious-mechanics-{variant}"
    for proof_path in root.rglob("episode-proof.json"):
        proof = json.loads(proof_path.read_text())
        if (proof.get("episode_id") == expected_id and
                proof.get("first_frame") == first and proof.get("last_frame") == last):
            return proof_path.parent
    raise FileNotFoundError(f"native shard artifact not found: {variant} {first}-{last}")


def decoded_md5(clip: Path) -> list[str]:
    output = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-pix_fmt", "rgb24",
         "-f", "framemd5", "-"], text=True
    )
    return [line.split(",")[-1].strip() for line in output.splitlines()
            if line and not line.startswith("#")]


def png_md5(folder: Path, proof: dict) -> list[str]:
    from PIL import Image
    hashes = []
    for frame in proof["frame_numbers"]:
        with Image.open(folder / f"frame_{frame:04d}.png") as image:
            image.load()
            if image.size != (1080, 1920) or image.mode != "RGB":
                raise ValueError(f"unexpected native frame format: {frame}")
            hashes.append(hashlib.md5(image.tobytes()).hexdigest())
    return hashes


def validate_shard(folder: Path, variant: str) -> dict:
    from shorts_studio.factory.curious_mechanics_native_qa import verify
    manifest = ROOT / f"examples/experiments/curious-mechanics-{variant}.json"
    qa = verify(folder, manifest, RENDERER)
    proof = json.loads((folder / "episode-proof.json").read_text())
    receipt = json.loads((folder / "native-validation.json").read_text())
    clip = folder / "native-lossless.mkv"
    clip_sha = digest(clip)
    if not receipt.get("decoded_exact") or receipt.get("clip_sha256") != clip_sha:
        raise ValueError("lossless clip receipt/hash mismatch")
    expected = png_md5(folder, proof)
    if decoded_md5(clip) != expected:
        raise ValueError("lossless clip differs from native PNG frames")
    return {"folder": folder, "proof": proof, "qa": qa, "clip": clip,
            "clip_sha256": clip_sha, "rgb_md5": expected,
            "validator_sha256": digest(NATIVE_QA)}


def encode_concat(clips: list[Path], out: Path, codec: str) -> None:
    concat = out.with_suffix(".concat.txt")
    concat.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips))
    if codec == "lossless":
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
               "-i", str(concat), "-c:v", "copy", str(out)]
    elif codec == "h264":
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
               "-i", str(concat), "-r", "30", "-c:v", "libx264", "-preset", "fast",
               "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    else:
        raise ValueError("unknown codec")
    subprocess.run(cmd, check=True)


def probe_video(path: Path, frames: int) -> dict:
    data = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,nb_frames",
        "-of", "json", str(path)], text=True))
    stream = data["streams"][0]
    if (stream["width"], stream["height"], stream["avg_frame_rate"], int(stream["nb_frames"])) != (1080, 1920, "30/1", frames):
        raise ValueError(f"pilot preview metadata mismatch: {path}")
    return stream


def make_pilot(native_root: Path, contact_root: Path, variant: str, out: Path) -> dict:
    if variant not in ("A", "B", "C"):
        raise ValueError("variant must be A, B or C")
    out.mkdir(parents=True, exist_ok=False)
    opening = [validate_shard(find_shard(native_root, variant, start, end), variant)
               for start, end in (shard_range(1), shard_range(2), shard_range(3))]
    frame_numbers = [n for item in opening for n in item["proof"]["frame_numbers"]]
    pixel_hashes = [h for item in opening for h in item["rgb_md5"]]
    if frame_numbers != list(range(1, 91)) or len(set(pixel_hashes)) != 90:
        raise ValueError("opening pilot does not prove unique contiguous frames 1-90")
    contact_start, contact_end = contact_range(variant)
    contact = validate_shard(find_shard(contact_root, variant, contact_start, contact_end), variant)
    if contact["proof"]["frame_numbers"] != list(range(contact_start, contact_end + 1)):
        raise ValueError("contact pilot frames are not contiguous")
    if len(set(contact["rgb_md5"])) != 30 or len(set(pixel_hashes + contact["rgb_md5"])) != 120:
        raise ValueError("contact pilot has repeated native pixels")
    opening_native = out / f"curious-mechanics-{variant}-opening-native.mkv"
    opening_mp4 = out / f"curious-mechanics-{variant}-opening.mp4"
    contact_native = out / f"curious-mechanics-{variant}-contact-native.mkv"
    contact_mp4 = out / f"curious-mechanics-{variant}-contact.mp4"
    encode_concat([item["clip"] for item in opening], opening_native, "lossless")
    encode_concat([opening_native], opening_mp4, "h264")
    shutil.copyfile(contact["clip"], contact_native)
    encode_concat([contact_native], contact_mp4, "h264")
    opening_probe = probe_video(opening_mp4, 90)
    contact_probe = probe_video(contact_mp4, 30)
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    montage = Image.new("RGB", (480, 640), (16, 16, 16))
    draw = ImageDraw.Draw(montage)
    try:
        font = ImageFont.truetype(str(FONT), 12)
    except OSError:
        font = ImageFont.load_default()
    samples = [(opening[0], 1, "OPEN"), (opening[1], 45, "OPEN"), (opening[2], 90, "OPEN"),
               (contact, contact_start, "CONTACT"),
               (contact, contact_start + 14, "CONTACT"), (contact, contact_end, "CONTACT")]
    for i, (item, frame, label) in enumerate(samples):
        row, col = divmod(i, 3)
        folder = item["folder"]
        image = Image.open(folder / f"frame_{frame:04d}.png").convert("RGB")
        image = ImageOps.contain(image, (156, 274))
        x, y = col * 160 + (160 - image.width) // 2, row * 320 + 30
        montage.paste(image, (x, y))
        draw.text((col * 160 + 5, row * 320 + 5), f"{variant} {label} {frame}", fill="white", font=font)
    montage_path = out / f"curious-mechanics-{variant}-pilot-montage.jpg"
    montage.save(montage_path, quality=80, optimize=True)
    info = {
        "status": "PASS_NATIVE_PILOT", "variant": variant,
        "opening_frames": [1, 90], "opening_seconds": 3.0,
        "contact_frames": [contact_start, contact_end], "contact_seconds": 1.0,
        "opening_shards": [item["clip_sha256"] for item in opening],
        "contact_clip_sha256": contact["clip_sha256"],
        "renderer_sha256": opening[0]["proof"]["renderer_source_sha256"],
        "timeline_sha256": opening[0]["proof"]["timeline_source_sha256"],
        "manifest_sha256": opening[0]["proof"]["manifest_sha256"],
        "experiment_plan_sha256": opening[0]["proof"]["experiment_plan_sha256"],
        "scene_sha256": opening[0]["proof"]["source_sha256"],
        "opening_native_sha256": digest(opening_native), "opening_preview_sha256": digest(opening_mp4),
        "contact_native_sha256": digest(contact_native), "contact_preview_sha256": digest(contact_mp4),
        "montage_sha256": digest(montage_path), "opening_probe": opening_probe, "contact_probe": contact_probe,
        "human_first_view": "UNVERIFIED", "upload_authorized": False,
    }
    (out / "pilot-validation.json").write_text(json.dumps(info, indent=2) + "\n")
    print("PILOT_PREVIEW_PASS", variant, info["opening_preview_sha256"], info["contact_preview_sha256"], flush=True)
    return info



def make_opening_preview(native_root: Path, variant: str, out: Path) -> dict:
    """Assemble only verified new frames 1-90; never renders or adds audio."""
    if variant not in ("A", "B", "C"):
        raise ValueError("variant must be A, B or C")
    out.mkdir(parents=True, exist_ok=False)
    opening = [
        validate_shard(find_shard(native_root, variant, start, end), variant)
        for start, end in (shard_range(1), shard_range(2), shard_range(3))
    ]
    frame_numbers = [n for item in opening for n in item["proof"]["frame_numbers"]]
    pixel_hashes = [h for item in opening for h in item["rgb_md5"]]
    if frame_numbers != list(range(1, 91)) or len(set(pixel_hashes)) != 90:
        raise ValueError("opening preview requires 90 contiguous unique native frames")
    camera_by_shot = {}
    source_fields = (
        "renderer_source_sha256", "timeline_source_sha256",
        "canonical_timeline_sha256", "manifest_sha256",
        "experiment_plan_sha256", "source_sha256",
    )
    source_values = {}
    for item in opening:
        proof = item["proof"]
        for key in source_fields:
            source_values.setdefault(key, set()).add(proof[key])
        for shot, camera in proof["camera_by_shot"].items():
            if shot in camera_by_shot and camera_by_shot[shot] != camera:
                raise ValueError(f"camera changed between shards: {shot}")
            camera_by_shot[shot] = camera
    if any(len(values) != 1 for values in source_values.values()):
        raise ValueError("opening shards were rendered from different inputs")
    native = out / f"curious-mechanics-{variant}-opening-native.mkv"
    preview = out / f"curious-mechanics-{variant}-opening-preview.mp4"
    encode_concat([item["clip"] for item in opening], native, "lossless")
    if decoded_md5(native) != pixel_hashes:
        raise ValueError("opening lossless concatenation differs from native PNG frames")
    encode_concat([native], preview, "h264")
    probe = probe_video(preview, 90)
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    samples = (1, 15, 30, 45, 46, 60, 90)
    folders = {
        frame: item["folder"]
        for item in opening
        for frame in item["proof"]["frame_numbers"]
    }
    montage = Image.new("RGB", (480, 960), (16, 16, 16))
    draw = ImageDraw.Draw(montage)
    try:
        font = ImageFont.truetype(str(FONT), 12)
    except OSError:
        font = ImageFont.load_default()
    for i, frame in enumerate(samples):
        row, col = divmod(i, 3)
        image = Image.open(folders[frame] / f"frame_{frame:04d}.png").convert("RGB")
        image = ImageOps.contain(image, (156, 274))
        x, y = col * 160 + (160 - image.width) // 2, row * 320 + 30
        montage.paste(image, (x, y))
        draw.text((col * 160 + 5, row * 320 + 5), f"{variant} FRAME {frame}",
                  fill="white", font=font)
    montage_path = out / f"curious-mechanics-{variant}-opening-montage.jpg"
    montage.save(montage_path, quality=85, optimize=True)
    info = {
        "status": "PASS_NATIVE_OPENING_PREVIEW",
        "variant": variant,
        "frames": [1, 90],
        "seconds": 3.0,
        "fps": 30,
        "resolution": [1080, 1920],
        "native_lossless_sha256": digest(native),
        "preview_mp4_sha256": digest(preview),
        "montage_sha256": digest(montage_path),
        "native_shards": [
            {"first_frame": item["proof"]["first_frame"],
             "last_frame": item["proof"]["last_frame"],
             "lossless_clip_sha256": item["clip_sha256"]}
            for item in opening
        ],
        "source_sha256": {key: next(iter(values)) for key, values in source_values.items()},
        "camera_by_shot": camera_by_shot,
        "preview_probe": probe,
        "has_audio": False,
        "full_film_qa_pass": False,
        "human_first_view": "UNVERIFIED",
        "upload_authorized": False,
    }
    (out / "opening-preview-validation.json").write_text(
        json.dumps(info, indent=2) + "\n")
    print("OPENING_PREVIEW_PASS", variant, info["preview_mp4_sha256"], flush=True)
    return info


def build_bundle(native_root: Path, audio_root: Path, variant: str) -> dict:
    if variant not in ("A", "B", "C"):
        raise ValueError("variant must be A, B or C")
    native_root = native_root.resolve()
    needed = ["B", "C"] if variant == "C" else [variant]
    from benchmarks.road_safety import episode2_film as film
    from shorts_studio.factory.curious_mechanics_native_qa import verify
    camera_maps = {}
    for v in needed:
        manifest = ROOT / f"examples/experiments/curious-mechanics-{v}.json"
        rows, cameras, all_rgb = [], {}, []
        for proof_path in native_root.rglob("episode-proof.json"):
            proof = json.loads(proof_path.read_text())
            if proof.get("episode_id") != f"curious-mechanics-{v}":
                continue
            folder = proof_path.parent
            qa = verify(folder, manifest, RENDERER)
            receipt = json.loads((folder / "native-validation.json").read_text())
            clip = folder / "native-lossless.mkv"
            clip_sha = digest(clip)
            if not receipt.get("decoded_exact") or receipt.get("clip_sha256") != clip_sha:
                raise ValueError(f"clip receipt mismatch {v} {proof['first_frame']}")
            hashes = png_md5(folder, proof)
            if decoded_md5(clip) != hashes:
                raise ValueError(f"native clip/PNG mismatch {v} {proof['first_frame']}")
            for shot, camera in proof["camera_by_shot"].items():
                if shot in cameras and cameras[shot] != camera:
                    raise ValueError(f"camera changed across shards: {v} {shot}")
                cameras[shot] = camera
            all_rgb.extend(hashes)
            rows.append({
                "clip": str(clip.relative_to(native_root)),
                "clip_sha256": clip_sha,
                "rgb_md5": hashes,
                "proof": proof,
                "controller_qa": qa,
                "validator_sha256": digest(NATIVE_QA),
            })
        rows.sort(key=lambda item: item["proof"]["first_frame"])
        film.validate_shard_layout([item["proof"] for item in rows])
        camera_maps[v] = cameras
        frames = [frame for item in rows for frame in item["proof"]["frame_numbers"]]
        if frames != list(range(1, 901)) or len(all_rgb) != 900 or len(set(all_rgb)) != 900:
            raise ValueError(f"incomplete/duplicated native coverage: {v}")
        if v == variant:
            audio_variant = audio_root / v
            validation_path = audio_variant / "audio-validation.json"
            validation = json.loads(validation_path.read_text())
            narration, captions = audio_variant / "narration.wav", audio_variant / "film.ass"
            if (validation.get("status") != "PASS" or
                    validation.get("voice") != "en-US-AndrewNeural" or
                    validation.get("rate") != "+5%" or
                    digest(narration) != validation.get("narration_sha256")):
                raise ValueError(f"audio validation mismatch: {v}")
            audio_dir = native_root / "audio" / v
            audio_dir.mkdir(parents=True, exist_ok=False)
            records = {}
            for name, source in (("narration.wav", narration), ("film.ass", captions),
                                 ("audio-validation.json", validation_path)):
                dest = audio_dir / name
                shutil.copyfile(source, dest)
                records[name] = {"path": str(dest.relative_to(native_root)), "sha256": digest(dest)}
        else:
            records = {}
        canonical = cameras
        if variant == "C" and v == "C":
            canonical = {**camera_maps["B"], **camera_maps["C"]}
        meta = {
            "variant": v, "shards": rows, "canonical_camera_by_shot": canonical,
            "audio": records, "controller_png_qa": "ACTUALLY_EXECUTED",
        }
        meta_path = native_root / f"{v}.json"
        if meta_path.exists():
            raise FileExistsError(f"preserve existing bundle metadata: {meta_path}")
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    font_dir = native_root / "fonts"
    font_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(FONT, font_dir / "DejaVuSans.ttf")
    font_sha = digest(font_dir / "DejaVuSans.ttf")
    manifest = {"font_sha256": font_sha, "files": {"fonts/DejaVuSans.ttf": font_sha}}
    (native_root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("BUNDLE_READY", variant, len(needed), flush=True)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("range")
    r.add_argument("--shard", type=int, required=True)
    c = sub.add_parser("contact")
    c.add_argument("--variant", choices=list("ABC"), required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--native-root", type=Path, required=True)
    p.add_argument("--contact-root", type=Path, required=True)
    p.add_argument("--variant", choices=list("ABC"), required=True)
    p.add_argument("--out", type=Path, required=True)
    o = sub.add_parser("opening-preview")
    o.add_argument("--native-root", type=Path, required=True)
    o.add_argument("--variant", choices=list("ABC"), required=True)
    o.add_argument("--out", type=Path, required=True)
    b = sub.add_parser("bundle")
    b.add_argument("--native-root", type=Path, required=True)
    b.add_argument("--audio-root", type=Path, required=True)
    b.add_argument("--variant", choices=list("ABC"), required=True)
    args = parser.parse_args()
    if args.command == "range":
        print(*shard_range(args.shard))
    elif args.command == "contact":
        print(*contact_range(args.variant))
    elif args.command == "pilot":
        make_pilot(args.native_root, args.contact_root, args.variant, args.out)
    elif args.command == "opening-preview":
        make_opening_preview(args.native_root, args.variant, args.out)
    else:
        build_bundle(args.native_root, args.audio_root, args.variant)


if __name__ == "__main__":
    main()
