"""Real Controller queue/storage, fake upstream, zero real Codex calls."""

import json

import pytest

from shorts_studio.asset_factory.controller.artifacts import LocalArtifactStore
from shorts_studio.asset_factory.controller.database import open_controller_db
from shorts_studio.asset_factory.controller.runner import run_once
from shorts_studio.asset_factory.controller.workers import MockWorker
from shorts_studio.asset_factory.integrations.hermes_pilot.audit import (
    Ledger,
    OperatorAuthority,
    open_ledger,
)
from shorts_studio.asset_factory.integrations.hermes_pilot.bridge import (
    BridgeRejected,
    reconcile_submission,
    submit_intent,
)
from shorts_studio.asset_factory.integrations.hermes_pilot.contracts import parse_intent
from shorts_studio.asset_factory.integrations.hermes_pilot.policy import ResourceView
from shorts_studio.asset_factory.integrations.hermes_pilot.report import inspect_result

HEAD = "a" * 40


class FakeHermes:
    """Produces only untrusted data; cannot mint operator approval."""

    def __init__(self):
        self.codex_invocations = 0

    def propose(self, intent_id, origin_id):
        payload = {
            "schema": "hermes-controller-pilot/v1", "intent_id": intent_id,
            "origin_task_id": origin_id, "source_sha": HEAD, "kind": "mock_proof",
            "requested_by": "hermes-proposal", "payload": {},
        }
        return parse_intent(json.dumps(payload).encode(), expected_head=HEAD)


class FakeOwnerApproval:
    """Test-only trusted capability; no real owner prompt or profile."""

    @staticmethod
    def approve(ledger, item):
        return ledger.approve_operator(
            item.intent_id, item.input_digest, authority=OperatorAuthority()
        )


