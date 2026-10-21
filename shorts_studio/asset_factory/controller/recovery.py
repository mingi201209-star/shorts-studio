"""Evidence-based lease recovery and offline, checksum-verified SQLite backups."""

import hashlib
import os
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

from .artifacts import LocalArtifactStore
from .contracts import ArtifactReceipt, Claim, JobSpec, _digest
from .database import open_controller_db
from .queue import _event, _finish, _time, _write

_JOB_COLUMNS = ', '.join('j.' + f.name for f in fields(JobSpec))


def reconcile_expired(
    conn: sqlite3.Connection, store: LocalArtifactStore, now: float,
    lookup: Callable[[Claim], str],
) -> list[str]:
    """Reconcile once per expired fencing token; uncertainty never authorizes retry.

    Queue completion/block APIs deliberately reject expired leases and existing receipts.
    Recovery therefore uses the same atomic finish primitive after its own fenced check.
    Lookup runs outside the write lock; every result is rechecked under BEGIN IMMEDIATE.
    """
    _time(now)
    rows = conn.execute(
        f"""SELECT {_JOB_COLUMNS}, l.owner, l.attempt, l.fencing_token, l.lease_until
            FROM jobs j JOIN leases l ON l.job_id=j.job_id
            WHERE j.state='running' AND l.lease_until <= ? ORDER BY j.job_id""", (now,),
    ).fetchall()
    changed = []
    for row in rows:
        job = JobSpec(*row[:len(fields(JobSpec))])
        claim = Claim(job.job_id, job.source_sha, job.input_digest,
                      *row[len(fields(JobSpec)):])
        try:
            status = lookup(claim)
        except Exception:  # noqa: BLE001 - any lookup failure is external uncertainty
            status = 'unknown'
        with _write(conn):
            current = conn.execute(
                """SELECT 1 FROM jobs j JOIN leases l ON l.job_id=j.job_id
                   JOIN attempts a ON a.job_id=l.job_id AND a.attempt=l.attempt
                   WHERE j.job_id=? AND j.state='running' AND j.source_sha=?
                   AND j.input_digest=? AND j.attempt_count=? AND j.fencing_token=?
                   AND l.owner=? AND l.attempt=? AND l.fencing_token=? AND l.lease_until=?
                   AND l.lease_until<=? AND a.owner=l.owner
                   AND a.fencing_token=l.fencing_token AND a.finished_at IS NULL
                   AND a.outcome IS NULL""",
                (claim.job_id, claim.source_sha, claim.input_digest, claim.attempt,
                 claim.fencing_token, claim.owner, claim.attempt, claim.fencing_token,
                 claim.lease_until, now),
            ).fetchone()
            if current is None or status == 'running':
                continue
            outcome, reason = 'blocked', 'external status unknown or unreachable'
            if status == 'completed':
                reason = 'external completion lacks verified current receipt'
                proof = conn.execute(
                    """SELECT job_id, source_sha, input_digest, artifact_sha256,
                       relative_path, byte_count, fencing_token FROM receipts WHERE job_id=?""",
                    (job.job_id,),
                ).fetchone()
                try:
                    verified = (proof is not None and proof[-1] == claim.fencing_token
                                and store.verify(job, ArtifactReceipt(*proof[:-1])))
                except (ValueError, TypeError, OSError):
                    verified = False
                if verified and job.worker_kind == 'mock':
                    outcome, reason = 'completed_mock', 'recovered verified stored artifact'
            elif status == 'not_started':
                reason = 'proven not_started; attempt budget exhausted'
                if claim.attempt < job.max_attempts:
                    outcome, reason = 'queued', 'proven not_started; retry permitted'
            _finish(conn, claim, outcome, now, reason if outcome == 'blocked' else None)
            _event(conn, job.job_id, 'reconciled', reason, now)
            changed.append(job.job_id)
    return changed


