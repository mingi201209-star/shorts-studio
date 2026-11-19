"""The one task record shared by all five departments.

Every unit of work in the studio -- a script beat, a render job, a cut
request, a QA check -- is the same Task shape, carrying who owns it
(department + division), what it depends on, what it needs, what it produced,
and why it failed if it did. Departments are just functions that read and
write Task records through a TaskLedger; there is no separate per-department
data model to keep in sync.
"""
from __future__ import annotations

import dataclasses
import time
import uuid
from typing import Any, Literal

Status = Literal["pending", "assigned", "running", "blocked", "completed", "failed"]

# Department -> its real divisions. A Task must declare one of each; this is
# the only place the five-department structure is enforced, so adding or
# renaming a division never requires touching every department module.
DEPARTMENTS: dict[str, tuple[str, ...]] = {
    "기획부": ("소재조사", "대본구성", "장면설계"),
    "렌더부": ("자산", "동작", "촬영", "렌더실행"),
    "편집부": ("컷편집", "음향", "자막"),
    "평가부": ("기술검수", "대본화면일치", "성과분석"),
    "관리부": ("작업통제", "자원관리", "기록복구"),
}

TERMINAL_STATUSES: tuple[Status, ...] = ("completed", "failed")


def new_task_id() -> str:
    return f"T-{uuid.uuid4().hex[:10]}"


@dataclasses.dataclass
class Task:
    task_id: str
    department: str
    division: str
    requirements: dict[str, Any]
    completion_criteria: str
    predecessors: list[str] = dataclasses.field(default_factory=list)
    input_hash: str | None = None
    output: dict[str, Any] | None = None
    status: Status = "pending"
    failure_reason: str | None = None
    # Not in the user's original field list, but required to satisfy "prevent
    # duplicate assignment / infinite retry" without inventing a second record
    # type: attempt/retry bookkeeping and the dedup/lock key live on the task.
    attempt_count: int = 0
    max_attempts: int = 3
    target_resource: str | None = None
    is_mock: bool = False
    created_at: float = dataclasses.field(default_factory=time.time)
    updated_at: float = dataclasses.field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.department not in DEPARTMENTS:
            raise ValueError(f"unknown department: {self.department!r}")
        if self.division not in DEPARTMENTS[self.department]:
            raise ValueError(
                f"{self.division!r} is not a division of {self.department!r}; "
                f"expected one of {DEPARTMENTS[self.department]}"
            )

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(**data)