@pytest.fixture
def state(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    controller_path = tmp_path / "controller.db"
    audit_path = private / "audit.db"
    obj_path = tmp_path / "artifacts"
    controller = open_controller_db(controller_path)
    audit = open_ledger(audit_path)
    yield Ledger(audit), controller, LocalArtifactStore(obj_path), controller_path, audit_path
    audit.close()
    controller.close()


def resources():
    return ResourceView(2*1024**3, .50, 0, 0, 0, 0)


def test_three_distinct_owner_approved_mock_jobs_produce_verified_receipts(state):
    ledger, controller, store, _, _ = state
    harness = FakeHermes()
    items = [harness.propose(f"pilot-{i:03d}", f"kanban-{i}") for i in (1, 2, 3)]
    for item in items:
        ledger.propose(item)
        FakeOwnerApproval.approve(ledger, item)
        assert submit_intent(ledger, controller, item, expected_head=HEAD,
                             resources=resources()) == "submitted"
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (3,)
    assert controller.execute("SELECT count(*) FROM attempts").fetchone() == (0,)
    for _ in range(3):
        assert run_once(controller, store, worker=MockWorker(), now=10,
                        disk_free_ratio=.5, monotonic=lambda: 0) == "completed_mock"
    digests = set()
    for item in items:
        result = inspect_result(ledger, controller, store, item.intent_id)
        assert result.status == "proof_verified_mock"
        assert (result.render_qa_pass, result.video_qa_pass, result.publish_ready) == (
            False, False, False)
        digests.add(result.proof_sha256)
    assert len(digests) == 3
    assert controller.execute("SELECT count(*) FROM receipts").fetchone() == (3,)
    assert controller.execute("SELECT count(*) FROM attempts").fetchone() == (3,)
    assert harness.codex_invocations == 0

def test_restart_between_enqueue_and_ledger_ack_is_idempotent(state, monkeypatch):
    ledger, controller, store, ctrl_path, audit_path = state
    item = FakeHermes().propose("pilot-001", "kanban-1")
    ledger.propose(item)
    FakeOwnerApproval.approve(ledger, item)
    def crash(*_):
        raise RuntimeError("injected process death after external commit")
    monkeypatch.setattr(ledger, "mark_submitted", crash)
    with pytest.raises(RuntimeError):
        submit_intent(ledger, controller, item, expected_head=HEAD,
                      resources=resources())
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (1,)
    controller.close()
    ledger.conn.close()
    after_ctrl = open_controller_db(ctrl_path)
    after_audit = open_ledger(audit_path)
    try:
        resumed = Ledger(after_audit)
        assert reconcile_submission(resumed, after_ctrl, item.intent_id) == "already_submitted"
        assert after_ctrl.execute("SELECT count(*) FROM jobs").fetchone() == (1,)
        assert run_once(after_ctrl, store, worker=MockWorker(), now=10,
                        disk_free_ratio=.5, monotonic=lambda: 0) == "completed_mock"
        assert inspect_result(resumed, after_ctrl, store, item.intent_id).status == (
            "proof_verified_mock")
        assert after_ctrl.execute("SELECT count(*) FROM attempts").fetchone() == (1,)
    finally:
        after_ctrl.close()
        after_audit.close()


def test_mock_worker_lease_expiry_stays_blocked(state):
    from shorts_studio.asset_factory.controller.queue import claim_next
    from shorts_studio.asset_factory.controller.recovery import reconcile_expired
    ledger, controller, store, _, _ = state
    item = FakeHermes().propose("pilot-001", "kanban-1")
    ledger.propose(item)
    FakeOwnerApproval.approve(ledger, item)
    submit_intent(ledger, controller, item, expected_head=HEAD, resources=resources())
    claim = claim_next(controller, "fake-killed-worker", 10, 2)
    assert claim is not None
    reconcile_expired(controller, store, 100, lambda _claim: "unknown")
    result = inspect_result(ledger, controller, store, item.intent_id)
    assert result.status == "blocked"
    assert result.publish_ready is False
    assert controller.execute("SELECT count(*) FROM attempts").fetchone() == (1,)
    assert controller.execute("SELECT count(*) FROM receipts").fetchone() == (0,)
    assert run_once(controller, store, worker=MockWorker(), now=101,
                    disk_free_ratio=.5, monotonic=lambda: 0) == "idle"
    assert controller.execute("SELECT count(*) FROM attempts").fetchone() == (1,)


def test_unauthorized_approval_never_executes(state):
    ledger, controller, store, _, _ = state
    item = FakeHermes().propose("pilot-001", "kanban-1")
    ledger.propose(item)
    with pytest.raises(BridgeRejected):
        submit_intent(ledger, controller, item, expected_head=HEAD,
                      resources=resources())
    assert run_once(controller, store, worker=MockWorker(), now=10,
                    disk_free_ratio=.5, monotonic=lambda: 0) == "idle"
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (0,)


def test_corrupt_or_missing_artifact_cannot_report_success(state):
    ledger, controller, store, _, _ = state
    item = FakeHermes().propose("pilot-001", "kanban-1")
    ledger.propose(item)
    FakeOwnerApproval.approve(ledger, item)
    submit_intent(ledger, controller, item, expected_head=HEAD, resources=resources())
    assert run_once(controller, store, worker=MockWorker(), now=10,
                    disk_free_ratio=.5, monotonic=lambda: 0) == "completed_mock"
    path = controller.execute("SELECT relative_path FROM receipts").fetchone()[0]
    (store.root / path).unlink()
    assert inspect_result(ledger, controller, store, item.intent_id).status == (
        "proof_not_verified")


def test_out_of_scope_codex_fake_success_not_production_qa(state):
    ledger, controller, store, _, _ = state
    item = FakeHermes().propose("pilot-001", "kanban-1")
    ledger.propose(item)
    FakeOwnerApproval.approve(ledger, item)
    submit_intent(ledger, controller, item, expected_head=HEAD, resources=resources())
    fake_codex = {"exit_code": 0, "status": "success"}
    assert fake_codex["status"] == "success"
    report = inspect_result(ledger, controller, store, item.intent_id)
    assert report.status == "queued"
    assert not report.render_qa_pass and not report.video_qa_pass
    assert not report.publish_ready


def test_rejects_sneaky_untrusted_command_payload():
    payload = {
        "schema": "hermes-controller-pilot/v1", "intent_id": "pilot-001",
        "origin_task_id": "kanban-1", "source_sha": HEAD, "kind": "mock_proof",
        "requested_by": "hermes-proposal", "payload": {"command": "sudo reboot"},
    }
    with pytest.raises(ValueError):
        parse_intent(json.dumps(payload).encode(), expected_head=HEAD)


def test_fake_hermes_cannot_directly_approve_or_modify_controller_sqlite(state):
    """P0 wire-boundary only; real Hermes UID separation is deferred to P1."""
    ledger, controller, store, _, _ = state
    p = FakeHermes().propose("pilot-001", "kanban-1")
    ledger.propose(p)
    malicious = {
        "schema": "hermes-controller-pilot/v1", "intent_id": "pilot-001",
        "origin_task_id": "kanban-1", "source_sha": HEAD, "kind": "mock_proof",
        "requested_by": "owner-reviewed", "payload": {},
    }
    with pytest.raises(ValueError):
        parse_intent(json.dumps(malicious).encode(), expected_head=HEAD)
    with pytest.raises(ValueError):
        ledger.approve_operator(p.intent_id, p.input_digest, authority=malicious)
    with pytest.raises(BridgeRejected):
        submit_intent(ledger, controller, p, expected_head=HEAD, resources=resources())
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (0,)
    assert run_once(controller, store, worker=MockWorker(), now=10,
                    disk_free_ratio=.5, monotonic=lambda: 0) == "idle"


def test_runbook_has_separate_p1_p2_authorization():
    from pathlib import Path
    doc = Path(__file__).resolve().parents[1] / "docs/operations/hermes-controller-pilot.md"
    text = doc.read_text(encoding="utf-8")
    assert "P0" in text and "P1" in text and "P2" in text
    assert "별도 승인" in text
    assert "auth.adopt_external_logins=false" in text
    assert "UID" in text
    assert "24시간" in text


def test_bridge_does_not_dispatch_codex_or_paid_provider(state, monkeypatch):
    import subprocess

    from shorts_studio.asset_factory.integrations.hermes_pilot import bridge
    assert not hasattr(bridge, "CodexWorker")
    calls = []
    def deny_any_subprocess(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("an external subprocess would violate P0")
    monkeypatch.setattr(subprocess, "run", deny_any_subprocess)
    ledger, controller, store, _, _ = state
    p = FakeHermes().propose("pilot-001", "kanban-1")
    ledger.propose(p)
    FakeOwnerApproval.approve(ledger, p)
    assert submit_intent(ledger, controller, p, expected_head=HEAD,
                         resources=resources()) == "submitted"
    assert run_once(controller, store, worker=MockWorker(), now=10,
                    disk_free_ratio=.5, monotonic=lambda: 0) == "completed_mock"
    assert calls == []