def _validate(conn: sqlite3.Connection) -> None:
    """Accept only intact, exact controller schema v1, without initializing a file."""
    reference = open_controller_db(Path(':memory:'))
    try:
        schema = "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
        if (conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]
                or conn.execute('PRAGMA foreign_key_check').fetchall()
                or conn.execute('PRAGMA user_version').fetchone() != (1,)
                or conn.execute(schema).fetchall() != reference.execute(schema).fetchall()
                or conn.execute('SELECT version FROM schema_metadata').fetchall() != [(1,)]):
            raise ValueError('invalid controller snapshot schema or integrity')
    except sqlite3.DatabaseError as exc:
        raise ValueError('corrupt controller snapshot') from exc
    finally:
        reference.close()


def _offline(path: Path) -> None:
    """Offline guard: refuse WAL sidecars and this process's open database handles.

    Restore is an operator offline operation: callers must prevent concurrent opens.
    SQLite locks additionally protect the final replacement against active writers.
    """
    if path.is_symlink():
        raise ValueError('database must not be a symlink')
    if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('database has live or uncheckpointed sidecars')
    if not path.exists():
        return
    target = path.stat()
    for process in (Path('/proc/self'),):
        try:
            descriptors = list((process / 'fd').iterdir())
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise ValueError('cannot establish offline destination') from exc
        for descriptor in descriptors:
            try:
                info = descriptor.stat()
            except FileNotFoundError:
                continue
            except PermissionError as exc:
                raise ValueError('cannot establish offline destination') from exc
            if (info.st_dev, info.st_ino) == (target.st_dev, target.st_ino):
                raise ValueError('database destination is open')


def _temporary(dest: Path) -> Path:
    fd, name = tempfile.mkstemp(prefix=f'.{dest.name}-', dir=dest.parent)
    os.close(fd)
    return Path(name)


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def snapshot_db(conn: sqlite3.Connection, dest: Path) -> str:
    """Use online backup, including committed WAL data, then publish a SHA256 sidecar."""
    dest = Path(dest)
    if conn.in_transaction:
        raise ValueError('snapshot requires no caller transaction')
    _offline(dest)
    temporary = _temporary(dest)
    sidecar = dest.with_suffix(dest.suffix + '.sha256')
    digest_temp = None
    try:
        backup = sqlite3.connect(temporary)
        try:
            conn.backup(backup)
            backup.execute('PRAGMA journal_mode=DELETE')
            _validate(backup)
        finally:
            backup.close()
        with temporary.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            os.fsync(stream.fileno())
        digest_temp = _temporary(sidecar)
        with digest_temp.open('w') as stream:
            stream.write(digest + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        _offline(dest)
        os.replace(temporary, dest)
        os.replace(digest_temp, sidecar)
        _sync_directory(dest.parent)
        return digest
    finally:
        temporary.unlink(missing_ok=True)
        if digest_temp is not None:
            digest_temp.unlink(missing_ok=True)


def restore_db(src: Path, dest: Path, expected_sha256: str) -> None:
    """Validate private snapshot bytes before touching an offline destination.

    Never copy a live WAL database: source must itself be an offline snapshot.
    Publication is atomic and all validation failures preserve the existing database.
    """
    _digest(expected_sha256, 64)
    src, dest = Path(src), Path(dest)
    _offline(src)
    # Verify before even creating a temporary file in the destination directory.
    content = src.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError('snapshot checksum mismatch')
    _offline(dest)
    temporary = _temporary(dest)
    guard = None
    try:
        with temporary.open('wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        check = sqlite3.connect(f'{temporary.resolve().as_uri()}?mode=ro&immutable=1', uri=True)
        try:
            _validate(check)
        finally:
            check.close()
        _offline(dest)
        if dest.exists():
            guard = sqlite3.connect(dest, timeout=0)
            guard.execute('BEGIN EXCLUSIVE')
        os.replace(temporary, dest)
        _sync_directory(dest.parent)
    except sqlite3.DatabaseError as exc:
        raise ValueError('snapshot invalid or destination locked') from exc
    finally:
        if guard is not None:
            guard.close()
        temporary.unlink(missing_ok=True)
