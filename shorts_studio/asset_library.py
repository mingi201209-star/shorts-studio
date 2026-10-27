"""Content-addressed static object shelf; registration never grants production approval."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

FILES = ("asset.blend", "asset.json", "frame.png")
KINDS = {"sedan", "wheel", "rail", "post"}
VIEWS = {"side", "three_quarter"}


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inspect_bundle(root: Path) -> tuple[dict, dict]:
    """Check bytes and static metadata, not geometry, animation or physics."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("bundle must be a real directory")
    for name in (*FILES, "manifest.json"):
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing or symlinked bundle file: {name}")
    manifest = json.loads((root / "manifest.json").read_text())
    outputs = manifest["outputs"]
    if set(outputs) != set(FILES):
        raise ValueError("unexpected bundle outputs")
    for name in FILES:
        record = outputs[name]
        path = root / name
        if record["bytes"] != path.stat().st_size or record["sha256"] != sha(path):
            raise ValueError(f"bundle checksum mismatch: {name}")
    metadata = json.loads((root / "asset.json").read_text())
    if metadata["asset"] not in KINDS or metadata["view"] not in VIEWS:
        raise ValueError("unsupported object or view")
    if metadata["motion"] != "static_object_view":
        raise ValueError("only static object bundles supported")
    if not re.fullmatch(r"[0-9a-f]{64}", metadata["source_sha256"]):
        raise ValueError("source checksum required")
    if metadata["blend_sha256"] != outputs["asset.blend"]["sha256"]:
        raise ValueError("model checksum differs from metadata")
    if metadata["image_sha256"] != outputs["frame.png"]["sha256"]:
        raise ValueError("image checksum differs from metadata")
    if (
        metadata.get("editorial_approved") is not False
        or metadata.get("interaction_physics_validated") is not False
    ):
        raise ValueError("shelf importer cannot import production or physics approval")
    return metadata, outputs


def identifier(outputs: dict) -> str:
    raw = json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def register(source: Path, library: Path) -> dict:
    metadata, outputs = inspect_bundle(source)
    key = identifier(outputs)
    library.mkdir(parents=True, exist_ok=True)
    with (library / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        bundles = library / "bundles"
        bundles.mkdir(exist_ok=True)
        destination = bundles / key
        if destination.exists():
            _, existing = inspect_bundle(destination)
            if identifier(existing) != key:
                raise ValueError("existing content-addressed bundle changed")
        else:
            with tempfile.TemporaryDirectory(prefix=".import-", dir=bundles) as temporary:
                staged = Path(temporary) / "bundle"
                staged.mkdir()
                for name in (*FILES, "manifest.json"):
                    shutil.copyfile(source / name, staged / name, follow_symlinks=False)
                _, copied = inspect_bundle(staged)
                if copied != outputs:
                    raise ValueError("source changed during import")
                staged.rename(destination)
    return {
        "id": key,
        "asset": metadata["asset"],
        "view": metadata["view"],
        "motion": "static_object_view",
        "blend_path": str(destination / "asset.blend"),
        "source_sha256": metadata["source_sha256"],
        "license_status": "unverified",
        "production_approved": False,
        "physics_validated": False,
    }


def import_shelf(shelf: Path, library: Path) -> dict:
    """Discover completed bundles and quarantine errors without changing source."""
    imported, rejected = [], []
    entries = shelf / "cache" / "entries"
    if entries.is_symlink() or not entries.is_dir():
        raise ValueError("shelf cache entries missing")
    for bundle in sorted(entries.iterdir()):
        if not bundle.is_dir():
            continue
        try:
            imported.append(register(bundle, library))
        except (OSError, ValueError, KeyError, TypeError) as error:
            rejected.append({"bundle": bundle.name, "reason": str(error)})
    return {"registered": imported, "rejected": rejected}


def search(
    library: Path,
    asset: str | None = None,
    view: str | None = None,
    motion: str = "static_object_view",
) -> list[dict]:
    """Revalidate bytes on each lookup; static bundles never satisfy moving shots."""
    if motion != "static_object_view":
        return []
    found = []
    for bundle in sorted((library / "bundles").glob("*")):
        try:
            metadata, outputs = inspect_bundle(bundle)
            if bundle.name != identifier(outputs):
                continue
            if asset and metadata["asset"] != asset:
                continue
            if view and metadata["view"] != view:
                continue
            found.append(
                {
                    "id": bundle.name,
                    "asset": metadata["asset"],
                    "view": metadata["view"],
                    "blend_path": str(bundle / "asset.blend"),
                    "motion": metadata["motion"],
                    "license_status": "unverified",
                    "production_approved": False,
                    "physics_validated": False,
                }
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import-shelf")
    importer.add_argument("shelf", type=Path)
    finder = commands.add_parser("search")
    finder.add_argument("--asset", choices=sorted(KINDS))
    finder.add_argument("--view", choices=sorted(VIEWS))
    finder.add_argument("--motion", default="static_object_view")
    args = parser.parse_args()
    if args.command == "import-shelf":
        result = import_shelf(args.shelf, args.library)
        print(json.dumps(result, indent=2))
        if result["rejected"]:
            raise SystemExit(2)
    else:
        print(json.dumps(search(args.library, args.asset, args.view, args.motion), indent=2))


if __name__ == "__main__":
    main()
