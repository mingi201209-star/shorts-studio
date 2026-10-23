"""Deterministic byte identities and bounded offline planning."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

MAX_FILE = 2**31
MAX_OBJECT = 2**27
MAX_MANIFEST = 2**20
SUFFIXES = {".json", ".mkv", ".mp4", ".png", ".blend", ".zip", ".wav", ".ass", ".srt", ".txt"}


class HandoffError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(ok: bool, code: str = "INVALID_INPUT") -> None:
    if not ok:
        raise HandoffError(code)


def count(value: int, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def digest_ok(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def identity(account_id: str, bucket: str, namespace: str) -> None:
    require(isinstance(account_id, str) and re.fullmatch(r"[0-9a-f]{32}", account_id) is not None)
    require(isinstance(bucket, str) and re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket)
            is not None)
    require(isinstance(namespace, str) and len(namespace) <= 80 and
            re.fullmatch(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", namespace) is not None)


@dataclass(frozen=True)
class Limits:
    max_bytes: int
    max_data_ops: int
    max_token_fetches: int
    deadline_utc: datetime
    chunk_bytes: int = 33554432
    max_retries: int = 2

    def __post_init__(self):
        require(count(self.max_bytes, 1, MAX_FILE) and count(self.max_data_ops, 1, 1024)
                and count(self.max_token_fetches, 1, 1024)
                and count(self.chunk_bytes, 1, MAX_OBJECT) and count(self.max_retries, 0, 2))
        require(isinstance(self.deadline_utc, datetime) and self.deadline_utc.tzinfo is not None)

    def validate_for(self, chunk_count: int, *, mode: Literal["upload", "verify"]):
        require(count(chunk_count, 1, 64) and mode in {"upload", "verify"})
        minimum = 4 * chunk_count + 4 if mode == "upload" else chunk_count + 1
        require(minimum <= self.max_data_ops and minimum <= self.max_token_fetches,
                "LIMIT_REACHED")


@dataclass(frozen=True)
class Chunk:
    index: int
    offset: int
    size_bytes: int
    sha256: str
    key: str


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    account_id: str
    bucket: str
    namespace: str
    source_name: str
    source_suffix: str
    size_bytes: int
    sha256: str
    chunk_bytes: int
    chunks: tuple[Chunk, ...]
    provenance: dict[str, str]


@dataclass(frozen=True)
class RestoreRequest:
    account_id: str
    bucket: str
    namespace: str
    manifest_key: str
    expected_manifest_sha256: str
    destination: Path

    def __post_init__(self):
        identity(self.account_id, self.bucket, self.namespace)
        require(digest_ok(self.expected_manifest_sha256))
        require(self.manifest_key ==
                f"shorts-studio/{self.namespace}/v1/manifests/{self.expected_manifest_sha256}.json")


@dataclass(frozen=True)
class Fingerprint:
    device: int
    inode: int
    size_bytes: int
    mtime_ns: int
    ctime_ns: int

    @classmethod
    def of(cls, info):
        return cls(info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@dataclass(frozen=True)
class Staged:
    plan_id: str
    source: Path
    source_fingerprint: Fingerprint
    spool: Path
    manifest: Manifest


@dataclass(frozen=True)
class Receipt:
    status: str
    plan_id: str | None
    manifest_key: str
    sha256: str
    size_bytes: int
    media_status: Literal["MEDIA_QA_PENDING"] = "MEDIA_QA_PENDING"
    authorized_to_cleanup_local: Literal[False] = False
    production_concurrent_writes_allowed: Literal[False] = False
    provider_spend_cap_enforced: Literal[False] = False
    upload_authorized: Literal[False] = False


def chunk_key(namespace: str, digest: str) -> str:
    return f"shorts-studio/{namespace}/v1/chunks/{digest}.bin"


def canonical_manifest(m: Manifest) -> bytes:
    identity(m.account_id, m.bucket, m.namespace)
    require(type(m.schema_version) is int and m.schema_version == 1)
    require(isinstance(m.source_name, str) and 0 < len(m.source_name) <= 255 and
            m.source_name not in {".", ".."} and
            not any(c in m.source_name for c in "/\\\x00") and
            not any(ord(c) < 32 for c in m.source_name))
    require(m.source_suffix in SUFFIXES and Path(m.source_name).suffix.lower() == m.source_suffix)
    require(count(m.size_bytes, 1, MAX_FILE) and count(m.chunk_bytes, 1, MAX_OBJECT)
            and digest_ok(m.sha256) and 1 <= len(m.chunks) <= 64)
    require(type(m.provenance) is dict and len(m.provenance) <= 16 and
            all(type(k) is str and type(v) is str and len(k) <= 80 and len(v) <= 256
                for k, v in m.provenance.items()))
    offset = 0
    for index, c in enumerate(m.chunks):
        require(type(c.index) is int and c.index == index and type(c.offset) is int
                and c.offset == offset and count(c.size_bytes, 1, m.chunk_bytes)
                and digest_ok(c.sha256) and c.key == chunk_key(m.namespace, c.sha256))
        require(c.size_bytes == min(m.chunk_bytes, m.size_bytes - offset))
        offset += c.size_bytes
    require(offset == m.size_bytes)
    raw = json.dumps(asdict(m), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    require(len(raw) <= MAX_MANIFEST)
    return raw


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def parse_manifest(raw: bytes, *, account_id: str, bucket: str, namespace: str) -> Manifest:
    require(type(raw) is bytes and len(raw) <= MAX_MANIFEST)
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
        data["chunks"] = tuple(Chunk(**c) for c in data["chunks"])
        m = Manifest(**data)
        canonical_manifest(m)
        require((m.account_id, m.bucket, m.namespace) == (account_id, bucket, namespace))
        return m
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise HandoffError("INVALID_MANIFEST") from None


def plan_id(m: Manifest) -> str:
    return hashlib.sha256(canonical_manifest(m)).hexdigest()


def manifest_key(m: Manifest) -> str:
    return f"shorts-studio/{m.namespace}/v1/manifests/{plan_id(m)}.json"


def source_handle(source: Path):
    try:
        handle = os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW), "rb")
        require(stat.S_ISREG(os.fstat(handle.fileno()).st_mode), "UNSAFE_SOURCE")
        return handle
    except OSError:
        raise HandoffError("UNSAFE_SOURCE") from None


def plan_source(source: Path, *, account_id: str, bucket: str, namespace: str,
                limits: Limits, expected_sha256: str | None, provenance: dict[str, str]) -> Manifest:
    source = Path(source)
    identity(account_id, bucket, namespace)
    require(source.suffix.lower() in SUFFIXES)
    with source_handle(source) as handle:
        before = Fingerprint.of(os.fstat(handle.fileno()))
        require(count(before.size_bytes, 1, limits.max_bytes))
        limits.validate_for((before.size_bytes + limits.chunk_bytes - 1)//limits.chunk_bytes,
                            mode="upload")
        digest = hashlib.sha256()
        chunks = []
        offset = 0
        while block := handle.read(limits.chunk_bytes):
            digest.update(block)
            sha = hashlib.sha256(block).hexdigest()
            chunks.append(Chunk(len(chunks), offset, len(block), sha, chunk_key(namespace, sha)))
            offset += len(block)
        require(Fingerprint.of(os.fstat(handle.fileno())) == before and
                Fingerprint.of(source.stat(follow_symlinks=False)) == before, "SOURCE_CHANGED")
    require(expected_sha256 is None or digest.hexdigest() == expected_sha256, "SOURCE_CHANGED")
    result = Manifest(1, account_id, bucket, namespace, source.name, source.suffix.lower(),
                      before.size_bytes, digest.hexdigest(), limits.chunk_bytes, tuple(chunks),
                      dict(provenance))
    canonical_manifest(result)
    return result
