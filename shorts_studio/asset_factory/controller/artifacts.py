"""Durable local content blobs; receipts prove bytes and identity, not native QA."""

import ctypes
import hashlib
import os
import secrets
import stat
from contextlib import contextmanager
from pathlib import Path

from .contracts import ArtifactReceipt, JobSpec

_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextmanager
def _directory(path: Path, *, create: bool):
    """Walk from / using directory descriptors, never following symlinks."""
    fd = os.open("/", _DIRECTORY)
    try:
        for part in path.absolute().parts[1:]:
            if part in (".", ".."):
                raise ValueError("artifact directories must not contain traversal")
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                else:
                    os.fsync(fd)
            child = os.open(part, _DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _matches(directory: int, name: str, digest: str, length: int) -> bool:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != length:
            return False
        return hashlib.file_digest(stream, "sha256").hexdigest() == digest


def _publish(directory: int, temporary: str, name: str) -> None:
    """Linux atomic rename with RENAME_NOREPLACE, including racing writers."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(directory, os.fsencode(temporary), directory, os.fsencode(name), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), name)


class LocalArtifactStore:
    """Filesystem double with immutable content and independent job receipts."""

    def __init__(self, root: Path):
        self.root = Path(root).absolute()
        if ".." in self.root.parts:
            raise ValueError("artifact root must not contain traversal")

    def put(self, job: JobSpec, content: bytes) -> ArtifactReceipt:
        if not isinstance(content, bytes):
            raise TypeError("artifact content must be bytes")
        digest = hashlib.sha256(content).hexdigest()
        relative = f"sha256/{digest[:2]}/{digest}"
        receipt = ArtifactReceipt(job.job_id, job.source_sha, job.input_digest,
                                  digest, relative, len(content))
        with _directory(self.root / "sha256" / digest[:2], create=True) as directory:
            temporary = f".tmp-{secrets.token_hex(16)}"
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    _publish(directory, temporary, digest)
                except FileExistsError:
                    try:
                        valid = _matches(directory, digest, digest, len(content))
                    except OSError as exc:
                        raise ValueError("existing artifact is unsafe") from exc
                    if not valid:
                        raise ValueError("existing artifact failed verification")
                os.fsync(directory)
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
        return receipt

    def verify(self, job: JobSpec, receipt: ArtifactReceipt) -> bool:
        if (job.job_id, job.source_sha, job.input_digest) != (
                receipt.job_id, receipt.source_sha, receipt.input_digest):
            return False
        digest = receipt.artifact_sha256
        if receipt.relative_path != f"sha256/{digest[:2]}/{digest}":
            return False
        try:
            with _directory(self.root / "sha256" / digest[:2], create=False) as directory:
                return _matches(directory, digest, digest, receipt.byte_count)
        except (OSError, ValueError):
            return False
