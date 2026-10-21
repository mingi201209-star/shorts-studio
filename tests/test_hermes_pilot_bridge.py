"""Real queue writes with an approval gate and independently persistent ledger."""


import pytest

from shorts_studio.asset_factory.controller.database import open_controller_db
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

HEAD = "a" * 40


def parsed(intent_id="pilot-001", origin="kanban-1", sha=HEAD):
    return parse_intent(
        ('{"schema":"hermes-controller-pilot/v1","intent_id":"' + intent_id +
         '","origin_task_id":"' + origin + '","source_sha":"' + sha +
         '","kind":"mock_proof","requested_by":"hermes-proposal","payload":{}}').encode(),
        expected_head=sha,
    )


@pytest.fixture
def setup(tmp_path):
    directory = tmp_path / "secure"
    directory.mkdir(mode=0o700)
    controller = open_controller_db(tmp_path / "controller.db")
    conn = open_ledger(directory / "ledger.db")
    yield Ledger(conn), controller
    conn.close()
    controller.close()


def healthy():
    return ResourceView(2 * 1024**3, .50, 0, 0, 0, 0)


def owner_approve(ledger, item):
    ledger.propose(item)
    ledger.approve_operator(item.intent_id, item.input_digest, authority=OperatorAuthority())


def test_unapproved_intent_cannot_enqueue(setup):
    ledger, controller = setup
    p = parsed()
    ledger.propose(p)
    with pytest.raises(BridgeRejected):
        submit_intent(ledger, controller, p, expected_head=HEAD, resources=healthy())
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (0,)


def test_approved_exact_digest_submits_one_mock(setup):
    ledger, controller = setup
    p = parsed()
    owner_approve(ledger, p)
    assert submit_intent(ledger, controller, p, expected_head=HEAD, resources=healthy()) == "submitted"
    assert controller.execute(
        "SELECT worker_kind,budget_usd,max_attempts,state FROM jobs WHERE job_id=?",
        (p.job_id,)).fetchone() == ("mock", "0", 1, "queued")
    assert ledger.lookup(p.intent_id).state == "submitted"


def test_duplicate_proposal_creates_one_controller_job(setup):
    ledger, controller = setup
    p = parsed()
    owner_approve(ledger, p)
    assert submit_intent(ledger, controller, p, expected_head=HEAD, resources=healthy()) == "submitted"
    assert submit_intent(ledger, controller, p, expected_head=HEAD, resources=healthy()) == "already_submitted"
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (1,)
    assert controller.execute("SELECT count(*) FROM attempts").fetchone() == (0,)


def test_controller_identity_conflict_refuses_and_preserves_first(setup):
    ledger, controller = setup
    p = parsed()
    owner_approve(ledger, p)
    # A foreign record that uses our deterministic job ID is not ours.
    from shorts_studio.asset_factory.controller.contracts import JobSpec
    from shorts_studio.asset_factory.controller.queue import enqueue
    foreign = JobSpec(p.job_id, "foreign", "v1", p.source_sha, p.input_digest,
                      "mock-proof", "mock", "{}", max_attempts=1)
    enqueue(controller, foreign)
    with pytest.raises(BridgeRejected):
        submit_intent(ledger, controller, p, expected_head=HEAD, resources=healthy())
    assert controller.execute("SELECT asset_id FROM jobs").fetchone() == ("foreign",)
    assert ledger.lookup(p.intent_id).state == "approved"


def test_crash_before_controller_enqueue_does_not_claim_success(setup, monkeypatch):
    ledger, controller = setup
    p = parsed()
    owner_approve(ledger, p)
    from shorts_studio.asset_factory.integrations.hermes_pilot import bridge

    def fail(_db, _job):
        raise RuntimeError("inject before controller commit")
    monkeypatch.setattr(bridge, "enqueue", fail)
    with pytest.raises(RuntimeError):
        submit_intent(ledger, controller, p, expected_head=HEAD, resources=healthy())
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (0,)
    assert ledger.lookup(p.intent_id).state == "approved"


def test_crash_after_enqueue_before_ledger_commit_reconciles_without_second_attempt(
    setup, monkeypatch,
):
    ledger, controller = setup
    p = parsed()
    owner_approve(ledger, p)
    original = ledger.mark_submitted

    def fail(*_args):
        raise RuntimeError("inject after controller commit")
    monkeypatch.setattr(ledger, "mark_submitted", fail)
    with pytest.raises(RuntimeError):
        submit_intent(ledger, controller, p, expected_head=HEAD, resources=healthy())
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (1,)
    assert ledger.lookup(p.intent_id).state == "approved"
    monkeypatch.setattr(ledger, "mark_submitted", original)
    assert reconcile_submission(ledger, controller, p.intent_id) == "already_submitted"
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (1,)
    assert controller.execute("SELECT count(*) FROM attempts").fetchone() == (0,)


def test_changed_head_blocks_submit_even_with_operator_approval(setup):
    ledger, controller = setup
    p = parsed()
    owner_approve(ledger, p)
    with pytest.raises(BridgeRejected):
        submit_intent(ledger, controller, p, expected_head="b"*40, resources=healthy())
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (0,)


def test_same_id_changed_origin_cannot_take_existing_approval(setup):
    ledger, controller = setup
    p = parsed()
    owner_approve(ledger, p)
    with pytest.raises(BridgeRejected):
        submit_intent(ledger, controller, parsed(origin="kanban-2"), expected_head=HEAD, resources=healthy())
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (0,)



def test_no_enqueue_when_disk_low_or_fourth_request(setup):
    from dataclasses import replace
    ledger, controller = setup
    first = parsed()
    owner_approve(ledger, first)
    with pytest.raises(BridgeRejected) as exc:
        submit_intent(ledger, controller, first, expected_head=HEAD,
                      resources=replace(healthy(), disk_free_ratio=.14))
    assert exc.value.reason_code == "blocked_disk"
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (0,)
    assert ledger.lookup(first.intent_id).approved

    assert submit_intent(ledger, controller, first, expected_head=HEAD,
                         resources=healthy()) == "submitted"
    for num in (2, 3):
        p = parsed(intent_id=f"pilot-00{num}", origin=f"kanban-{num}")
        owner_approve(ledger, p)
        assert submit_intent(ledger, controller, p, expected_head=HEAD,
                             resources=healthy()) == "submitted"
    fourth = parsed(intent_id="pilot-004", origin="kanban-4")
    owner_approve(ledger, fourth)
    with pytest.raises(BridgeRejected) as exc:
        submit_intent(ledger, controller, fourth, expected_head=HEAD,
                      resources=healthy())
    assert exc.value.reason_code == "blocked_capacity"
    assert controller.execute("SELECT count(*) FROM jobs").fetchone() == (3,)
    assert ledger.lookup(fourth.intent_id).state == "approved"
