"""Persisted operator-only approval ledger, no live provider interactions."""

import os
import sqlite3

import pytest

from shorts_studio.asset_factory.integrations.hermes_pilot.audit import (
    Ledger,
    OperatorAuthority,
    open_ledger,
)
from shorts_studio.asset_factory.integrations.hermes_pilot.contracts import parse_intent

HEAD = "a" * 40


def intent(intent_id="first-job", origin_task_id="kanban-1"):
    raw = ('{"schema":"hermes-controller-pilot/v1","intent_id":"' + intent_id +
           '","origin_task_id":"' + origin_task_id +
           '","source_sha":"' + HEAD +
           '","kind":"mock_proof","requested_by":"hermes-proposal","payload":{}}')
    return parse_intent(raw.encode(), expected_head=HEAD)


def make_ledger(tmp_path):
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    return open_ledger(folder / "audit.db")


def test_private_ledger_requires_secure_directory(tmp_path):
    allowed = tmp_path / "secure"
    allowed.mkdir(mode=0o700)
    c = open_ledger(allowed / "audit.db")
    assert c.execute("PRAGMA user_version").fetchone() == (1,)
    assert (allowed / "audit.db").stat().st_mode & 0o077 == 0
    c.close()
    denied = tmp_path / "public"
    denied.mkdir(mode=0o755)
    with pytest.raises(ValueError):
        open_ledger(denied / "audit.db")


def test_propose_idempotent_and_conflict_preserves_first_digest(tmp_path):
    c = make_ledger(tmp_path)
    a = intent()
    ledger = Ledger(c)
    assert ledger.propose(a) == "proposed"
    assert ledger.propose(a) == "already_proposed"
    with pytest.raises(ValueError):
        ledger.propose(intent(origin_task_id="kanban-2"))
    assert ledger.lookup("first-job").input_digest == a.input_digest
    assert c.execute("SELECT count(*) FROM proposals").fetchone() == (1,)
    c.close()


def test_owner_approval_exact_digest_only(tmp_path):
    c = make_ledger(tmp_path)
    ledger = Ledger(c)
    p = intent()
    ledger.propose(p)
    with pytest.raises(ValueError):
        ledger.approve_operator(p.intent_id, "b"*64, authority=OperatorAuthority())
    assert not ledger.lookup(p.intent_id).approved
    assert ledger.approve_operator(p.intent_id, p.input_digest,
                                   authority=OperatorAuthority()) == "approved"
    assert ledger.lookup(p.intent_id).approved
    assert c.execute("SELECT digest FROM approvals").fetchone() == (p.input_digest,)
    c.close()


def test_persist_after_close_reopen(tmp_path):
    c = make_ledger(tmp_path)
    p = intent()
    ledger = Ledger(c)
    ledger.propose(p)
    ledger.approve_operator(p.intent_id, p.input_digest, authority=OperatorAuthority())
    c.close()
    reopened = open_ledger(tmp_path / "private" / "audit.db")
    assert Ledger(reopened).lookup(p.intent_id).approved
    reopened.close()


def test_non_owner_or_hermes_cannot_approve(tmp_path):
    c = make_ledger(tmp_path)
    ledger = Ledger(c)
    p = intent(origin_task_id="approved")
    ledger.propose(p)
    for authority in (None, "approved", {"approved": True}, object()):
        with pytest.raises(ValueError):
            ledger.approve_operator(p.intent_id, p.input_digest, authority=authority)
    assert not ledger.lookup(p.intent_id).approved
    c.close()


def test_private_ledger_rejects_symlinks_and_invalid_schema(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    outside = tmp_path / "target.db"
    outside.touch()
    (private / "bad.db").symlink_to(outside)
    with pytest.raises(ValueError):
        open_ledger(private / "bad.db")
    renamed = tmp_path / "renamed"
    renamed.mkdir(mode=0o700)
    (private / "alias").symlink_to(renamed, target_is_directory=True)
    with pytest.raises(ValueError):
        open_ledger(private / "alias" / "audit.db")
    conn = sqlite3.connect(private / "invalid.db")
    conn.execute("PRAGMA user_version=9")
    conn.close()
    os.chmod(private / "invalid.db", 0o600)
    with pytest.raises(ValueError):
        open_ledger(private / "invalid.db")


def test_two_connections_cannot_change_approved_intent(tmp_path):
    c = make_ledger(tmp_path)
    d = open_ledger(tmp_path / "private" / "audit.db")
    first = Ledger(c)
    second = Ledger(d)
    p = intent()
    assert first.propose(p) == "proposed"
    assert second.propose(p) == "already_proposed"
    first.approve_operator(p.intent_id, p.input_digest, authority=OperatorAuthority())
    assert second.approve_operator(p.intent_id, p.input_digest,
                                   authority=OperatorAuthority()) == "already_approved"
    assert second.lookup(p.intent_id).approved
    c.close()
    d.close()
