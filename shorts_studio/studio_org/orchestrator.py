"""Runs ready 렌더부 tasks, then the 평가부 checks that follow them.

Only independent tasks run in parallel: two render tasks targeting different
resources run concurrently; two tasks that would touch the same
target_resource never run at the same time, because the second one fails to
acquire that resource's lock and is left for the next pass instead of racing
the first.
"""
from __future__ import annotations

import concurrent.futures

from .departments.evaluation import EvaluationDept
from .departments.render import RenderDept
from .ledger import TaskLedger
from .task import Task


class Orchestrator:
    def __init__(self, ledger: TaskLedger, render: RenderDept, evaluation: EvaluationDept,
                 *, mock: bool = True):
        self.ledger = ledger
        self.render = render
        self.evaluation = evaluation
        self.mock = mock

    def _is_ready(self, task: Task) -> bool:
        if task.department != "렌더부" or task.status != "assigned":
            return False
        return all(self.ledger.get(p).status == "completed" for p in task.predecessors)

    def _execute_locked(self, task_id: str) -> Task:
        task = self.ledger.get(task_id)
        lock = self.ledger.resource_lock(task.target_resource)
        if not lock.acquire(blocking=False):
            # Someone else is already handling this resource this pass.
            return self.ledger.get(task_id)
        try:
            current = self.ledger.get(task_id)
            if current.status != "assigned":
                return current  # picked up or finished elsewhere already
            return self.render.execute(current, self.ledger, mock=self.mock)
        finally:
            lock.release()

    def run_ready_renders(self, max_workers: int = 4) -> list[Task]:
        ready_ids = [t.task_id for t in self.ledger.all() if self._is_ready(t)]
        if not ready_ids:
            return []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(self._execute_locked, ready_ids))
        return results

    def run_pending_evaluations(self) -> list[Task]:
        created = []
        for task in self.ledger.all():
            if task.department != "렌더부" or task.status != "completed":
                continue
            if self.ledger.find_evaluation_for(task.task_id) is not None:
                continue
            created.append(self.evaluation.evaluate(task, task.requirements, self.ledger))
        return created

    def tick(self, max_workers: int = 4) -> dict[str, list[Task]]:
        """One scheduling pass: run whatever renders are ready, then evaluate
        whatever just finished. Call repeatedly (e.g. after recovery) rather
        than assuming one tick drains the whole graph."""
        rendered = self.run_ready_renders(max_workers=max_workers)
        evaluated = self.run_pending_evaluations()
        return {"rendered": rendered, "evaluated": evaluated}
