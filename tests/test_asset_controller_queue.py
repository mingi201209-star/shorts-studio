"""Queue transitions use persisted identity and fencing, not artifact QA."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from shorts_studio.asset_factory.controller.contracts import ArtifactReceipt, JobSpec
from shorts_studio.asset_factory.controller.database import open_controller_db
from shorts_studio.asset_factory.controller.queue import (
    block_claim,
    claim_next,
    complete_claim,
    enqueue,
)


@pytest.fixture
def conn(tmp_path):
    db = open_controller_db(tmp_path / "queue.db")
    yield db
    db.close()


def job(**changes):
    return replace(JobSpec("job", "asset", "v1", "a" * 40, "b" * 64,
                           "proof", "mock", "{}"), **changes)


def receipt(**changes):
    return replace(ArtifactReceipt("job", "a" * 40, "b" * 64,
                                   "c" * 64, "sha256/proof", 12), **changes)


def counts(conn):
    return tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                 for table in ("jobs", "attempts", "leases", "receipts", "events"))


def test_duplicate_identity_conflict_rejected(conn):
    assert enqueue(conn, job()) is True
    before = counts(conn)
    assert enqueue(conn, job()) is False
    for changes in ({"source_sha": "d" * 40}, {"input_digest": "e" * 64},
                    {"payload_json": "{ }"}, {"asset_id": "other"},
                    {"asset_version": "v2"}, {"stage": "other"},
                    {"worker_kind": "codex"}, {"max_attempts": 3}, {"budget_usd": "0.0"}):
        with pytest.raises(ValueError):
            enqueue(conn, job(**changes))
    assert counts(conn) == before


def test_simultaneous_claimers_only_one_wins(tmp_path):
    path = tmp_path / "shared.db"
    db = open_controller_db(path)
    enqueue(db, job())
    db.close()
    barrier = Barrier(2)

    def claim(owner):
        connection = open_controller_db(path)
        try:
            barrier.wait(timeout=5)
            return claim_next(connection, owner, 10, 20)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, ("one", "two")))
    assert sum(value is not None for value in claims) == 1
    db = open_controller_db(path)
    assert counts(db)[:3] == (1, 1, 1)
    assert claim_next(db, "third", 100, 20) is None  # expiry is not retry evidence
    db.close()


def test_stale_fencing_token_cannot_complete(conn):
    enqueue(conn, job())
    old = claim_next(conn, "worker", 10, 20)
    # Simulate a later recovery task's evidence-authorized requeue, not automatic expiry.
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("DELETE FROM leases")
    conn.execute("UPDATE jobs SET state='queued'")
    conn.commit()
    new = claim_next(conn, "worker", 31, 20)
    assert new.fencing_token > old.fencing_token
    assert new.attempt == old.attempt + 1
    before = counts(conn)
    assert complete_claim(conn, old, receipt(), 32) is False
    assert block_claim(conn, old, "late", 32) is False
    assert counts(conn) == before
    assert complete_claim(conn, new, receipt(), 32) is True


def test_different_source_sha_cannot_complete(conn):
    enqueue(conn, job())
    claim = claim_next(conn, "worker", 10, 20)
    before = counts(conn)
    for changes in ({"source_sha": "d" * 40}, {"input_digest": "e" * 64},
                    {"job_id": "foreign"}):
        assert complete_claim(conn, claim, receipt(**changes), 11) is False
        assert complete_claim(conn, replace(claim, **changes), receipt(), 11) is False
    for changes in ({"owner": "other"}, {"attempt": 2}, {"fencing_token": 2},
                    {"lease_until": 31}):
        forged = replace(claim, **changes)
        assert complete_claim(conn, forged, receipt(), 11) is False
        assert block_claim(conn, forged, "forged", 11) is False
    assert counts(conn) == before


def test_codex_not_automatically_claimable(conn):
    enqueue(conn, job(worker_kind="codex"))
    assert claim_next(conn, "worker", 10, 20) is None
    enqueue(conn, job(job_id="mock"))
    assert claim_next(conn, "worker", 10, 20).job_id == "mock"


@pytest.mark.parametrize("now", [30, 31])
def test_expired_lease_cannot_complete_or_block(conn, now):
    enqueue(conn, job())
    claim = claim_next(conn, "worker", 10, 20)
    before = counts(conn)
    assert complete_claim(conn, claim, receipt(), now) is False
    assert block_claim(conn, claim, "expired", now) is False
    assert counts(conn) == before


def test_completion_is_idempotent_and_receipt_is_immutable(conn):
    enqueue(conn, job())
    claim = claim_next(conn, "worker", 10, 20)
    assert complete_claim(conn, claim, receipt(), 11) is True
    before = counts(conn)
    assert complete_claim(conn, claim, receipt(), 12) is False
    assert complete_claim(conn, claim, receipt(artifact_sha256="d" * 64), 12) is False
    assert block_claim(conn, claim, "late", 12) is False
    assert counts(conn) == before
    assert conn.execute("SELECT state FROM jobs").fetchone() == ("completed_mock",)
    assert conn.execute("SELECT outcome FROM attempts").fetchone() == ("completed_mock",)


def test_block_is_durable_and_not_retried(conn):
    enqueue(conn, job())
    claim = claim_next(conn, "worker", 10, 20)
    assert block_claim(conn, claim, "worker uncertain", 11) is True
    before = counts(conn)
    assert block_claim(conn, claim, "worker uncertain", 12) is False
    assert claim_next(conn, "other", 40, 20) is None
    assert counts(conn) == before
    assert conn.execute("SELECT state, blocked_reason FROM jobs").fetchone() == (
        "blocked", "worker uncertain")
    assert conn.execute("SELECT outcome FROM attempts").fetchone() == ("blocked",)


@pytest.mark.parametrize("owner, now, duration", [
    ("", 10, 20), (" ", 10, 20), ("worker", 10, 0), ("worker", 10, -1),
    ("worker", float("nan"), 20), ("worker", 10, float("inf")),
    ("worker", -1, 20), ("worker", 1e308, 1e308),
])
def test_invalid_claim_arguments_do_not_mutate(conn, owner, now, duration):
    enqueue(conn, job())
    before = counts(conn)
    with pytest.raises(ValueError):
        claim_next(conn, owner, now, duration)
    assert counts(conn) == before


def test_validation_and_attempt_budget(conn):
    assert claim_next(conn, "worker", 10, 20) is None
    enqueue(conn, job(max_attempts=1))
    claim = claim_next(conn, "worker", 10, 20)
    for reason in ("", " "):
        with pytest.raises(ValueError):
            block_claim(conn, claim, reason, 11)
    for transition in (lambda: complete_claim(conn, claim, receipt(), float("nan")),
                       lambda: block_claim(conn, claim, "reason", float("inf"))):
        with pytest.raises(ValueError):
            transition()
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("DELETE FROM leases")
    conn.execute("UPDATE jobs SET state='queued'")
    conn.commit()
    assert claim_next(conn, "worker", 31, 20) is None


def test_mutations_use_immediate_transactions(conn):
    statements = []
    conn.set_trace_callback(statements.append)
    enqueue(conn, job())
    claim = claim_next(conn, "worker", 10, 20)
    complete_claim(conn, claim, receipt(), 11)
    enqueue(conn, job(job_id="other"))
    other = claim_next(conn, "worker", 10, 20)
    block_claim(conn, other, "uncertain", 11)
    assert [s for s in statements if s.startswith("BEGIN")] == ["BEGIN IMMEDIATE"] * 6
