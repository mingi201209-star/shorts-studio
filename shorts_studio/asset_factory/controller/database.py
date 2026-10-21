"""SQLite schema version 1; future versions require explicit migrations."""

import sqlite3
from pathlib import Path

_SCHEMA_V1 = (
    "CREATE TABLE schema_metadata (version INTEGER NOT NULL)",
    "INSERT INTO schema_metadata VALUES (1)",
    """CREATE TABLE jobs (
        job_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, asset_version TEXT NOT NULL,
        source_sha TEXT NOT NULL, input_digest TEXT NOT NULL, stage TEXT NOT NULL,
        worker_kind TEXT NOT NULL CHECK (worker_kind IN ('mock', 'codex')),
        payload_json TEXT NOT NULL, max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
        budget_usd TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
        attempt_count INTEGER NOT NULL DEFAULT 0, fencing_token INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL DEFAULT 0, updated_at REAL NOT NULL DEFAULT 0,
        retry_after REAL, blocked_reason TEXT)""",
    """CREATE TABLE attempts (
        job_id TEXT NOT NULL REFERENCES jobs(job_id), attempt INTEGER NOT NULL,
        owner TEXT NOT NULL, fencing_token INTEGER NOT NULL, started_at REAL NOT NULL,
        finished_at REAL, outcome TEXT, PRIMARY KEY (job_id, attempt),
        UNIQUE (job_id, fencing_token))""",
    """CREATE TABLE leases (
        job_id TEXT PRIMARY KEY REFERENCES jobs(job_id), owner TEXT NOT NULL,
        attempt INTEGER NOT NULL, fencing_token INTEGER NOT NULL, lease_until REAL NOT NULL,
        FOREIGN KEY (job_id, attempt) REFERENCES attempts(job_id, attempt))""",
    """CREATE TABLE receipts (
        job_id TEXT PRIMARY KEY REFERENCES jobs(job_id), source_sha TEXT NOT NULL,
        input_digest TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, relative_path TEXT NOT NULL,
        byte_count INTEGER NOT NULL CHECK (byte_count >= 0), fencing_token INTEGER NOT NULL,
        created_at REAL NOT NULL)""",
    """CREATE TABLE events (
        event_id INTEGER PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(job_id),
        kind TEXT NOT NULL, detail TEXT NOT NULL, created_at REAL NOT NULL)""",
)


def open_controller_db(path: Path) -> sqlite3.Connection:
    """Open a durable database, initializing only an empty version-zero database."""
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        # Refuse unknown versions before changing persistent settings or schema.
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise ValueError(f"unsupported schema version: {version}")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            if conn.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone():
                raise ValueError("unversioned database is not empty; explicit migration required")
            for statement in _SCHEMA_V1:
                conn.execute(statement)
            conn.execute("PRAGMA user_version=1")
        elif version != 1:
            raise ValueError(f"unsupported schema version: {version}")
        try:
            metadata = conn.execute("SELECT version FROM schema_metadata").fetchall()
        except sqlite3.DatabaseError as exc:
            raise ValueError("missing schema version metadata") from exc
        if metadata != [(1,)]:
            raise ValueError("inconsistent schema version metadata")
        conn.commit()
        return conn
    except BaseException:
        conn.close()
        raise
