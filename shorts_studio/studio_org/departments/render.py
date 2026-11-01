"""렌더부: 자산 · 동작 · 촬영 · 렌더실행.

Only the mock path is implemented and exercised in this round, as required:
"첫 검증은 실제 렌더 없는 모의 작업으로 해". The mock output is tagged
is_mock=True everywhere and its renderer/status strings are deliberately
different from the real pipeline's (see shorts_studio.factory.
curious_mechanics_native_qa's actual "PASS_NATIVE_ORIGINAL_SHARD"), so a mock
result can never be mistaken for a real render success downstream.

The real path is a documented interface, not a working implementation: it
would dispatch the existing benchmarks/road_safety/render_curious_mechanics.py
pipeline through the .github/workflows/curious-mechanics-b-causal-shot.yml
GitHub Actions workflow (free standard runners only) and poll for its
artifact, exactly as this project already does by hand. That dispatch/poll
loop is not implemented here.
"""
from __future__ import annotations

from ..ledger import TaskLedger
from ..task import Task

MOCK_RENDERER_TAG = "MOCK_NO_BLENDER"


class RealRenderNotImplemented(NotImplementedError):
    pass


class RenderDept:
    def execute(self, task: Task, ledger: TaskLedger, *, mock: bool) -> Task:
        if task.department != "렌더부":
            raise ValueError(f"not a render-dept task: {task.task_id}")
        ledger.update(task.task_id, status="running")
        if not mock:
            raise RealRenderNotImplemented(
                "real render dispatch (GitHub Actions workflow_dispatch against "
                "curious-mechanics-b-causal-shot.yml) is not implemented in this "
                "minimal structure; only mock=True is supported"
            )
        output = {
            "is_mock": True,
            "clip_ref": f"mock://{task.target_resource}/{task.task_id}",
            "frames": 0,
            "renderer": MOCK_RENDERER_TAG,
        }
        return ledger.update(task.task_id, status="completed", output=output, is_mock=True)

    def simulate_failure(self, task: Task, ledger: TaskLedger, reason: str) -> Task:
        """Test/demo hook only: forces a render task to fail, for exercising
        the retry-cap and recovery paths without a real renderer."""
        ledger.update(task.task_id, status="running")
        return ledger.update(task.task_id, status="failed", failure_reason=reason)
