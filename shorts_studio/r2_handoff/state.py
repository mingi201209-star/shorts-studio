"""Stable host locks and crash-durable, conservative operation accounting."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading

from .contracts import (
    Fingerprint, HandoffError, Limits, RestoreRequest, Staged, canonical_manifest, identity,
    parse_manifest, plan_id, require,
)
from .staging import private_dir

_held = threading.local()
SIDE = {"WAIT_AUTH_WINDOW", "AUTH_REQUIRED", "SOURCE_CHANGED", "INTEGRITY_FAILED",
        "LIMIT_REACHED", "FAILED_RETRYABLE"}
NEXT = {"STAGED": {"TRANSFERRING"}, "TRANSFERRING": {"TRANSFERRING", "MANIFEST_VERIFIED"},
        "MANIFEST_VERIFIED": {"RECONSTRUCTING", "TRANSFERRING"},
        "RECONSTRUCTING": {"REMOTE_VERIFIED", "DOWNLOAD_VERIFIED", "TRANSFERRING"},
        "REMOTE_VERIFIED": {"TRANSFERRING"}, "DOWNLOAD_VERIFIED": {"TRANSFERRING"}}


@contextmanager
def _lock(root: Path, name: str, rank: int):
    root = private_dir(root)
    ranks = getattr(_held, "ranks", [])
    require(not ranks or rank > ranks[-1], "LOCK_ORDER")
    fd = os.open(root / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                not info.st_mode & 0o077, "UNSAFE_PATH")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HandoffError("BUSY") from None
        _held.ranks = ranks + [rank]
        try:
            yield
        finally:
            _held.ranks = ranks
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def bucket_lock(root: Path, *, account_id: str, bucket: str):
    identity(account_id, bucket, "lock")
    return _lock(root, f"bucket-{account_id}-{bucket}.lock", 10)


def profile_lock(root: Path, *, profile: str):
    require(isinstance(profile, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", profile) is not None)
    return _lock(root, f"profile-{profile}.lock", 20)


def _limits(raw: str) -> Limits:
    data = json.loads(raw)
    data["deadline_utc"] = datetime.fromisoformat(data["deadline_utc"])
    return Limits(**data)


def _json(value) -> str:
    return json.dumps(value, default=str, sort_keys=True, separators=(",", ":"))


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path).absolute()
        private_dir(self.path.parent)
        self._ends = {}
        new = False
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            os.close(fd)
            new = True
        except FileExistsError:
            require(not self.path.is_symlink(), "STATE_INVALID")
        info = self.path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                not info.st_mode & 0o077, "STATE_INVALID")
        self.db = sqlite3.connect(self.path, timeout=5)
        self.db.row_factory = sqlite3.Row
        try:
            if not new:
                require(self.db.execute("PRAGMA user_version").fetchone()[0] == 1,
                        "STATE_INVALID")
                require(self.db.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                        "STATE_INVALID")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            if new:
                with self.db:
                    self.db.executescript('''
                    CREATE TABLE jobs(id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                        payload TEXT NOT NULL, limits_json TEXT NOT NULL, state TEXT NOT NULL,
                        data_used INTEGER NOT NULL DEFAULT 0, token_used INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE attempts(job TEXT,kind TEXT,op TEXT,n INTEGER NOT NULL,
                        PRIMARY KEY(job,kind,op));
                    CREATE TABLE events(job TEXT,state TEXT,chunk INTEGER,code TEXT);
                    CREATE TABLE extensions(job TEXT,old_limits TEXT,new_limits TEXT,reason TEXT);
                    PRAGMA user_version=1;
                    ''')
            require(self.db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                    "AND name='jobs'").fetchone() is not None, "STATE_INVALID")
        except (sqlite3.DatabaseError, HandoffError):
            self.db.close()
            raise HandoffError("STATE_INVALID") from None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.db.close()

    def _row(self, job: str):
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
        require(row is not None, "UNKNOWN_JOB")
        return row

    def _create(self, job: str, kind: str, payload: dict, limits: Limits) -> str:
        raw = _json(payload)
        with self.db:
            old = self.db.execute("SELECT kind,payload FROM jobs WHERE id=?", (job,)).fetchone()
            if old:
                require(old["kind"] == kind and old["payload"] == raw, "PLAN_CHANGED")
            else:
                self.db.execute("INSERT INTO jobs(id,kind,payload,limits_json,state) "
                                "VALUES(?,?,?,?, 'STAGED')",
                                (job, kind, raw, _json(asdict(limits))))
        return job

    def create_job(self, staged: Staged, limits: Limits) -> str:
        require(staged.plan_id == plan_id(staged.manifest), "PLAN_CHANGED")
        limits.validate_for(len(staged.manifest.chunks), mode="upload")
        return self._create(staged.plan_id, "upload", {
            "source": str(staged.source), "spool": str(staged.spool),
            "fingerprint": asdict(staged.source_fingerprint),
            "manifest": canonical_manifest(staged.manifest).decode()}, limits)

    def create_verify_job(self, request: RestoreRequest, limits: Limits) -> str:
        payload = asdict(request)
        payload["destination"] = str(Path(request.destination).absolute())
        job = "verify-" + hashlib.sha256(_json(payload).encode()).hexdigest()
        return self._create(job, "verify", payload, limits)

    def load_job(self, job_id: str) -> tuple[Staged, Limits]:
        row = self._row(job_id)
        require(row["kind"] == "upload", "READ_ONLY_JOB")
        p = json.loads(row["payload"])
        m = json.loads(p["manifest"])
        manifest = parse_manifest(p["manifest"].encode(), account_id=m["account_id"],
                                  bucket=m["bucket"], namespace=m["namespace"])
        require(plan_id(manifest) == job_id, "STATE_INVALID")
        return Staged(job_id, Path(p["source"]), Fingerprint(**p["fingerprint"]),
                      Path(p["spool"]), manifest), _limits(row["limits_json"])

    def status(self, job_id: str) -> dict[str, object]:
        row = self._row(job_id)
        return {k: row[k] for k in ("id", "kind", "state", "data_used", "token_used")}

    def limits_for(self, job_id: str) -> Limits:
        return _limits(self._row(job_id)["limits_json"])

    def reserve(self, job_id: str, *, kind: str, operation_id: str,
                utc_now: datetime, monotonic_now: float) -> None:
        require(kind in {"data", "token"} and utc_now.tzinfo is not None and
                isinstance(operation_id, str) and 0 < len(operation_id) <= 180)
        column = "data_used" if kind == "data" else "token_used"
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row = self._row(job_id)
            limits = _limits(row["limits_json"])
            remaining = (limits.deadline_utc - utc_now).total_seconds()
            end = min(self._ends.get(job_id, float("inf")), monotonic_now + remaining)
            self._ends[job_id] = end
            require(remaining > 0 and monotonic_now < end, "LIMIT_REACHED")
            ceiling = limits.max_data_ops if kind == "data" else limits.max_token_fetches
            require(row[column] < ceiling, "LIMIT_REACHED")
            attempt = self.db.execute("SELECT n FROM attempts WHERE job=? AND kind=? AND op=?",
                                      (job_id, kind, operation_id)).fetchone()
            n = 0 if attempt is None else attempt[0]
            require(n <= limits.max_retries, "LIMIT_REACHED")
            self.db.execute("INSERT INTO attempts VALUES(?,?,?,?) ON CONFLICT(job,kind,op) "
                            "DO UPDATE SET n=excluded.n", (job_id, kind, operation_id, n+1))
            self.db.execute(f"UPDATE jobs SET {column}={column}+1 WHERE id=?", (job_id,))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def transition(self, job_id: str, state: str, *, chunk_index: int | None = None,
                   code: str | None = None) -> None:
        require(code is None or re.fullmatch(r"[A-Z_]{1,80}", code) is not None)
        with self.db:
            row = self._row(job_id)
            old = row["state"]
            allowed = NEXT.get(old, {"TRANSFERRING"} if old in SIDE else set())
            require(old != "SOURCE_CHANGED" and (state in allowed or state in SIDE),
                    "INVALID_TRANSITION")
            require(not (row["kind"] == "verify" and state == "REMOTE_VERIFIED"), "READ_ONLY_JOB")
            self.db.execute("UPDATE jobs SET state=? WHERE id=?", (state, job_id))
            self.db.execute("INSERT INTO events VALUES(?,?,?,?)", (job_id, state, chunk_index, code))

    def extend_limits(self, job_id: str, *, limits: Limits, operator_reason: str) -> None:
        require(type(operator_reason) is str and 0 < len(operator_reason.strip()) <= 256)
        with self.db:
            row = self._row(job_id)
            old = _limits(row["limits_json"])
            require(limits.chunk_bytes == old.chunk_bytes and limits.max_retries == old.max_retries
                    and limits.max_bytes >= old.max_bytes and limits.max_data_ops >= old.max_data_ops
                    and limits.max_token_fetches >= old.max_token_fetches
                    and limits.deadline_utc >= old.deadline_utc, "INVALID_EXTENSION")
            self.db.execute("INSERT INTO extensions VALUES(?,?,?,?)",
                            (job_id, row["limits_json"], _json(asdict(limits)), operator_reason))
            self.db.execute("UPDATE jobs SET limits_json=? WHERE id=?",
                            (_json(asdict(limits)), job_id))
            self._ends.pop(job_id, None)
