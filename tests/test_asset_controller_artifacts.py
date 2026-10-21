"""Local artifact proofs bind immutable bytes to exact job identities."""

import hashlib
from dataclasses import replace

import pytest

from shorts_studio.asset_factory.controller.artifacts import LocalArtifactStore
from shorts_studio.asset_factory.controller.contracts import JobSpec


def job(**changes):
    return replace(JobSpec("job", "asset", "v1", "a" * 40, "b" * 64,
                           "proof", "mock", "{}"), **changes)


def test_bytes_are_durable_and_sha_verified(tmp_path):
    content = b"local mock proof\x00\xff"
    store = LocalArtifactStore(tmp_path)
    receipt = store.put(job(), content)
    digest = hashlib.sha256(content).hexdigest()
    assert receipt.artifact_sha256 == digest
    assert receipt.relative_path == f"sha256/{digest[:2]}/{digest}"
    assert receipt.byte_count == len(content)
    assert (tmp_path / receipt.relative_path).read_bytes() == content
    assert LocalArtifactStore(tmp_path).verify(job(), receipt)
    assert not store.verify(job(), replace(receipt, byte_count=len(content) + 1))
    assert not store.verify(job(), replace(receipt, artifact_sha256="0" * 64))
    empty = store.put(job(), b"")
    assert store.verify(job(), empty)


def test_corrupt_or_foreign_artifact_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path)
    receipt = store.put(job(), b"good")
    path = tmp_path / receipt.relative_path
    for changes in ({"job_id": "foreign"}, {"source_sha": "c" * 40},
                    {"input_digest": "d" * 64}):
        assert not store.verify(job(), replace(receipt, **changes))
        assert not store.verify(job(**changes), receipt)
    assert path.read_bytes() == b"good"
    assert store.verify(job(), receipt)
    path.write_bytes(b"evil")  # same length, wrong digest
    assert not store.verify(job(), receipt)
    with pytest.raises(ValueError):
        store.put(job(), b"good")
    assert path.read_bytes() == b"evil"  # do not silently replace stored objects


def test_same_content_is_deduplicated_safely(tmp_path):
    store = LocalArtifactStore(tmp_path)
    first = store.put(job(), b"shared")
    path = tmp_path / first.relative_path
    before = path.stat()
    assert store.put(job(), b"shared") == first
    other = job(job_id="other", source_sha="c" * 40, input_digest="d" * 64)
    second = store.put(other, b"shared")
    assert second.relative_path == first.relative_path
    assert second.job_id == other.job_id
    assert store.verify(other, second)
    assert not store.verify(other, first)
    assert not store.verify(job(), second)
    assert path.stat().st_ino == before.st_ino
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    assert list(path.parent.iterdir()) == [path]


def test_path_traversal_and_symlink_rejected(tmp_path):
    root = tmp_path / "store"
    store = LocalArtifactStore(root)
    receipt = store.put(job(), b"good")
    for value in ("../outside", "/absolute", "sha256/../../outside"):
        with pytest.raises(ValueError):
            replace(receipt, relative_path=value)
    assert not store.verify(job(), replace(receipt, relative_path="other"))
    path = root / receipt.relative_path
    outside = tmp_path / "outside"
    outside.write_bytes(b"good")  # a matching hash must not make a symlink valid
    path.unlink()
    path.symlink_to(outside)
    assert not store.verify(job(), receipt)
    with pytest.raises(ValueError):
        store.put(job(), b"good")
    path.unlink()
    path.parent.rmdir()
    path.parent.symlink_to(tmp_path, target_is_directory=True)
    assert not store.verify(job(), receipt)
    with pytest.raises((ValueError, OSError)):
        store.put(job(), b"good")
    assert outside.read_bytes() == b"good"
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(root, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        LocalArtifactStore(linked_root).put(job(), b"good")
