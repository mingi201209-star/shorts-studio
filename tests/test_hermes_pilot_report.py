"""Independent receipt proof; no fake Hermes/Codex success is enough."""

from dataclasses import FrozenInstanceError

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
from shorts_studio.asset_factory.integrations.hermes_pilot.bridge import submit_intent
from shorts_studio.asset_factory.integrations.hermes_pilot.contracts import parse_intent
from shorts_studio.asset_factory.integrations.hermes_pilot.report import (
    PilotReport,
    inspect_result,
    report_public,
)

HEAD = "a" * 40


@pytest.fixture
def setup(tmp_path):
    priv = tmp_path / "private"
    priv.mkdir(mode=0o700)
    controller = open_controller_db(tmp_path / "controller.db")
    audit = open_ledger(priv / "ledger.db")
    ledger = Ledger(audit)
    raw = ('{"schema":"hermes-controller-pilot/v1","intent_id":"pilot-job1",'
           '"origin_task_id":"kanban-1","source_sha":"' + HEAD +
           '","kind":"mock_proof","requested_by":"hermes-proposal","payload":{}}')
    item = parse_intent(raw.encode(), expected_head=HEAD)
    ledger.propose(item)
    store = LocalArtifactStore(tmp_path / "objects")
    yield ledger, controller, store, item
    audit.close()
    controller.close()


def submit(setup):
    ledger, controller, _, item = setup
    ledger.approve_operator(item.intent_id, item.input_digest, authority=OperatorAuthority())
    assert submit_intent(ledger, controller, item, expected_head=HEAD) == "submitted"


def finish(setup):
    submit(setup)
    _, controller, store, _ = setup
    assert run_once(controller, store, worker=MockWorker(), now=10,
                    disk_free_ratio=.5, monotonic=lambda: 0) == "completed_mock"


def test_mock_completed_with_verified_bytes_returns_proof_verified_mock(setup):
    finish(setup)
    ledger, controller, store, p = setup
    result = inspect_result(ledger, controller, store, p.intent_id)
    assert isinstance(result, PilotReport)
    assert result.status == "proof_verified_mock"
    assert len(result.proof_sha256) == 64
    assert (result.render_qa_pass, result.video_qa_pass, result.publish_ready) == (
        False, False, False)
    with pytest.raises(FrozenInstanceError):
        result.status = "fake"
    public = report_public(result)
    assert all("path" not in k and "token" not in k for k in public)


def test_done_message_without_receipt_is_not_verified(setup):
    submit(setup)
    ledger, controller, store, p = setup
    assert inspect_result(ledger, controller, store, p.intent_id).status == "queued"
    assert inspect_result(ledger, controller, store, p.intent_id).publish_ready is False


@pytest.mark.parametrize("damage", ["delete", "corrupt", "symlink"])
def test_missing_or_changed_blob_rejects_success(setup, damage, tmp_path):
    finish(setup)
    ledger, controller, store, p = setup
    relative = controller.execute(
        "SELECT relative_path FROM receipts WHERE job_id=?", (p.job_id,)
    ).fetchone()[0]
    blob = store.root / relative
    blob.unlink()
    if damage == "corrupt":
        blob.write_bytes(b"tamper")
    if damage == "symlink":
        blob.symlink_to(tmp_path / "missing")
    assert inspect_result(ledger, controller, store, p.intent_id).status == "proof_not_verified"


def test_foreign_receipt_source_digest_is_review_required(setup):
    finish(setup)
    ledger, controller, store, p = setup
    controller.execute("UPDATE receipts SET source_sha=?", ("b" * 40,))
    controller.commit()
    assert inspect_result(ledger, controller, store, p.intent_id).status == "review_required"


def test_report_never_reports_render_or_video_qa(setup):
    finish(setup)
    ledger, controller, store, p = setup
    report = report_public(inspect_result(ledger, controller, store, p.intent_id))
    assert report["render_qa_pass"] is False
    assert report["video_qa_pass"] is False
    assert report["publish_ready"] is False


def test_fake_codex_zero_exit_does_not_grant_mock_completion(setup):
    submit(setup)
    ledger, controller, store, p = setup
    fake_codex_status = "success"
    assert fake_codex_status == "success"
    assert inspect_result(ledger, controller, store, p.intent_id).status == "queued"
    assert not inspect_result(ledger, controller, store, p.intent_id).video_qa_pass
