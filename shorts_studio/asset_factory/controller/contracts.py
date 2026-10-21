"""Immutable, validated controller identities and receipts."""

import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _digest(value: str, length: int) -> None:
    if not isinstance(value, str) or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError(f"expected canonical lowercase {length}-character digest")


def _identity(job_id: str, source_sha: str, input_digest: str) -> None:
    _text(job_id, "job_id")
    _digest(source_sha, 40)
    _digest(input_digest, 64)


def _integer(value: int, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"expected integer >= {minimum}")


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    asset_id: str
    asset_version: str
    source_sha: str
    input_digest: str
    stage: str
    worker_kind: str
    payload_json: str
    max_attempts: int = 2
    budget_usd: str = "0"

    def __post_init__(self) -> None:
        _identity(self.job_id, self.source_sha, self.input_digest)
        for name in ("asset_id", "asset_version", "stage"):
            _text(getattr(self, name), name)
        if self.worker_kind not in ("mock", "codex"):
            raise ValueError("unknown worker kind")
        _integer(self.max_attempts, 1)
        if not isinstance(self.payload_json, str):
            raise ValueError("payload_json must be JSON text")  # noqa: TRY004
        json.loads(self.payload_json, parse_constant=_reject_constant)
        try:
            if not isinstance(self.budget_usd, str):
                raise ValueError("budget_usd must be decimal text")  # noqa: TRY004
            budget = Decimal(self.budget_usd)
            if not budget.is_finite() or budget < 0:
                raise ValueError("budget must be finite and nonnegative")
        except InvalidOperation as exc:
            raise ValueError("invalid budget") from exc


@dataclass(frozen=True)
class Claim:
    job_id: str
    source_sha: str
    input_digest: str
    owner: str
    attempt: int
    fencing_token: int
    lease_until: float

    def __post_init__(self) -> None:
        _identity(self.job_id, self.source_sha, self.input_digest)
        _text(self.owner, "owner")
        _integer(self.attempt, 1)
        _integer(self.fencing_token, 1)
        if (type(self.lease_until) not in (int, float)
                or not math.isfinite(self.lease_until) or self.lease_until < 0):
            raise ValueError("lease_until must be finite and nonnegative")


@dataclass(frozen=True)
class ArtifactReceipt:
    job_id: str
    source_sha: str
    input_digest: str
    artifact_sha256: str
    relative_path: str
    byte_count: int

    def __post_init__(self) -> None:
        _identity(self.job_id, self.source_sha, self.input_digest)
        _digest(self.artifact_sha256, 64)
        _integer(self.byte_count, 0)
        _text(self.relative_path, "relative_path")
        path = PurePosixPath(self.relative_path)
        if (path.is_absolute() or ".." in path.parts or path == PurePosixPath(".")
                or "\\" in self.relative_path or "\x00" in self.relative_path
                or re.match(r"^[A-Za-z]:", self.relative_path)):
            raise ValueError("artifact path must be relative without traversal")
