"""One mock-only scheduling cycle, with no external dispatch or background loop."""

import math
import sqlite3
import time
from collections.abc import Callable
from dataclasses import fields
from decimal import Decimal, InvalidOperation

from .artifacts import LocalArtifactStore
from .contracts import JobSpec
from .queue import _event, _time, _write, block_claim, claim_next, complete_claim
from .recovery import reconcile_expired
from .workers import MockWorker


def run_once(
    conn: sqlite3.Connection, store: LocalArtifactStore, *, worker: MockWorker,
    now: float, disk_free_ratio: float, approved_budget_usd: str = "0",
    monotonic: Callable[[], float] = time.monotonic,
) -> str:
    """Admit at most one free mock; approval never enables other worker kinds.

    Disk pressure and cooldown defer queued work without consuming an attempt.
    The built-in mock performs only finite local hashing. A supplied test worker's
    timeout/error is checkpointed; no subprocess or external timeout worker exists.
    """
    _time(now)
    started = monotonic()

    def fresh_time():
        elapsed = monotonic() - started
        _time(elapsed)
        return now + elapsed

    if (type(disk_free_ratio) not in (int, float)
            or not math.isfinite(disk_free_ratio) or not 0 <= disk_free_ratio <= 1):
        raise ValueError('disk_free_ratio must be finite and between zero and one')
    try:
        if not isinstance(approved_budget_usd, str):
            raise ValueError('approved budget must be decimal text')  # noqa: TRY004
        budget = Decimal(approved_budget_usd)
        if not budget.is_finite() or budget < 0:
            raise ValueError('approved budget must be finite and nonnegative')
    except InvalidOperation as exc:
        raise ValueError('invalid approved budget') from exc
    if not isinstance(worker, MockWorker):
        raise ValueError('only MockWorker is admitted')  # noqa: TRY004

    # Quarantine disallowed queued jobs before the queue can claim them. Budget
    # metadata never authorizes live work, even if an approval value is positive.
    with _write(conn):
        row = conn.execute(
            "SELECT job_id, worker_kind, budget_usd, retry_after FROM jobs "
            "WHERE state='queued' ORDER BY created_at, job_id LIMIT 1"
        ).fetchone()
        if row is None:
            return 'idle'
        job_id, kind, cost, retry_after = row
        if kind != 'mock' or Decimal(cost) != 0:
            reason = 'mock-only pilot: billable or non-mock work disabled'
            conn.execute(
                "UPDATE jobs SET state='blocked', blocked_reason=?, updated_at=? "
                "WHERE job_id=?", (reason, now, job_id),
            )
            _event(conn, job_id, 'blocked', reason, now)
            return 'blocked'
        if disk_free_ratio < .10:
            _event(conn, job_id, 'deferred', 'disk free ratio below 0.10', now)
            return 'blocked'
        if retry_after is not None and retry_after > now:
            _event(conn, job_id, 'deferred', 'model cooldown: retry_after pending', now)
            return 'blocked'

    claim = claim_next(conn, 'mock-runner', now, 60)
    if claim is None:
        return 'blocked'
    try:
        columns = ', '.join(field.name for field in fields(JobSpec))
        row = conn.execute(f'SELECT {columns} FROM jobs WHERE job_id=?',
                           (claim.job_id,)).fetchone()
        job = JobSpec(*row)
        content = worker.run(job)
        receipt = store.put(job, content)
        if not store.verify(job, receipt):
            raise ValueError('local artifact verification failed')
        finished = fresh_time()
        if complete_claim(conn, claim, receipt, finished):
            return 'completed_mock'
        reconcile_expired(conn, store, finished, lambda c: 'unknown')
        block_claim(conn, claim, 'completion rejected; preserve local evidence', finished)
    except Exception as exc:  # noqa: BLE001 - checkpoint every worker/storage failure
        # Persist only the exception type: arbitrary messages may contain secrets.
        finished = fresh_time()
        reconcile_expired(conn, store, finished, lambda c: 'unknown')
        block_claim(conn, claim, f'mock worker/storage error: {type(exc).__name__}', finished)
    return 'blocked'
