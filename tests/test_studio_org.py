"""Validates the department/task-graph structure with mock-only work.

No Blender, no GitHub Actions dispatch, no publishing -- per the explicit
instruction that the first validation must be a mock task with no real
render. These tests assert that a mock result is never recorded in a way
that could be mistaken for a real rendered-video success.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shorts_studio.studio_org.asset_registry import AssetRegistry
from shorts_studio.studio_org.departments.editing import EditingDept
from shorts_studio.studio_org.departments.evaluation import EvaluationDept, MOCK_TECHNICAL_QA_STATUS
from shorts_studio.studio_org.departments.management import ManagementDept
from shorts_studio.studio_org.departments.render import RenderDept
from shorts_studio.studio_org.ledger import TaskLedger
from shorts_studio.studio_org.orchestrator import Orchestrator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples/experiments/curious-mechanics-progressive-B.json"
REAL_TECHNICAL_QA_PASS = "PASS_NATIVE_ORIGINAL_SHARD"  # must never appear in a mock output

MISSING_SHOT_REQUIREMENT = {
    "shot": "driver_reaction_closeup",
    "narration_tag": "a distracted driver notices the sound and vibration",
}


def _status_values(d: dict):
    for k, v in d.items():
        if k == "status":
            yield v
        if isinstance(v, dict):
            yield from _status_values(v)


def _no_real_success_claim(ledger: TaskLedger) -> None:
    """Fails if any task output could be mistaken for a real rendered/
    published success rather than a mock."""
    for task in ledger.all():
        if not task.output:
            continue
        blob = json.dumps(task.output)
        assert REAL_TECHNICAL_QA_PASS not in blob, (task.task_id, task.output)
        if "PASS" in _status_values(task.output):
            assert task.is_mock, ("a non-mock PASS was recorded", task.task_id, task.output)


@pytest.fixture
def registry() -> AssetRegistry:
    return AssetRegistry.from_manifest(MANIFEST)


@pytest.fixture
def ledger(tmp_path) -> TaskLedger:
    return TaskLedger(tmp_path / "tasks.json")


@pytest.fixture
def management(ledger, registry) -> ManagementDept:
    return ManagementDept(ledger, registry, max_attempts=3)


@pytest.fixture
def editing() -> EditingDept:
    return EditingDept()


@pytest.fixture
def render_dept() -> RenderDept:
    return RenderDept()


@pytest.fixture
def evaluation_dept() -> EvaluationDept:
    return EvaluationDept()


@pytest.fixture
def orchestrator(ledger, render_dept, evaluation_dept) -> Orchestrator:
    return Orchestrator(ledger, render_dept, evaluation_dept, mock=True)


# ---------------------------------------------------------------------------
# 1. The scenario the user asked for, end to end, mock-only.
# ---------------------------------------------------------------------------

def test_driver_response_cut_request_flow_is_mock_only(
    ledger, registry, management, editing, orchestrator,
):
    # The manifest genuinely has no such shot/style -- this is a real fact
    # about the production (see curious_mechanics_asset_inventory.py's
    # finding that no human/driver asset exists), not a scripted mock.
    assert registry.find_clip(MISSING_SHOT_REQUIREMENT["shot"]) is None

    need = editing.request_cut(MISSING_SHOT_REQUIREMENT, management, ledger)
    assert need.status == "blocked"
    render_task = ledger.get(need.predecessors[0])
    assert render_task.department == "렌더부" and render_task.status == "assigned"

    result = orchestrator.tick()
    assert len(result["rendered"]) == 1
    assert ledger.get(render_task.task_id).status == "completed"
    assert ledger.get(render_task.task_id).is_mock is True
    assert len(result["evaluated"]) == 1
    evaluation = result["evaluated"][0]
    assert evaluation.status == "completed"
    assert evaluation.output["technical_qa"]["status"] == MOCK_TECHNICAL_QA_STATUS
    assert evaluation.output["performance_analysis"]["status"] == "UNVERIFIED"

    resumed = editing.resume_assembly(need.task_id, ledger)
    assert resumed.status == "completed"
    assert resumed.is_mock is True
    assert resumed.output["is_mock"] is True

    _no_real_success_claim(ledger)


def test_evaluation_separates_technical_content_and_performance(
    ledger, registry, management, editing, orchestrator,
):
    editing.request_cut(MISSING_SHOT_REQUIREMENT, management, ledger)
    result = orchestrator.tick()
    evaluation = result["evaluated"][0]
    out = evaluation.output
    assert set(out) == {"technical_qa", "content_screen_match", "performance_analysis"}
    # Performance is always reported unverified: this project never publishes.
    assert out["performance_analysis"] == {
        "status": "UNVERIFIED",
        "reason": "no publish/performance data available (no public upload performed)",
    }


# ---------------------------------------------------------------------------
# 2. Duplicate request blocking.
# ---------------------------------------------------------------------------

def test_duplicate_cut_request_does_not_create_second_render_task(
    ledger, management, editing,
):
    need_a = editing.request_cut(MISSING_SHOT_REQUIREMENT, management, ledger)
    need_b = editing.request_cut(MISSING_SHOT_REQUIREMENT, management, ledger)

    assert need_a.predecessors[0] == need_b.predecessors[0]
    render_tasks = [t for t in ledger.all() if t.department == "렌더부"]
    assert len(render_tasks) == 1


# ---------------------------------------------------------------------------
# 3. Interruption + recovery across a simulated process restart.
# ---------------------------------------------------------------------------

def test_interrupted_render_task_recovers_without_duplicate(
    tmp_path, registry, editing,
):
    path = tmp_path / "tasks.json"
    ledger_a = TaskLedger(path)
    management_a = ManagementDept(ledger_a, registry, max_attempts=3)
    need = editing.request_cut(MISSING_SHOT_REQUIREMENT, management_a, ledger_a)
    render_task_id = need.predecessors[0]

    # Simulate a worker having picked the task up and the process dying
    # mid-render, before persisting completion.
    ledger_a.update(render_task_id, status="running")

    # Simulate a process restart: a fresh TaskLedger loading the same file.
    ledger_b = TaskLedger(path)
    assert ledger_b.get(render_task_id).status == "running"

    management_b = ManagementDept(ledger_b, registry, max_attempts=3)
    recovered = management_b.recover_interrupted()
    assert [t.task_id for t in recovered] == [render_task_id]
    assert ledger_b.get(render_task_id).status == "assigned"
    assert ledger_b.get(render_task_id).attempt_count == 1

    # Recovery must not have spawned a second render task for the same target.
    render_tasks = [t for t in ledger_b.all() if t.department == "렌더부"]
    assert len(render_tasks) == 1

    render_dept, evaluation_dept = RenderDept(), EvaluationDept()
    orchestrator = Orchestrator(ledger_b, render_dept, evaluation_dept, mock=True)
    orchestrator.tick()
    resumed = editing.resume_assembly(need.task_id, ledger_b)
    assert resumed.status == "completed"
    assert resumed.is_mock is True


# ---------------------------------------------------------------------------
# 4. Retry cap stops infinite retry.
# ---------------------------------------------------------------------------

def test_max_attempts_cap_stops_infinite_retry(ledger, registry, render_dept):
    management = ManagementDept(ledger, registry, max_attempts=2)
    render_task = management.request_or_create_render(MISSING_SHOT_REQUIREMENT)

    render_dept.simulate_failure(render_task, ledger, "mock failure 1")
    after_first = management.retry_or_finalize(render_task.task_id, "mock failure 1")
    assert after_first.status == "assigned"
    assert after_first.attempt_count == 1

    render_dept.simulate_failure(after_first, ledger, "mock failure 2")
    after_second = management.retry_or_finalize(render_task.task_id, "mock failure 2")
    assert after_second.status == "failed"
    assert after_second.attempt_count == 2
    assert "max_attempts" in after_second.failure_reason

    orchestrator = Orchestrator(ledger, render_dept, EvaluationDept(), mock=True)
    # A permanently failed task is never picked up again.
    assert orchestrator.run_ready_renders() == []
    assert ledger.get(render_task.task_id).status == "failed"


# ---------------------------------------------------------------------------
# 5. Independent tasks run in parallel; same-resource tasks are serialized.
# ---------------------------------------------------------------------------

def test_independent_render_tasks_run_in_one_pass(ledger, registry, orchestrator):
    management = ManagementDept(ledger, registry)
    task_a = management.request_or_create_render({"shot": "driver_reaction_closeup_a"})
    task_b = management.request_or_create_render({"shot": "driver_reaction_closeup_b"})
    assert task_a.target_resource != task_b.target_resource

    rendered = orchestrator.run_ready_renders(max_workers=4)
    assert {t.task_id for t in rendered} == {task_a.task_id, task_b.task_id}
    assert all(ledger.get(t.task_id).status == "completed" for t in rendered)


def test_same_resource_task_is_not_executed_while_lock_is_held(ledger, registry):
    management = ManagementDept(ledger, registry)
    render_task = management.request_or_create_render(MISSING_SHOT_REQUIREMENT)
    render_dept, evaluation_dept = RenderDept(), EvaluationDept()
    orchestrator = Orchestrator(ledger, render_dept, evaluation_dept, mock=True)

    lock = ledger.resource_lock(render_task.target_resource)
    lock.acquire()
    try:
        result = orchestrator._execute_locked(render_task.task_id)
    finally:
        lock.release()

    # The lock was held, so the task must still be untouched (never raced).
    assert result.status == "assigned"
    assert ledger.get(render_task.task_id).status == "assigned"

    # Now that the lock is free, the same task can actually run.
    final = orchestrator._execute_locked(render_task.task_id)
    assert final.status == "completed"
