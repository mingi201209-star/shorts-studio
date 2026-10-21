"""Local operator commands. No live worker admission or external dispatch."""

import argparse
import json
import math
import shutil
import signal
import sqlite3
import sys
import threading
import time
from pathlib import Path

from .artifacts import LocalArtifactStore
from .contracts import JobSpec
from .database import CoordinatedConnection, maintenance_lock, open_controller_db
from .queue import enqueue
from .recovery import _validate, reconcile_expired, restore_db, snapshot_db
from .runner import run_once
from .workers import MockWorker


def _positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('poll seconds must be finite and positive')
    return number


def _positive_ticks(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('max ticks must be positive')
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('init', 'enqueue-mock', 'step', 'serve', 'status', 'snapshot', 'recover'):
        command = commands.add_parser(name)
        command.add_argument('--db', type=Path, required=True)
        if name == 'enqueue-mock':
            command.add_argument('--id', required=True)
            command.add_argument('--source-sha', required=True)
            command.add_argument('--input-digest', required=True)
        if name in ('step', 'serve'):
            command.add_argument('--storage', type=Path, required=True)
            command.add_argument('--mock-only', action='store_true', required=True)
        if name == 'serve':
            command.add_argument('--poll-seconds', type=_positive_seconds, default=60)
            command.add_argument('--max-ticks', type=_positive_ticks)
        if name == 'status':
            command.add_argument('--json', action='store_true')
        if name == 'snapshot':
            command.add_argument('--dest', type=Path, required=True)
        if name == 'recover':
            command.add_argument('--source', type=Path, required=True)
            command.add_argument('--expected-sha256', required=True)
    return parser


def _open_existing(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    # URI mode prevents accidental initialization, including empty/foreign databases.
    if path.is_symlink() or not path.is_file():
        raise ValueError('existing regular database required')
    mode = 'ro' if readonly else 'rw'
    lock = maintenance_lock(path)
    try:
        conn = sqlite3.connect(f'{path.resolve().as_uri()}?mode={mode}', uri=True, timeout=5,
                               factory=CoordinatedConnection)
        conn._maintenance_lock = lock
    except BaseException:
        lock.close()
        raise
    try:
        _validate(conn)
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=5000')
        if not readonly:
            conn.execute('PRAGMA synchronous=FULL')
        return conn
    except BaseException:
        conn.close()
        raise


def _status(conn: sqlite3.Connection) -> dict:
    conn.execute('BEGIN')
    try:
        counts = dict(conn.execute('SELECT state, count(*) FROM jobs GROUP BY state'))
        row = conn.execute(
            'SELECT event_id, created_at FROM events ORDER BY event_id DESC LIMIT 1'
        ).fetchone()
        # Never echo free-form job identifiers, event kinds/details or payloads.
        return {
            **{state: counts.get(state, 0) for state in ('queued', 'running', 'blocked', 'completed_mock')},
            'expired_leases': conn.execute(
                'SELECT count(*) FROM leases WHERE lease_until<=?', (time.time(),)
            ).fetchone()[0],
            'receipts': conn.execute('SELECT count(*) FROM receipts').fetchone()[0],
            'last_event': {'event_id': row[0], 'created_at': row[1]} if row else None,
            'schema_version': conn.execute('PRAGMA user_version').fetchone()[0],
        }
    finally:
        conn.rollback()


def _tick(conn: sqlite3.Connection, store: LocalArtifactStore) -> None:
    now = time.time()
    reconcile_expired(conn, store, now, lambda claim: 'unknown')
    probe = store.root
    while not probe.exists():
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    print(run_once(conn, store, worker=MockWorker(), now=now,
                   disk_free_ratio=usage.free / usage.total), flush=True)


def _serve(conn: sqlite3.Connection, store: LocalArtifactStore, args) -> None:
    stopped = threading.Event()
    previous = {}
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda *_: stopped.set())
        ticks = 0
        while not stopped.is_set():
            _tick(conn, store)
            ticks += 1
            if args.max_ticks is not None and ticks >= args.max_ticks:
                break
            stopped.wait(args.poll_seconds)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    conn = None
    try:
        if args.command == 'recover':
            restore_db(args.source, args.db, args.expected_sha256)
            print('recovered')
            return 0
        if args.command == 'init':
            if args.db.is_symlink():
                raise ValueError('symlink database refused')
            conn = open_controller_db(args.db)
            print('initialized')
            return 0
        conn = _open_existing(args.db, readonly=args.command in ('status', 'snapshot'))
        if args.command == 'enqueue-mock':
            job = JobSpec(args.id, 'pilot-mock', '1', args.source_sha, args.input_digest,
                          'mock-proof', 'mock', '{}')
            print('enqueued' if enqueue(conn, job) else 'already_exists')
        elif args.command == 'status':
            report = _status(conn)
            print(json.dumps(report, sort_keys=True) if args.json else
                  '\n'.join(f'{key}: {value}' for key, value in report.items()))
        elif args.command == 'snapshot':
            # An online source must never also be the snapshot destination.
            if args.dest.resolve() == args.db.resolve():
                raise ValueError('snapshot must use a separate destination')
            print(snapshot_db(conn, args.dest))
        else:
            store = LocalArtifactStore(args.storage)
            if args.command == 'step':
                _tick(conn, store)
            else:
                _serve(conn, store, args)
        return 0
    except (OSError, ValueError, sqlite3.Error):
        # Exception messages can contain caller paths, payloads or credentials.
        print('controller: operation refused; check paths, schema, checksum and offline state',
              file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == '__main__':
    raise SystemExit(main())
