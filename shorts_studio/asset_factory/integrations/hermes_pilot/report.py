"""Proof-of-bytes projection; an AI's claim of success has no authority."""

import sqlite3
from dataclasses import astuple, dataclass, fields

from shorts_studio.asset_factory.controller.artifacts import LocalArtifactStore
from shorts_studio.asset_factory.controller.contracts import ArtifactReceipt, JobSpec

from .audit import Ledger

_JOB_COLUMNS = tuple(field.name for field in fields(JobSpec))
_STATUSES = frozenset({
    "awaiting_approval", "queued", "running", "blocked",
    "proof_not_verified", "proof_verified_mock", "review_required",
})


@dataclass(frozen=True)
class PilotReport:
    intent_id: str
    status: str
    proof_sha256: str | None = None
    render_qa_pass: bool = False
    video_qa_pass: bool = False
    publish_ready: bool = False


def inspect_result(
    ledger: Ledger, controller_conn: sqlite3.Connection, store: LocalArtifactStore,
    intent_id: str,
) -> PilotReport:
    """Read exact Controller identity + independently hash local receipt bytes."""
    try:
        info = ledger.lookup(intent_id)
    except ValueError:
        return PilotReport("", "review_required")
    if not info.approved:
        return PilotReport(info.intent_id, "awaiting_approval")
    identity = JobSpec(
        info.job_id, "hermes-pilot", "v1", info.source_sha, info.input_digest,
        "mock-proof", "mock", "{}", max_attempts=1, budget_usd="0",
    )
    row = controller_conn.execute(
        f"SELECT {', '.join(_JOB_COLUMNS)}, state, fencing_token "
        "FROM jobs WHERE job_id=?", (info.job_id,)
    ).fetchone()
    if row is None:
        return PilotReport(info.intent_id, "review_required")
    expected = astuple(identity)
    if tuple(row[:len(expected)]) != expected:
        return PilotReport(info.intent_id, "review_required")
    state, token = row[-2:]
    if state in ("queued", "running", "blocked"):
        return PilotReport(info.intent_id, state)
    if state != "completed_mock":
        return PilotReport(info.intent_id, "review_required")
    stored = controller_conn.execute(
        """SELECT job_id,source_sha,input_digest,artifact_sha256,
                  relative_path,byte_count,fencing_token
           FROM receipts WHERE job_id=?""", (info.job_id,),
    ).fetchone()
    if stored is None:
        return PilotReport(info.intent_id, "proof_not_verified")
    try:
        receipt = ArtifactReceipt(*stored[:6])
    except ValueError:
        return PilotReport(info.intent_id, "review_required")
    if (stored[6] != token or receipt.source_sha != info.source_sha
            or receipt.input_digest != info.input_digest or receipt.job_id != info.job_id):
        return PilotReport(info.intent_id, "review_required")
    if not store.verify(identity, receipt):
        return PilotReport(info.intent_id, "proof_not_verified")
    return PilotReport(info.intent_id, "proof_verified_mock", receipt.artifact_sha256)


def report_public(report: PilotReport) -> dict[str, str | bool | None]:
    """Return only a bounded enum, digest, and explicit non-production flags."""
    status = report.status if report.status in _STATUSES else "review_required"
    return {
        "status": status,
        "proof_sha256": report.proof_sha256 if status == "proof_verified_mock" else None,
        "render_qa_pass": False,
        "video_qa_pass": False,
        "publish_ready": False,
    }
