"""렌더부: 자산 · 동작 · 촬영 · 렌더실행.

mock=True (의무: "첫 검증은 실제 렌더 없는 모의 작업으로 해") is unchanged from
the first round: no Blender, no network, tagged is_mock=True with a renderer
string distinct from the real pipeline's.

mock=False is now a real, working connection: it dispatches the existing,
unmodified benchmarks/road_safety/render_curious_mechanics.py through a new
standalone GitHub Actions workflow
(.github/workflows/studio-org-render-task.yml), on a free GitHub-hosted
runner only, in the already-established --preview mode (cheap: 7 Cycles
samples, 450x800 -- never the 32-sample/1080x1920 production contract, and
it never touches the approved 30-shard B asset bed). That workflow then runs
the real, unmodified curious_mechanics_native_qa.verify() and prints its
verdict; this module relays that verdict rather than recomputing it, because
this sandbox cannot download GitHub Actions artifacts (a 403 from the
blob-storage redirect, established earlier in this project), so the only
honest "real" technical QA is the one that already ran server-side, inside
the same job that has the actual rendered files and Blender.

촬영/자산/동작 (asset prep, motion, cinematography beyond the one
render_curious_mechanics.py call) are not separately implemented; 렌더실행 is
the only division with a working method here.
"""
from __future__ import annotations

import json
import re
import subprocess
import time

from ..ledger import TaskLedger
from ..task import Task

MOCK_RENDERER_TAG = "MOCK_NO_BLENDER"
REAL_RENDER_WORKFLOW = "studio-org-render-task.yml"
REAL_RENDER_TIMEOUT_SECONDS = 900
REAL_RENDER_POLL_SECONDS = 15


class RealRenderDispatchError(RuntimeError):
    pass


def dispatch_real_render(frame_list: list[int], request_tag: str, ref: str) -> str:
    """Triggers studio-org-render-task.yml via the `gh` CLI and returns the
    new run's numeric id, parsed from the URL `gh workflow run` prints."""
    csv = ",".join(str(f) for f in frame_list)
    proc = subprocess.run(
        ["gh", "workflow", "run", REAL_RENDER_WORKFLOW, "--ref", ref,
         "-f", f"frame_list={csv}", "-f", f"request_tag={request_tag}"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RealRenderDispatchError(proc.stderr.strip() or proc.stdout.strip())
    match = re.search(r"/actions/runs/(\d+)", proc.stdout)
    if not match:
        raise RealRenderDispatchError(f"no run id in `gh workflow run` output: {proc.stdout!r}")
    return match.group(1)


def wait_for_run(run_id: str, timeout_seconds: int = REAL_RENDER_TIMEOUT_SECONDS,
                  poll_seconds: int = REAL_RENDER_POLL_SECONDS) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while True:
        proc = subprocess.run(
            ["gh", "run", "view", run_id, "--json", "status,conclusion"],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0:
            raise RealRenderDispatchError(proc.stderr.strip())
        state = json.loads(proc.stdout)
        if state["status"] == "completed":
            return state
        if time.monotonic() > deadline:
            raise RealRenderDispatchError(f"run {run_id} did not complete within {timeout_seconds}s")
        time.sleep(poll_seconds)


def fetch_eval_result(run_id: str, request_tag: str) -> dict:
    """Pulls the one STUDIO_ORG_EVAL_RESULT line out of the job log. Not an
    artifact download (which this sandbox cannot do); job logs are plain text
    and always reachable."""
    proc = subprocess.run(["gh", "run", "view", run_id, "--log"],
                           capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RealRenderDispatchError(proc.stderr.strip())
    marker = f"STUDIO_ORG_EVAL_RESULT {request_tag} "
    for line in proc.stdout.splitlines():
        idx = line.find(marker)
        if idx != -1:
            return json.loads(line[idx + len(marker):])
    raise RealRenderDispatchError(f"no STUDIO_ORG_EVAL_RESULT line found for tag {request_tag}")


class RenderDept:
    def execute(self, task: Task, ledger: TaskLedger, *, mock: bool, ref: str | None = None) -> Task:
        if task.department != "렌더부":
            raise ValueError(f"not a render-dept task: {task.task_id}")
        ledger.update(task.task_id, status="running")
        if mock:
            output = {
                "is_mock": True,
                "clip_ref": f"mock://{task.target_resource}/{task.task_id}",
                "frames": 0,
                "renderer": MOCK_RENDERER_TAG,
            }
            return ledger.update(task.task_id, status="completed", output=output, is_mock=True)
        return self._execute_real(task, ledger, ref)

    def _execute_real(self, task: Task, ledger: TaskLedger, ref: str | None) -> Task:
        if not ref:
            raise ValueError("real render dispatch requires ref (the branch to run against)")
        frame_list = task.requirements.get("frame_list")
        if not frame_list:
            raise ValueError("real render requires requirements['frame_list']")
        run_id = dispatch_real_render(frame_list, task.task_id, ref)
        state = wait_for_run(run_id)
        eval_result = fetch_eval_result(run_id, task.task_id)
        output = {
            "is_mock": False,
            "github_run_id": run_id,
            "workflow_conclusion": state["conclusion"],
            "preview_only": True,
            "frame_list": frame_list,
            "real_technical_qa": eval_result,
        }
        return ledger.update(task.task_id, status="completed", output=output, is_mock=False)

    def simulate_failure(self, task: Task, ledger: TaskLedger, reason: str) -> Task:
        """Test/demo hook only: forces a render task to fail, for exercising
        the retry-cap and recovery paths without a real renderer."""
        ledger.update(task.task_id, status="running")
        return ledger.update(task.task_id, status="failed", failure_reason=reason)
