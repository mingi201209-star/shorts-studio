"""관리부: 작업통제 · 자원관리 · 기록복구.

This is where the rules the user asked for actually live: never assign the
same render twice for one resource, never let two tasks write the same
output at once (the lock itself lives on TaskLedger; this module is what
decides *when* to take it), and never retry a failed task forever.
"""
from __future__ import annotations

from shorts_studio.factory.planner import fingerprint

from ..asset_registry import AssetRegistry
from ..ledger import TaskLedger
from ..task import Task


class ManagementDept:
    def __init__(self, ledger: TaskLedger, registry: AssetRegistry, max_attempts: int = 3):
        self.ledger = ledger
        self.registry = registry
        self.max_attempts = max_attempts

    def request_or_create_render(self, requirement: dict) -> Task:
        """자원관리 + 작업통제: find an existing clip first; only assign 렌더부
        if nothing covers this requirement, and never assign it twice."""
        target = requirement["shot"]
        existing = self.registry.find_clip(target)
        if existing is not None:
            return self.ledger.create(
                department="관리부", division="자원관리",
                requirements=requirement, predecessors=[],
                input_hash=fingerprint(requirement), output=dict(existing),
                completion_criteria="existing file located and SHA256 verified",
                status="completed", target_resource=target,
            )
        duplicate = self.ledger.find_active_by_target(target)
        if duplicate is not None:
            return duplicate
        return self.ledger.create(
            department="렌더부", division="렌더실행",
            requirements=requirement, predecessors=[],
            input_hash=fingerprint(requirement),
            completion_criteria="a rendered clip exists and has passed evaluation",
            status="assigned", target_resource=target, max_attempts=self.max_attempts,
        )

    def retry_or_finalize(self, task_id: str, failure_reason: str) -> Task:
        """작업통제: a render task failed -- requeue it under the retry cap, or
        finalize it as permanently failed. Never silently retries forever."""
        task = self.ledger.get(task_id)
        if task.attempt_count + 1 >= task.max_attempts:
            return self.ledger.update(
                task_id, status="failed", attempt_count=task.attempt_count + 1,
                failure_reason=f"max_attempts ({task.max_attempts}) exceeded: {failure_reason}",
            )
        return self.ledger.update(
            task_id, status="assigned", attempt_count=task.attempt_count + 1,
            failure_reason=failure_reason,
        )

    def recover_interrupted(self) -> list[Task]:
        """기록복구: resume tasks stuck mid-flight (e.g. the process restarted
        while they were 'running') without creating a duplicate task, and
        without exceeding the same retry cap used for ordinary failures."""
        recovered = []
        for task in self.ledger.all():
            if task.status != "running":
                continue
            if task.attempt_count >= task.max_attempts:
                self.ledger.update(
                    task.task_id, status="failed",
                    failure_reason="max_attempts exceeded while recovering an interrupted task",
                )
                continue
            recovered.append(self.ledger.update(
                task.task_id, status="assigned", attempt_count=task.attempt_count + 1,
                failure_reason="recovered after interruption",
            ))
        return recovered
