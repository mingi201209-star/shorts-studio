"""Host-serialized, crash-resumable handoff; only whole-byte proof yields success."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import time

from .contracts import (
    HandoffError, MAX_MANIFEST, Receipt, RestoreRequest, canonical_manifest, manifest_key,
    parse_manifest, plan_id, require,
)
from .staging import digest_file, private_dir, restore_file, validate_original, validate_staged
from .state import SIDE, bucket_lock
from .wrangler import RemoteMissing


class Coordinator:
    def __init__(self, store, backend_factory, *, lock_root: Path,
                 utc_clock=lambda: datetime.now(timezone.utc), monotonic_clock=time.monotonic):
        self.store, self.backend_factory, self.lock_root = store, backend_factory, lock_root
        self.utc_clock, self.monotonic_clock = utc_clock, monotonic_clock

    def _failure(self, job, error):
        if self.store.status(job)["state"] == "SOURCE_CHANGED":
            return
        state = error.code if error.code in SIDE else "INTEGRITY_FAILED"
        self.store.transition(job, state, code=error.code)

    def _retry(self, callback, limits):
        for n in range(limits.max_retries+1):
            try:
                return callback()
            except HandoffError as error:
                if error.code != "FAILED_RETRYABLE" or n == limits.max_retries:
                    raise
                delay = 2**n
                require((limits.deadline_utc-self.utc_clock()).total_seconds() > delay,
                        "LIMIT_REACHED")
                time.sleep(delay)

    def _get(self, backend, key, destination, size, *, limits, scope):
        def attempt():
            backend.scope = scope
            if destination.exists() and not destination.is_symlink():
                destination.unlink()  # disposable, coordinator-owned readback only
            backend.get(key, destination, expected_size=size)
        return self._retry(attempt, limits)

    def _ensure(self, backend, key, source, sha, size, *, root, limits, scope):
        with tempfile.TemporaryDirectory(prefix="readback-", dir=root) as tmp:
            dest = Path(tmp) / "checked"
            def readback(phase):
                self._get(backend, key, dest, size, limits=limits, scope=scope+phase)
                require(digest_file(dest, size=size) == sha, "INTEGRITY_FAILED")
            try:
                readback("-preflight")
                return
            except RemoteMissing:
                pass
            for n in range(limits.max_retries+1):
                backend.scope = scope+"-write"
                try:
                    backend.put(key, source, expected_sha256=sha, expected_size=size)
                except HandoffError as error:
                    if error.code != "PUT_UNCERTAIN":
                        raise
                    # Unknown write outcome: no second PUT without a fresh GET.
                try:
                    readback("-readback")
                    return
                except RemoteMissing:
                    if n == limits.max_retries:
                        raise HandoffError("FAILED_RETRYABLE") from None
                    delay = 2**n
                    require((limits.deadline_utc-self.utc_clock()).total_seconds() > delay,
                            "LIMIT_REACHED")
                    time.sleep(delay)

    def _manifest(self, backend, key, expected_sha, *, root, limits):
        with tempfile.TemporaryDirectory(prefix="manifest-read-", dir=root) as tmp:
            dest = Path(tmp) / "manifest.json"
            self._get(backend, key, dest, MAX_MANIFEST, limits=limits, scope="restore-manifest")
            require(digest_file(dest) == expected_sha, "INTEGRITY_FAILED")
            return dest.read_bytes()

    def _restore(self, backend, m, destination, *, limits):
        def fetch(chunk, path):
            self._get(backend, chunk.key, path, chunk.size_bytes, limits=limits,
                      scope=f"reconstruct-{chunk.index}")
        restore_file(m, destination=destination, fetch=fetch)

    def apply(self, job_id: str):
        return self.resume(job_id)

    def resume(self, job_id: str, *, limits=None, operator_reason=None):
        staged, previous_limits = self.store.load_job(job_id)
        m = staged.manifest
        with bucket_lock(self.lock_root, account_id=m.account_id, bucket=m.bucket):
            try:
                if limits is not None:
                    self.store.extend_limits(job_id, limits=limits, operator_reason=operator_reason)
                elif operator_reason is not None:
                    raise HandoffError("INVALID_EXTENSION")
                limits = self.store.limits_for(job_id)
                require(m.size_bytes <= limits.max_bytes, "LIMIT_REACHED")
                limits.validate_for(len(m.chunks), mode="upload")
                try:
                    validate_original(staged)
                except OSError:
                    raise HandoffError("SOURCE_CHANGED") from None
                validate_staged(staged)
                self.store.transition(job_id, "TRANSFERRING")
                backend = self.backend_factory(job_id)
                for chunk in m.chunks:
                    self._ensure(backend, chunk.key, staged.spool/f"{chunk.index}.bin",
                                 chunk.sha256, chunk.size_bytes, root=staged.spool, limits=limits,
                                 scope=f"chunk-{chunk.index}")
                    self.store.transition(job_id, "TRANSFERRING", chunk_index=chunk.index)
                raw = canonical_manifest(m)
                self._ensure(backend, manifest_key(m), staged.spool/"manifest.json", plan_id(m),
                             len(raw), root=staged.spool, limits=limits, scope="manifest")
                downloaded = self._manifest(backend, manifest_key(m), plan_id(m),
                                            root=staged.spool, limits=limits)
                require(downloaded == raw, "INTEGRITY_FAILED")
                self.store.transition(job_id, "MANIFEST_VERIFIED")
                self.store.transition(job_id, "RECONSTRUCTING")
                directory = Path(tempfile.mkdtemp(prefix="reconstruction-", dir=staged.spool))
                self._restore(backend, m, directory/"payload", limits=limits)
                try:
                    validate_original(staged)
                except OSError:
                    raise HandoffError("SOURCE_CHANGED") from None
                self.store.transition(job_id, "REMOTE_VERIFIED")
                return Receipt("REMOTE_VERIFIED", job_id, manifest_key(m), m.sha256, m.size_bytes)
            except HandoffError as error:
                self._failure(job_id, error)
                raise

    def verify(self, *, account_id, bucket, namespace, manifest_key: str,
               expected_manifest_sha256: str, destination: Path, limits):
        request = RestoreRequest(account_id, bucket, namespace, manifest_key,
                                 expected_manifest_sha256, Path(destination).absolute())
        with bucket_lock(self.lock_root, account_id=account_id, bucket=bucket):
            job = self.store.create_verify_job(request, limits)
            try:
                limits = self.store.limits_for(job)
                self.store.transition(job, "TRANSFERRING")
                backend = self.backend_factory(job)
                root = private_dir(self.store.path.parent / "verify-spool")
                raw = self._manifest(backend, manifest_key, expected_manifest_sha256,
                                     root=root, limits=limits)
                m = parse_manifest(raw, account_id=account_id, bucket=bucket, namespace=namespace)
                require(raw == canonical_manifest(m) and m.size_bytes <= limits.max_bytes,
                        "INTEGRITY_FAILED")
                limits.validate_for(len(m.chunks), mode="verify")
                used = self.store.status(job)
                require(limits.max_data_ops-used["data_used"] >= len(m.chunks) and
                        limits.max_token_fetches-used["token_used"] >= len(m.chunks), "LIMIT_REACHED")
                self.store.transition(job, "MANIFEST_VERIFIED")
                self.store.transition(job, "RECONSTRUCTING")
                self._restore(backend, m, request.destination, limits=limits)
                self.store.transition(job, "DOWNLOAD_VERIFIED")
                return Receipt("DOWNLOAD_VERIFIED", None, manifest_key, m.sha256, m.size_bytes)
            except HandoffError as error:
                self._failure(job, error)
                raise
