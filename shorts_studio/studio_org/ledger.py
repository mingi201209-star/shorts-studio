"""Durable, lockable store of Task records.

This is the 관리부/작업통제 substrate: every department reads and writes
through one TaskLedger so that duplicate assignment, concurrent writes to the
same output, and interrupted work are handled in one place instead of five.

Persistence is a single JSON file written atomically (temp file + rename), so
a crashed process can be recovered by pointing a fresh TaskLedger at the same
path -- this is how the interruption/recovery test simulates a restart
without actually killing a process.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from .task import Task, new_task_id


class DuplicateTaskError(RuntimeError):
    pass


class TaskLedger:
    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path is not None else None
        self._lock = threading.RLock()
        self._resource_locks: dict[str, threading.Lock] = {}
        self._resource_locks_guard = threading.Lock()
        self._tasks: dict[str, Task] = {}
        if self._path is not None and self._path.is_file():
            self._load()

    # -- persistence -------------------------------------------------
    def _load(self) -> None:
        raw = json.loads(self._path.read_text(encoding="utf8"))
        self._tasks = {tid: Task.from_dict(t) for tid, t in raw.items()}

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {tid: t.to_dict() for tid, t in self._tasks.items()}
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=".tasks-", suffix=".json.tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            os.replace(tmp_name, self._path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)

    # -- task CRUD -----------------------------------------------------
    def create(self, *, department: str, division: str, requirements: dict[str, Any],
               completion_criteria: str, predecessors: list[str] | None = None,
               input_hash: str | None = None, output: dict[str, Any] | None = None,
               status: str = "pending", failure_reason: str | None = None,
               target_resource: str | None = None,
               max_attempts: int = 3, is_mock: bool = False,
               task_id: str | None = None) -> Task:
        with self._lock:
            for pred in predecessors or []:
                if pred not in self._tasks:
                    raise ValueError(f"unknown predecessor task: {pred}")
            tid = task_id or new_task_id()
            if tid in self._tasks:
                raise DuplicateTaskError(tid)
            task = Task(
                task_id=tid, department=department, division=division,
                requirements=requirements, completion_criteria=completion_criteria,
                predecessors=list(predecessors or []), input_hash=input_hash,
                output=output, status=status, failure_reason=failure_reason,
                target_resource=target_resource,
                max_attempts=max_attempts, is_mock=is_mock,
            )
            self._tasks[tid] = task
            self._save()
            return task

    def get(self, task_id: str) -> Task:
        with self._lock:
            return self._tasks[task_id]

    def update(self, task_id: str, **fields: Any) -> Task:
        with self._lock:
            task = self._tasks[task_id]
            for key, value in fields.items():
                if not hasattr(task, key):
                    raise ValueError(f"Task has no field {key!r}")
                setattr(task, key, value)
            task.updated_at = time.time()
            self._save()
            return task

    def all(self) -> list[Task]:
        with self._lock:
            return list(self._tasks.values())

    # -- the queries departments actually need -------------------------
    def find_active_by_target(self, target_resource: str) -> Task | None:
        """작업통제: the task already in flight for this resource, if any.

        'Active' is anything not yet terminal -- used to stop a second
        request for the same cut from spawning a second render task.
        """
        with self._lock:
            for task in self._tasks.values():
                if task.target_resource == target_resource and not task.is_terminal:
                    return task
            return None

    def find_evaluation_for(self, predecessor_task_id: str) -> Task | None:
        """The most recent 평가부 task that evaluated this task, if any."""
        with self._lock:
            matches = [
                t for t in self._tasks.values()
                if t.department == "평가부" and predecessor_task_id in t.predecessors
            ]
            return max(matches, key=lambda t: t.created_at) if matches else None

    def resource_lock(self, target_resource: str) -> threading.Lock:
        """One lock per target resource, so two tasks never write the same
        output at once. Never acquired for a None resource (nothing shared)."""
        with self._resource_locks_guard:
            if target_resource not in self._resource_locks:
                self._resource_locks[target_resource] = threading.Lock()
            return self._resource_locks[target_resource]
