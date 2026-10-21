"""Atomic mock-only queue transitions with durable identity and fencing.

Completion records a matching receipt, not file/hash verification or production QA.
Callers must verify artifact bytes separately before requesting completion.
"""

import math
import sqlite3
from contextlib import contextmanager
from dataclasses import astuple, fields

from .contracts import ArtifactReceipt, Claim, JobSpec

_JOB_COLUMNS = tuple(field.name for field in fields(JobSpec))


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty")


def _time(value: float) -> None:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("time must be finite and nonnegative")


@contextmanager
def _write(conn: sqlite3.Connection):
    # Never commit or roll back a transaction belonging to the caller.
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _event(conn, job_id, kind, detail, now):
    conn.execute(
        "INSERT INTO events (job_id, kind, detail, created_at) VALUES (?, ?, ?, ?)",
        (job_id, kind, detail, now),
    )


def enqueue(conn: sqlite3.Connection, job: JobSpec) -> bool:
    """Insert once; any difference in the original spec is an identity conflict."""
    with _write(conn):
        existing = conn.execute(
            f"SELECT {', '.join(_JOB_COLUMNS)} FROM jobs WHERE job_id=?", (job.job_id,)
        ).fetchone()
        if existing is not None:
            if tuple(existing) != astuple(job):
                raise ValueError("job identity conflict")
            return False
        conn.execute(
            f"INSERT INTO jobs ({', '.join(_JOB_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in _JOB_COLUMNS)})",
            astuple(job),
        )
        _event(conn, job.job_id, "enqueued", "job registered", 0)
        return True


def claim_next(
    conn: sqlite3.Connection, owner: str, now: float, lease_seconds: float
) -> Claim | None:
    """Claim one queued mock job. Expired leases require separate reconciliation."""
    _text(owner, "owner")
    _time(now)
    _time(lease_seconds)
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")
    lease_until = now + lease_seconds
    _time(lease_until)
    if lease_until <= now:
        raise ValueError("lease must extend beyond now")
    with _write(conn):
        row = conn.execute(
            """SELECT job_id, source_sha, input_digest, attempt_count, fencing_token
               FROM jobs WHERE state='queued' AND worker_kind='mock'
               AND attempt_count < max_attempts AND (retry_after IS NULL OR retry_after <= ?)
               AND NOT EXISTS (SELECT 1 FROM leases WHERE leases.job_id=jobs.job_id)
               ORDER BY created_at, job_id LIMIT 1""",
            (now,),
        ).fetchone()
        if row is None:
            return None
        job_id, source_sha, input_digest, attempt, token = row
        claim = Claim(job_id, source_sha, input_digest, owner, attempt + 1, token + 1,
                      lease_until)
        conn.execute(
            """UPDATE jobs SET state='running', attempt_count=?, fencing_token=?,
               updated_at=?, blocked_reason=NULL WHERE job_id=?""",
            (claim.attempt, claim.fencing_token, now, job_id),
        )
        conn.execute(
            """INSERT INTO attempts (job_id, attempt, owner, fencing_token, started_at)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, claim.attempt, owner, claim.fencing_token, now),
        )
        conn.execute(
            """INSERT INTO leases (job_id, owner, attempt, fencing_token, lease_until)
               VALUES (?, ?, ?, ?, ?)""",
            (job_id, owner, claim.attempt, claim.fencing_token, lease_until),
        )
        _event(conn, job_id, "claimed", f"attempt={claim.attempt}; token={claim.fencing_token}",
               now)
        return claim


def _matches(conn: sqlite3.Connection, claim: Claim, now: float) -> bool:
    return conn.execute(
        """SELECT 1 FROM jobs j JOIN leases l ON l.job_id=j.job_id
           JOIN attempts a ON a.job_id=l.job_id AND a.attempt=l.attempt
           WHERE j.job_id=? AND j.source_sha=? AND j.input_digest=?
           AND j.state='running' AND j.worker_kind='mock'
           AND j.attempt_count=? AND j.fencing_token=?
           AND l.owner=? AND l.attempt=? AND l.fencing_token=? AND l.lease_until=?
           AND l.lease_until > ? AND a.owner=l.owner AND a.fencing_token=l.fencing_token
           AND a.finished_at IS NULL AND a.outcome IS NULL""",
        (claim.job_id, claim.source_sha, claim.input_digest, claim.attempt,
         claim.fencing_token, claim.owner, claim.attempt, claim.fencing_token,
         claim.lease_until, now),
    ).fetchone() is not None


def _finish(conn, claim, outcome, now, reason=None):
    conn.execute(
        "UPDATE jobs SET state=?, updated_at=?, blocked_reason=? WHERE job_id=?",
        (outcome, now, reason, claim.job_id),
    )
    conn.execute(
        """UPDATE attempts SET finished_at=?, outcome=?
           WHERE job_id=? AND attempt=? AND fencing_token=?""",
        (now, outcome, claim.job_id, claim.attempt, claim.fencing_token),
    )
    conn.execute("DELETE FROM leases WHERE job_id=?", (claim.job_id,))
    _event(conn, claim.job_id, outcome, reason or "matching receipt recorded; no file QA", now)


def complete_claim(
    conn: sqlite3.Connection, claim: Claim, receipt: ArtifactReceipt, now: float
) -> bool:
    """Record a matching mock receipt once; return False on stale/repeated completion."""
    _time(now)
    with _write(conn):
        if ((receipt.job_id, receipt.source_sha, receipt.input_digest)
                != (claim.job_id, claim.source_sha, claim.input_digest)
                or not _matches(conn, claim, now)):
            return False
        # Preserve any earlier receipt, including evidence persisted by recovery.
        if conn.execute("SELECT 1 FROM receipts WHERE job_id=?", (claim.job_id,)).fetchone():
            return False
        conn.execute(
            """INSERT INTO receipts (job_id, source_sha, input_digest, artifact_sha256,
               relative_path, byte_count, fencing_token, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (*astuple(receipt), claim.fencing_token, now),
        )
        _finish(conn, claim, "completed_mock", now)
        return True


def block_claim(
    conn: sqlite3.Connection, claim: Claim, reason: str, now: float
) -> bool:
    """Block an active matching lease without retrying an uncertain worker."""
    _text(reason, "reason")
    _time(now)
    with _write(conn):
        if not _matches(conn, claim, now):
            return False
        _finish(conn, claim, "blocked", now, reason)
        return True
