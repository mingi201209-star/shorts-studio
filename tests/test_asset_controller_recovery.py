"""Fail-closed recovery and offline, verified SQLite snapshots."""

import hashlib
import sqlite3
from dataclasses import astuple, replace

import pytest

from shorts_studio.asset_factory.controller.artifacts import LocalArtifactStore
from shorts_studio.asset_factory.controller.contracts import JobSpec
from shorts_studio.asset_factory.controller.database import open_controller_db
from shorts_studio.asset_factory.controller.queue import claim_next, complete_claim, enqueue
from shorts_studio.asset_factory.controller.recovery import (
    reconcile_expired,
    restore_db,
    snapshot_db,
)


@pytest.fixture
def setup(tmp_path):
    conn = open_controller_db(tmp_path / "live.db")
    job = JobSpec("job", "asset", "v1", "a" * 40, "b" * 64, "proof", "mock", "{}")
    store = LocalArtifactStore(tmp_path / "objects")
    yield conn, job, store
    conn.close()


def state(conn):
    return conn.execute("SELECT state FROM jobs").fetchone()[0]


def expire(conn, job):
    enqueue(conn, job)
    return claim_next(conn, "worker", 10, 5)


def persist(conn, receipt, token=1):
    conn.execute("INSERT INTO receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (*astuple(receipt), token, 11))
    conn.commit()


def test_unknown_expired_job_is_blocked_without_retry(setup):
    conn, job, store = setup
    claim = expire(conn, job)
    assert reconcile_expired(conn, store, 15, lambda c: "unknown") == [job.job_id]
    assert state(conn) == "blocked"
    assert claim_next(conn, "retry", 100, 10) is None
    assert not complete_claim(conn, claim, store.put(job, b"late"), 100)
    assert conn.execute("SELECT outcome FROM attempts").fetchone() == ("blocked",)
    assert conn.execute("SELECT count(*) FROM events WHERE kind='blocked'").fetchone() == (1,)
    assert reconcile_expired(conn, store, 100, lambda c: pytest.fail("repeated lookup")) == []


@pytest.mark.parametrize("proof", ["missing", "valid", "corrupt", "foreign", "stale"])
def test_completed_external_result_must_have_verified_receipt(setup, proof):
    conn, job, store = setup
    expire(conn, job)
    if proof != "missing":
        receipt = store.put(job, b"proof")
        if proof == "foreign":
            receipt = replace(receipt, source_sha="c" * 40)
        persist(conn, receipt, 99 if proof == "stale" else 1)
        if proof == "corrupt":
            (store.root / receipt.relative_path).write_bytes(b"wrong")
    reconcile_expired(conn, store, 20, lambda c: "completed")
    assert state(conn) == ("completed_mock" if proof == "valid" else "blocked")
    assert claim_next(conn, "retry", 100, 10) is None


def test_known_not_started_respects_attempt_budget(setup):
    conn, job, store = setup
    old = expire(conn, job)
    reconcile_expired(conn, store, 20, lambda c: "not_started")
    assert state(conn) == "queued"
    new = claim_next(conn, "retry", 21, 5)
    assert new.attempt == 2 and new.fencing_token > old.fencing_token
    assert not complete_claim(conn, old, store.put(job, b"old"), 22)
    reconcile_expired(conn, store, 26, lambda c: "not_started")
    assert state(conn) == "blocked"
    assert claim_next(conn, "retry", 100, 10) is None


@pytest.mark.parametrize("status", ["garbage", "Completed", "", None, [], "unreachable"])
def test_unknown_worker_statuses_fail_closed(setup, status):
    conn, job, store = setup
    expire(conn, job)

    def lookup(claim):
        if status == "unreachable":
            raise OSError("external unavailable")
        return status

    reconcile_expired(conn, store, 20, lookup)
    assert state(conn) == "blocked"
    assert claim_next(conn, "retry", 100, 10) is None


def test_running_and_unexpired_jobs_are_not_retried(setup):
    conn, job, store = setup
    claim = expire(conn, job)
    assert reconcile_expired(conn, store, 14, lambda c: pytest.fail("too early")) == []
    assert reconcile_expired(conn, store, 15, lambda c: "running") == []
    assert state(conn) == "running"
    assert claim_next(conn, "retry", 100, 10) is None
    assert conn.execute("SELECT lease_until FROM leases").fetchone() == (claim.lease_until,)


def test_snapshot_restore_survives_reopen(setup, tmp_path):
    conn, job, store = setup
    expire(conn, job)
    reconcile_expired(conn, store, 20, lambda c: "unknown")
    enqueue(conn, replace(job, job_id="queued"))
    source = tmp_path / "snapshot.db"
    digest = snapshot_db(conn, source)
    assert digest == hashlib.sha256(source.read_bytes()).hexdigest()
    assert source.with_suffix(source.suffix + ".sha256").read_text().strip() == digest
    dest = tmp_path / "restored.db"
    restore_db(source, dest, digest)
    restored = open_controller_db(dest)
    try:
        assert restored.execute("SELECT state, count(*) FROM jobs GROUP BY state").fetchall() == [
            ("blocked", 1), ("queued", 1)]
        assert restored.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        restored.close()


def test_corrupt_snapshot_does_not_overwrite_good_db(setup, tmp_path):
    conn, job, _ = setup
    enqueue(conn, job)
    source, dest = tmp_path / "snapshot.db", tmp_path / "good.db"
    digest = snapshot_db(conn, source)
    restore_db(source, dest, digest)
    before = dest.read_bytes()
    source.write_bytes(b"corrupt")
    for expected in (digest, hashlib.sha256(source.read_bytes()).hexdigest()):
        with pytest.raises(ValueError):
            restore_db(source, dest, expected)
        assert dest.read_bytes() == before


@pytest.mark.parametrize("schema", ["version", "metadata", "missing_table", "missing_column"])
def test_invalid_snapshot_schema_preserves_destination(setup, tmp_path, schema):
    conn, _, _ = setup
    source, dest = tmp_path / "snapshot.db", tmp_path / "good.db"
    digest = snapshot_db(conn, source)
    restore_db(source, dest, digest)
    before = dest.read_bytes()
    bad = sqlite3.connect(source)
    bad.execute({"version": "PRAGMA user_version=99",
                 "metadata": "UPDATE schema_metadata SET version=99",
                 "missing_table": "DROP TABLE events",
                 "missing_column": "ALTER TABLE jobs DROP COLUMN retry_after"}[schema])
    bad.commit()
    bad.close()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        restore_db(source, dest, digest)
    assert dest.read_bytes() == before


@pytest.mark.parametrize("locked", [False, True])
def test_restore_refuses_open_destination(setup, tmp_path, locked):
    conn, _, _ = setup
    source, dest = tmp_path / "snapshot.db", tmp_path / "good.db"
    digest = snapshot_db(conn, source)
    restore_db(source, dest, digest)
    live = open_controller_db(dest)
    try:
        if locked:
            live.execute("BEGIN IMMEDIATE")
        before = dest.read_bytes()
        with pytest.raises(ValueError):
            restore_db(source, dest, digest)
        assert dest.read_bytes() == before
    finally:
        live.close()


def test_lookup_race_cannot_overwrite_new_claim(setup):
    conn, job, store = setup
    expire(conn, job)

    def lookup(claim):
        reconcile_expired(conn, store, 20, lambda c: "not_started")
        claim_next(conn, "new", 21, 20)
        return "unknown"

    assert reconcile_expired(conn, store, 20, lookup) == []
    assert state(conn) == "running"
    assert conn.execute("SELECT owner FROM leases").fetchone() == ("new",)


def test_single_attempt_not_started_is_blocked(setup):
    conn, job, store = setup
    expire(conn, replace(job, max_attempts=1))
    reconcile_expired(conn, store, 15, lambda c: "not_started")
    assert state(conn) == "blocked"
    assert claim_next(conn, "retry", 100, 10) is None


def test_live_wal_source_is_not_restored(setup, tmp_path):
    conn, job, _ = setup
    enqueue(conn, job)
    source = tmp_path / "live.db"
    dest = tmp_path / "untouched.db"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        restore_db(source, dest, digest)
    assert not dest.exists()


def test_snapshot_rejects_caller_transaction(setup, tmp_path):
    conn, _, _ = setup
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(ValueError):
        snapshot_db(conn, tmp_path / "snapshot.db")
    assert conn.in_transaction
    conn.rollback()
