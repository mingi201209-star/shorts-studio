import hashlib
import json
from pathlib import Path

import pytest

from shorts_studio.asset_library import import_shelf, register, search


def bundle(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "asset.blend").write_bytes(b"fixture model; not actual Blender geometry")
    (root / "frame.png").write_bytes(b"fixture image; not actual visual QA")
    metadata = {
        "asset": "wheel",
        "view": "side",
        "motion": "static_object_view",
        "source_sha256": "a" * 64,
        "editorial_approved": False,
        "interaction_physics_validated": False,
        "blend_sha256": hashlib.sha256((root / "asset.blend").read_bytes()).hexdigest(),
        "image_sha256": hashlib.sha256((root / "frame.png").read_bytes()).hexdigest(),
    }
    (root / "asset.json").write_text(json.dumps(metadata))
    outputs = {
        name: {
            "bytes": (root / name).stat().st_size,
            "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
        }
        for name in ("asset.blend", "asset.json", "frame.png")
    }
    (root / "manifest.json").write_text(json.dumps({"outputs": outputs}))
    return root


def test_import_is_idempotent_self_contained_and_cannot_authorize_motion(tmp_path):
    source = bundle(tmp_path / "source")
    library = tmp_path / "library"
    first = register(source, library)
    assert register(source, library) == first
    (source / "asset.blend").unlink()
    result = search(library, asset="wheel", view="side")
    assert len(result) == 1
    assert result[0]["production_approved"] is False
    assert result[0]["license_status"] == "unverified"
    assert search(library, motion="native_animation") == []
    assert search(library, asset="sedan") == []


@pytest.mark.parametrize("file", ["asset.blend", "frame.png", "asset.json", "manifest.json"])
def test_corruption_is_not_returned_by_search(tmp_path, file):
    record = register(bundle(tmp_path / "source"), tmp_path / "library")
    root = Path(record["blend_path"]).parent
    (root / file).write_bytes(b"corrupted")
    assert search(tmp_path / "library") == []


def test_symlink_file_and_bundle_rejected(tmp_path):
    source = bundle(tmp_path / "source")
    model = source / "asset.blend"
    other = tmp_path / "outside"
    other.write_bytes(model.read_bytes())
    model.unlink()
    model.symlink_to(other)
    with pytest.raises(ValueError, match="symlink"):
        register(source, tmp_path / "library")
    linked = tmp_path / "linked"
    linked.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError):
        register(linked, tmp_path / "library")


def test_partial_or_failed_shelf_entry_is_quarantined(tmp_path):
    shelf = tmp_path / "shelf"
    bundle(shelf / "cache/entries/good")
    broken = shelf / "cache/entries/broken"
    broken.mkdir()
    result = import_shelf(shelf, tmp_path / "library")
    assert len(result["registered"]) == 1
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["bundle"] == "broken"


@pytest.mark.parametrize(
    "field,value",
    [
        ("motion", "native_animation"),
        ("editorial_approved", True),
        ("interaction_physics_validated", True),
        ("source_sha256", "invalid"),
    ],
)
def test_rehashed_claims_cannot_upgrade_static_shelf(tmp_path, field, value):
    source = bundle(tmp_path / "source")
    path = source / "asset.json"
    metadata = json.loads(path.read_text())
    metadata[field] = value
    path.write_text(json.dumps(metadata))
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["outputs"]["asset.json"] = {
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        register(source, tmp_path / "library")
