"""편집부 연결: this driver-cut's real render + evaluation feeding resume_assembly.

Uses the actual STUDIO_ORG... evaluation payload printed by GitHub Actions
run 42028852096 (the idle-motion-fixed 90-frame driver pilot,
driver-review.mp4 sha256 9689623f10056a3da9de6dec85bb1806434461697cdc972842
aec635fd0975c1) -- not a fabricated fixture -- wired through the real
Task/Ledger objects into the unmodified, production-owned
EditingDept.resume_assembly (shorts_studio/studio_org/departments/editing.py,
owned by PR #97's fix/studio-org-integration-20261102).

resume_assembly's real-completion path requires film_pipeline.finish_film,
which only assembles the full narrated B-episode from episode-proof.json
shots. The driver pilot is a standalone test asset (its own
driver-pilot.json carries narration_alignment: "NOT_YET_APPLIED") that has
never gone through that assembler, so a real technical-QA PASS on it must
NOT be enough to mark the edit "need" task editorially complete -- doing so
would fabricate an acceptance the content never earned. This test proves
that gate holds for exactly this driver-cut's real data, i.e. that the real
feedback path is connected (not bypassed) rather than silently absent.
"""
from __future__ import annotations

from shorts_studio.studio_org.asset_registry import AssetRegistry
from shorts_studio.studio_org.departments.editing import EditingDept
from shorts_studio.studio_org.departments.management import ManagementDept
from shorts_studio.studio_org.ledger import TaskLedger

# Printed verbatim by job 127253034420 of run 42028852096 (see PR #100).
REAL_DRIVER_PILOT_EVALUATION = {
    "technical_status": "PASS_DRIVER_PILOT_INTEGRITY",
    "video": "/home/runner/work/_temp/complete/driver-review.mp4",
    "sha256": "9689623f10056a3da9de6dec85bb1806434461697cdc972842aec635fd0975c1",
    "native_frames_verified": 90,
    "lossless_decoded_exact": True,
    "is_final": False,
    "is_mock": False,
    "silent": True,
    "editorial_status": "REVIEW_REQUIRED",
    "narration_alignment": "NOT_YET_APPLIED",
    "human_first_view": "UNVERIFIED",
    "upload_authorized": False,
    "github_run_id": 42028852096,
}


def _build_real_driver_cut(ledger: TaskLedger):
    editing = EditingDept()
    management = ManagementDept(ledger, AssetRegistry())
    need = editing.request_cut({"shot": "driver_action_insert"}, management, ledger)
    render_task_id = need.predecessors[0]
    ledger.update(
        render_task_id, status="completed", is_mock=False,
        output={"is_mock": False, "github_run_id": 42028852096,
                "preview_only": False, "workflow_conclusion": "success"},
    )
    ledger.create(
        department="평가부", division="기술검수", predecessors=[render_task_id],
        requirements={"kind": "driver-pilot-integrity"},
        completion_criteria="90 actual frames, exact lossless pixels, no final/editorial claim",
        input_hash=REAL_DRIVER_PILOT_EVALUATION["sha256"],
        output=REAL_DRIVER_PILOT_EVALUATION, status="completed", is_mock=False,
    )
    return editing, need


def test_real_passing_driver_pilot_qa_does_not_fake_edit_completion(tmp_path):
    ledger = TaskLedger(tmp_path / "tasks.json")
    editing, need = _build_real_driver_cut(ledger)

    resumed = editing.resume_assembly(need.task_id, ledger)

    assert resumed.status == "blocked"
    assert resumed.failure_reason == "real cut requires MP4 assembly and QA receipt"
    assert resumed.output is None


def test_resume_assembly_is_idempotent_on_the_still_blocked_real_cut(tmp_path):
    ledger = TaskLedger(tmp_path / "tasks.json")
    editing, need = _build_real_driver_cut(ledger)

    first = editing.resume_assembly(need.task_id, ledger)
    second = editing.resume_assembly(need.task_id, ledger)

    assert first.status == second.status == "blocked"
    assert first.failure_reason == second.failure_reason
