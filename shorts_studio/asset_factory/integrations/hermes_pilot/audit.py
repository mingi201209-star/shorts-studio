"""Private operator-owned ledger for proposals, approval and correlation only.

The marker capability is not an OS security boundary. P1 must isolate Unix
identities so an actual Hermes process cannot access the ledger or mint it.
"""

import os
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .contracts import ParsedIntent


class OperatorAuthority:
    """Typed capability supplied only by the trusted local operator caller.

    Must never be accepted from JSON or exposed to an untrusted Hermes runtime.
    """


@dataclass(frozen=True)
class LedgerEntry:
    intent_id: str
    origin_task_id: str
    input_digest: str
    source_sha: str
    job_id: str
    state: str
    approved: bool


@contextmanager
def transaction(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def open_ledger(path: Path) -> sqlite3.Connection:
    """Open a private, owner-writable SQLite journal; never follow symlinks."""
    path = Path(path).absolute()
    folder = path.parent
    if folder.resolve() != folder or not folder.is_dir():
        raise ValueError("ledger directory must be a real directory")
    info = folder.stat()
    if info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("ledger directory must be private to operator")
    if path.is_symlink():
        raise ValueError("symlink ledger refused")
    created = False
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(fd)
        created = True
    file_info = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(file_info.st_mode) or file_info.st_uid != os.geteuid()
            or file_info.st_mode & 0o077):
        raise ValueError("ledger DB must be a private regular file")
    try:
        conn = sqlite3.connect(f"{path.as_uri()}?mode=rw", uri=True, timeout=5)
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            raise ValueError("unsupported audit schema")
        if version == 0:
            found = conn.execute(
                "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            ).fetchone()
            if found:
                raise ValueError("unversioned populated audit DB refused")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        with transaction(conn):
            if version == 0:
                # executescript() commits any open transaction first: each
                # CREATE would otherwise persist on its own, leaving a broken
                # version-0 DB after an interrupted first initialization.
                for ddl in (
                    """CREATE TABLE proposals (
                        intent_id TEXT PRIMARY KEY, origin_task_id TEXT NOT NULL,
                        digest TEXT NOT NULL, source_sha TEXT NOT NULL,
                        job_id TEXT NOT NULL, state TEXT NOT NULL)""",
                    """CREATE TABLE approvals (
                        intent_id TEXT PRIMARY KEY REFERENCES proposals(intent_id),
                        digest TEXT NOT NULL, approved_at REAL NOT NULL,
                        consumed INTEGER NOT NULL DEFAULT 0)""",
                    """CREATE TABLE audit_events (
                        id INTEGER PRIMARY KEY, intent_id TEXT NOT NULL,
                        kind TEXT NOT NULL, created_at REAL NOT NULL)""",
                ):
                    conn.execute(ddl)
                conn.execute("PRAGMA user_version=1")
            else:
                expected = {"proposals", "approvals", "audit_events"}
                current = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )}
                if current != expected:
                    raise ValueError("audit schema mismatch")
        return conn
    except BaseException:
        conn.close()
        raise


class Ledger:
    """Auditable approval and correlation, not a second execution queue."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def propose(self, parsed: ParsedIntent) -> str:
        if not isinstance(parsed, ParsedIntent):
            raise TypeError("validated intent required")
        with transaction(self.conn):
            row = self.conn.execute(
                "SELECT origin_task_id,digest,source_sha,job_id FROM proposals WHERE intent_id=?",
                (parsed.intent_id,),
            ).fetchone()
            identity = (parsed.origin_task_id, parsed.input_digest,
                        parsed.source_sha, parsed.job_id)
            if row:
                if row != identity:
                    raise ValueError("intent identity conflict")
                return "already_proposed"
            # Enforce the backlog limit at the proposal entrypoint. Applying
            # it only at Controller submission permits unbounded new intents.
            pending = self.conn.execute(
                "SELECT count(*) FROM proposals WHERE state IN ('proposed', 'approved')"
            ).fetchone()[0]
            if pending >= 20:
                raise ValueError("proposal capacity reached")
            self.conn.execute(
                """INSERT INTO proposals(intent_id,origin_task_id,digest,source_sha,job_id,state)
                   VALUES(?,?,?,?,?,'proposed')""",
                (parsed.intent_id, *identity),
            )
            self.conn.execute(
                "INSERT INTO audit_events(intent_id,kind,created_at) VALUES(?,'proposed',?)",
                (parsed.intent_id, time.time()),
            )
        return "proposed"

    def approve_operator(self, intent_id: str, input_digest: str, *,
                         authority: OperatorAuthority) -> str:
        if type(authority) is not OperatorAuthority:
            raise ValueError("trusted operator capability required")
        with transaction(self.conn):
            row = self.conn.execute(
                "SELECT digest,state FROM proposals WHERE intent_id=?", (intent_id,)
            ).fetchone()
            if row is None or row[0] != input_digest:
                raise ValueError("approval digest or intent mismatch")
            existing = self.conn.execute(
                "SELECT digest FROM approvals WHERE intent_id=?", (intent_id,)
            ).fetchone()
            if existing:
                if existing[0] != input_digest:
                    raise ValueError("approval conflict")
                return "already_approved"
            self.conn.execute(
                "INSERT INTO approvals(intent_id,digest,approved_at) VALUES(?,?,?)",
                (intent_id, input_digest, time.time()),
            )
            self.conn.execute(
                "UPDATE proposals SET state='approved' WHERE intent_id=? AND state='proposed'",
                (intent_id,),
            )
            self.conn.execute(
                "INSERT INTO audit_events(intent_id,kind,created_at) VALUES(?,'approved',?)",
                (intent_id, time.time()),
            )
        return "approved"

    def lookup(self, intent_id: str) -> LedgerEntry:
        row = self.conn.execute(
            """SELECT p.intent_id,p.origin_task_id,p.digest,p.source_sha,p.job_id,p.state,
                CASE WHEN a.digest=p.digest THEN 1 ELSE 0 END
                FROM proposals p LEFT JOIN approvals a ON a.intent_id=p.intent_id
                WHERE p.intent_id=?""",
            (intent_id,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown proposal")
        return LedgerEntry(*row[:6], bool(row[6]))

    def mark_submitted(self, intent_id: str, job_id: str) -> None:
        if not self.conn.in_transaction:
            with transaction(self.conn):
                self.mark_submitted(intent_id, job_id)
            return
        row = self.conn.execute(
            "SELECT job_id,state FROM proposals WHERE intent_id=?", (intent_id,)
        ).fetchone()
        if row is None or row[0] != job_id or row[1] not in ("approved", "submitted"):
            raise ValueError("not approved or wrong job")
        if row[1] == "submitted":
            return  # Idempotent replay must not grow unbounded event history.
        self.conn.execute("UPDATE proposals SET state='submitted' WHERE intent_id=?",
                          (intent_id,))
        self.conn.execute(
            "UPDATE approvals SET consumed=1 WHERE intent_id=? AND digest=(SELECT digest FROM proposals WHERE intent_id=?)",
            (intent_id, intent_id),
        )
        self.conn.execute(
            "INSERT INTO audit_events(intent_id,kind,created_at) VALUES(?,'submitted',?)",
            (intent_id, time.time()),
        )
