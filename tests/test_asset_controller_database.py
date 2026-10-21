import sqlite3

import pytest

from shorts_studio.asset_factory.controller.database import open_controller_db


def test_schema_v1_and_wal_persist_after_reopen(tmp_path):
    path = tmp_path / "controller.sqlite"
    for _ in range(2):
        with open_controller_db(path) as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            assert {"jobs", "attempts", "leases", "receipts", "events", "schema_metadata"} <= tables
            assert conn.execute("SELECT version FROM schema_metadata").fetchall() == [(1,)]
        conn.close()


def test_unknown_schema_version_refused(tmp_path):
    path = tmp_path / "future.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="version"):
        open_controller_db(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []
    with open_controller_db(tmp_path / "mismatch.sqlite") as conn:
        conn.execute("UPDATE schema_metadata SET version=99")
    conn.close()
    with pytest.raises(ValueError, match="version"):
        open_controller_db(tmp_path / "mismatch.sqlite")
