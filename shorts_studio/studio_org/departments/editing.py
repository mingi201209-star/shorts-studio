"""편집부: 컷편집 · 음향 · 자막.

Only 컷편집 (cut editing) is exercised by this round's scenario: requesting a
missing cut, and resuming assembly once it is resolved and evaluated. 음향
and 자막 are real divisions in the department structure but are not given
task-producing methods here, since nothing in this round's scope touches
audio or captions -- adding stub methods for them would be exactly the
"폴더만 나누기" the user asked not to do.
"""
from __future__ import annotations

from ..ledger import TaskLedger
from ..task import Task
from .management import ManagementDept


class EditingDept:
    def request_cut(self, requirement: dict, management: ManagementDept,
                     ledger: TaskLedger) -> Task:
        """컷편집 requests a cut; 관리부 decides whether it already exists or
        needs a new render. The 'need' task is blocked until that resolves."""
        resolved = management.request_or_create_render(requirement)
        return ledger.create(
            department="편집부", division="컷편집",
            requirements=requirement, predecessors=[resolved.task_id],
            input_hash=resolved.input_hash,
            completion_criteria="predecessor asset exists and (if rendered) passed evaluation",
            status="blocked",
            target_resource=f"edit:{requirement['shot']}",
        )

    def resume_assembly(self, need_task_id: str, ledger: TaskLedger) -> Task:
        """Re-check whether a blocked cut is now ready to assemble. Safe to
        call repeatedly: a task already completed or failed is returned as-is."""
        need = ledger.get(need_task_id)
        if need.is_terminal:
            return need
        predecessor = ledger.get(need.predecessors[0])
        if not predecessor.is_mock:
            # Real completion belongs to film_pipeline.finish_film, which emits
            # an actual MP4 and full QA receipt. Dependency resolution is not assembly.
            return ledger.update(
                need.task_id, status="blocked",
                failure_reason="real cut requires MP4 assembly and QA receipt",
            )
        if predecessor.department == "관리부":
            if predecessor.status == "completed":
                return ledger.update(
                    need.task_id, status="completed",
                    output={"assembled_from": predecessor.task_id, "is_mock": False},
                )
            return need
        if predecessor.department == "렌더부":
            if predecessor.status == "failed":
                return ledger.update(
                    need.task_id, status="failed",
                    failure_reason=f"render task {predecessor.task_id} failed: "
                                   f"{predecessor.failure_reason}",
                )
            evaluation = ledger.find_evaluation_for(predecessor.task_id)
            if evaluation is None:
                return need  # still waiting on 평가부
            if evaluation.status == "failed":
                return ledger.update(
                    need.task_id, status="failed",
                    failure_reason=f"evaluation {evaluation.task_id} failed: "
                                   f"{evaluation.failure_reason}",
                )
            return ledger.update(
                need.task_id, status="completed",
                output={
                    "assembled_from": predecessor.task_id,
                    "evaluated_by": evaluation.task_id,
                    "is_mock": predecessor.is_mock,
                },
                is_mock=predecessor.is_mock,
            )
        return need
