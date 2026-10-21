"""Validated, operator-mediated single mock queue ingress; no external worker."""

import sqlite3
from dataclasses import astuple, fields, replace

from shorts_studio.asset_factory.controller.contracts import JobSpec
from shorts_studio.asset_factory.controller.queue import enqueue

from .audit import Ledger, LedgerEntry, transaction
from .contracts import ParsedIntent, to_mock_job
from .policy import ResourceView, assess_ingress

_JOB_COLUMNS = tuple(field.name for field in fields(JobSpec))


class BridgeRejected(ValueError):
    """Safe enum, never raw untrusted task or provider output."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def _entry(ledger: Ledger, intent_id: str) -> LedgerEntry:
    try:
        return ledger.lookup(intent_id)
    except ValueError as exc:
        raise BridgeRejected("unknown_proposal") from exc


def _same_controller_job(conn: sqlite3.Connection, job: JobSpec) -> bool | None:
    """None = absent, False = foreign record, True = exact identity."""
    row = conn.execute(
        f"SELECT {', '.join(_JOB_COLUMNS)} FROM jobs WHERE job_id=?",
        (job.job_id,),
    ).fetchone()
    if row is None:
        return None
    return tuple(row) == astuple(job)


def _check_entry(entry: LedgerEntry, parsed: ParsedIntent, expected_head: str) -> None:
    if (entry.intent_id != parsed.intent_id
            or entry.origin_task_id != parsed.origin_task_id
            or entry.input_digest != parsed.input_digest
            or entry.source_sha != parsed.source_sha or entry.job_id != parsed.job_id):
        raise BridgeRejected("identity_conflict")
    if expected_head != parsed.source_sha:
        raise BridgeRejected("head_drift")
    if not entry.approved or entry.state == "proposed":
        raise BridgeRejected("approval_required")


def submit_intent(
    ledger: Ledger, controller_conn: sqlite3.Connection, parsed: ParsedIntent, *,
    expected_head: str, resources: ResourceView | None = None,
) -> str:
    """Submit one approved, exact-SHA mock job; no promotion to native render."""
    if not isinstance(parsed, ParsedIntent):
        raise BridgeRejected("invalid_proposal")
    job = to_mock_job(parsed)
    with transaction(ledger.conn):
        entry = _entry(ledger, parsed.intent_id)
        _check_entry(entry, parsed, expected_head)
        found = _same_controller_job(controller_conn, job)
        if found is None:
            # Counters from the trusted caller cannot understate this ledger's
            # authoritative cumulative P0 session limits or active mock work.
            if resources is None:
                raise BridgeRejected("resource_metrics_unavailable")
            pending = ledger.conn.execute(
                "SELECT count(*) FROM proposals WHERE state IN ('proposed','approved')"
            ).fetchone()[0]
            submitted = ledger.conn.execute(
                "SELECT count(*) FROM proposals WHERE state='submitted'"
            ).fetchone()[0]
            active = controller_conn.execute(
                "SELECT count(*) FROM jobs WHERE state='running'"
            ).fetchone()[0]
            current = replace(
                resources,
                pending_proposals=max(resources.pending_proposals, pending),
                accepted_this_session=max(resources.accepted_this_session, submitted),
                active_mock_workers=max(resources.active_mock_workers, active),
            )
            try:
                admissible = assess_ingress(current)
            except ValueError as exc:
                raise BridgeRejected("resource_metrics_unavailable") from exc
            if admissible not in ("allow", "warn_memory"):
                raise BridgeRejected(admissible)
        if found is False:
            raise BridgeRejected("foreign_controller_job")
        if found is None:
            try:
                enqueue(controller_conn, job)
            except ValueError as exc:
                raise BridgeRejected("controller_identity_conflict") from exc
            ledger.mark_submitted(parsed.intent_id, parsed.job_id)
            return "submitted"
        ledger.mark_submitted(parsed.intent_id, parsed.job_id)
        return "already_submitted"


def reconcile_submission(
    ledger: Ledger, controller_conn: sqlite3.Connection, intent_id: str,
) -> str:
    """Recover an enqueue committed before the bridge acknowledgement."""
    with transaction(ledger.conn):
        entry = _entry(ledger, intent_id)
        if not entry.approved:
            return "review_required"
        identity = JobSpec(
            job_id=entry.job_id, asset_id="hermes-pilot", asset_version="v1",
            source_sha=entry.source_sha, input_digest=entry.input_digest,
            stage="mock-proof", worker_kind="mock", payload_json="{}",
            max_attempts=1, budget_usd="0",
        )
        if _same_controller_job(controller_conn, identity) is not True:
            return "review_required"
        ledger.mark_submitted(entry.intent_id, entry.job_id)
        return "already_submitted"
