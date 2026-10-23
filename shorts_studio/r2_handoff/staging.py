"""Private local snapshots; verified no-replace restores. Never deletes sources."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from pathlib import Path

from .contracts import (
    Fingerprint,
    HandoffError,
    Manifest,
    Staged,
    canonical_manifest,
    plan_id,
    require,
    source_handle,
)


def private_dir(path: Path) -> Path:
    path = Path(path).absolute()
    for parent in reversed((path, *path.parents)):
        require(not parent.is_symlink(), "UNSAFE_PATH")
        if not parent.exists():
            parent.mkdir(mode=0o700)
        info = parent.stat()
        require(stat.S_ISDIR(info.st_mode), "UNSAFE_PATH")
        # Sticky shared system parents (e.g. /tmp) do not let another UID replace
        # our private owned child. Other group/world writable parents are unsafe.
        require(not info.st_mode & 0o022 or info.st_mode & stat.S_ISVTX, "UNSAFE_PATH")
    info = path.stat()
    require(info.st_uid == os.getuid() and not info.st_mode & 0o077, "UNSAFE_PATH")
    return path


def fsync_dir(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def space(path: Path, needed: int, floor: int = 268435456):
    require(shutil.disk_usage(path).free >= needed + floor, "DISK_LIMIT")


def digest_file(path: Path, *, size: int | None = None) -> str:
    with source_handle(path) as handle:
        before = Fingerprint.of(os.fstat(handle.fileno()))
        require(size is None or before.size_bytes == size, "INTEGRITY_FAILED")
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(1024*1024), b""):
            digest.update(block)
        require(Fingerprint.of(os.fstat(handle.fileno())) == before and
                Fingerprint.of(path.stat(follow_symlinks=False)) == before, "SOURCE_CHANGED")
        return digest.hexdigest()


def validate_original(staged: Staged) -> None:
    require(not staged.source.is_symlink() and
            Fingerprint.of(staged.source.stat(follow_symlinks=False)) == staged.source_fingerprint,
            "SOURCE_CHANGED")
    require(digest_file(staged.source, size=staged.manifest.size_bytes) == staged.manifest.sha256,
            "SOURCE_CHANGED")


def validate_staged(staged: Staged) -> None:
    private_dir(staged.spool)
    require(plan_id(staged.manifest) == staged.plan_id, "INTEGRITY_FAILED")
    full = hashlib.sha256()
    for c in staged.manifest.chunks:
        path = staged.spool / f"{c.index}.bin"
        require(digest_file(path, size=c.size_bytes) == c.sha256, "INTEGRITY_FAILED")
        with source_handle(path) as handle:
            for block in iter(lambda: handle.read(1024*1024), b""):
                full.update(block)
    require(full.hexdigest() == staged.manifest.sha256, "INTEGRITY_FAILED")


def stage_source(source: Path, *, root: Path, planned: Manifest,
                 min_free_bytes: int = 268435456) -> Staged:
    canonical_manifest(planned)
    root = private_dir(root)
    space(root, planned.size_bytes + min(planned.chunk_bytes, planned.size_bytes), min_free_bytes)
    spool = Path(tempfile.mkdtemp(prefix=plan_id(planned) + "-", dir=root))
    with source_handle(source) as handle:
        before = Fingerprint.of(os.fstat(handle.fileno()))
        require(before.size_bytes == planned.size_bytes, "SOURCE_CHANGED")
        for c in planned.chunks:
            space(root, c.size_bytes, min_free_bytes)
            raw = handle.read(c.size_bytes)
            require(len(raw) == c.size_bytes and hashlib.sha256(raw).hexdigest() == c.sha256,
                    "SOURCE_CHANGED")
            target = spool / f"{c.index}.bin"
            with target.open("xb") as out:
                os.chmod(target, 0o600)
                out.write(raw)
                out.flush()
                os.fsync(out.fileno())
            target.chmod(0o400)
        require(not handle.read(1) and Fingerprint.of(os.fstat(handle.fileno())) == before,
                "SOURCE_CHANGED")
    staged = Staged(plan_id(planned), Path(source).absolute(), before, spool, planned)
    validate_original(staged)
    validate_staged(staged)
    with (spool / "manifest.json").open("xb") as out:
        os.chmod(out.name, 0o400)
        out.write(canonical_manifest(planned))
        out.flush()
        os.fsync(out.fileno())
    fsync_dir(spool)
    fsync_dir(root)
    return staged


def restore_file(manifest: Manifest, *, destination: Path, fetch,
                 min_free_bytes: int = 268435456) -> None:
    canonical_manifest(manifest)
    destination = Path(destination).absolute()
    root = private_dir(destination.parent)
    require(not destination.exists() and not destination.is_symlink(), "DESTINATION_EXISTS")
    space(root, manifest.size_bytes + min(manifest.size_bytes, manifest.chunk_bytes), min_free_bytes)
    with tempfile.TemporaryDirectory(prefix=".r2-restore-", dir=root) as tmp:
        tmp = Path(tmp)
        candidate = tmp / "reconstructed"
        digest = hashlib.sha256()
        with candidate.open("xb") as out:
            candidate.chmod(0o600)
            for c in manifest.chunks:
                space(root, c.size_bytes, min_free_bytes)
                checked = tmp / "readback"
                if checked.exists():
                    checked.unlink()
                fetch(c, checked)
                require(digest_file(checked, size=c.size_bytes) == c.sha256, "INTEGRITY_FAILED")
                with source_handle(checked) as handle:
                    for block in iter(lambda: handle.read(1024*1024), b""):
                        out.write(block)
                        digest.update(block)
            out.flush()
            os.fsync(out.fileno())
        require(candidate.stat().st_size == manifest.size_bytes and
                digest.hexdigest() == manifest.sha256, "INTEGRITY_FAILED")
        try:
            os.link(candidate, destination, follow_symlinks=False)
        except FileExistsError:
            raise HandoffError("DESTINATION_EXISTS") from None
        fsync_dir(root)
