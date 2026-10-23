"""Pinned private CLI boundary. Ambiguous remote errors never imply absence."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from .contracts import MAX_OBJECT, HandoffError, count, identity, require
from .oauth import data_environment
from .process import bounded_run
from .staging import digest_file, private_dir


class RemoteMissing(HandoffError):
    def __init__(self):
        super().__init__("REMOTE_MISSING")


class WranglerBackend:
    def __init__(self, wrangler: Path, *, acquire, before_call, account_id: str, bucket: str,
                 home: Path, runner=bounded_run, missing_key_verified: bool = False,
                 clock=lambda: datetime.now(UTC)):
        identity(account_id, bucket, "lock")
        self.wrangler, self.acquire, self.before_call = Path(wrangler), acquire, before_call
        self.account_id, self.bucket, self.home = account_id, bucket, Path(home)
        self.runner, self.missing_key_verified, self.clock = runner, missing_key_verified, clock
        self.scope = ""

    def _key(self, key: str):
        require(isinstance(key, str) and len(key) <= 200 and re.fullmatch(
            r"shorts-studio/[a-z0-9]+(?:[-/][a-z0-9]+)*/v1/"
            r"(?:chunks/[0-9a-f]{64}\.bin|manifests/[0-9a-f]{64}\.json)", key) is not None)

    def _call(self, operation: str, key: str, path: Path, size: int):
        self.before_call(self.scope + ":" + operation + ":" + key)
        grant = self.acquire()
        require((grant.expiry-self.clock()).total_seconds() >= 120, "WAIT_AUTH_WINDOW")
        env = data_environment(grant, home=self.home)
        env["CLOUDFLARE_ACCOUNT_ID"] = self.account_id
        args = [str(self.wrangler), "r2", "object", operation, f"{self.bucket}/{key}",
                "--remote", "--file", str(path)]
        if operation == "put":
            args.extend(["--content-type", "application/octet-stream", "--force"])
        try:
            result = self.runner(args, env=env, timeout=90, capture_output=True,
                                 text=True, max_file_bytes=size+1)
        except (HandoffError, OSError):
            raise HandoffError("PUT_UNCERTAIN" if operation == "put" else
                               "FAILED_RETRYABLE") from None
        require(len(result.stdout) <= 2**20 and len(result.stderr) <= 2**20,
                "PUT_UNCERTAIN" if operation == "put" else "REMOTE_UNKNOWN")
        if result.returncode == 0:
            return
        if operation == "put":
            raise HandoffError("PUT_UNCERTAIN")
        # This exact fixture is opt-in only after its pinned-release/host audit.
        # There is intentionally no substring fallback and no missing-bucket case.
        if (self.missing_key_verified and result.returncode == 1 and not result.stdout.strip()
                and result.stderr.strip() == "The specified key does not exist."):
            raise RemoteMissing()
        if result.stderr.strip() in {"HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504"}:
            raise HandoffError("FAILED_RETRYABLE")
        if result.stderr.strip() in {"Unauthorized", "Authentication error"}:
            raise HandoffError("AUTH_REQUIRED")
        raise HandoffError("REMOTE_UNKNOWN")

    def get(self, key: str, destination: Path, *, expected_size: int) -> None:
        self._key(key)
        require(count(expected_size, 1, MAX_OBJECT))
        destination = Path(destination)
        private_dir(destination.parent)
        require(not destination.exists() and not destination.is_symlink(), "DESTINATION_EXISTS")
        self._call("get", key, destination, expected_size)
        require(not destination.is_symlink() and destination.is_file() and
                0 < destination.stat().st_size <= expected_size, "INTEGRITY_FAILED")

    def put(self, key: str, source: Path, *, expected_sha256: str, expected_size: int) -> None:
        self._key(key)
        require(count(expected_size, 1, MAX_OBJECT))
        source = Path(source)
        private_dir(source.parent)
        require(digest_file(source, size=expected_size) == expected_sha256, "INTEGRITY_FAILED")
        self._call("put", key, source, expected_size)
