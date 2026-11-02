import pytest

from shorts_studio.studio_org.departments import render
from shorts_studio.studio_org.ledger import TaskLedger


def setup_task(tmp_path):
    ledger = TaskLedger(tmp_path / "tasks.json")
    task = ledger.create(department="렌더부", division="렌더실행",
                         requirements={"frame_list": [1]}, completion_criteria="QA",
                         status="assigned", target_resource="preview")
    return ledger, task


def test_timeout_keeps_run_id_and_reuses_it_without_dispatch(tmp_path, monkeypatch):
    ledger, task = setup_task(tmp_path)
    calls = []
    monkeypatch.setattr(render, "dispatch_real_render",
                        lambda *args: calls.append(args) or "123")
    def timeout(*args):
        persisted = TaskLedger(tmp_path / "tasks.json").get(task.task_id)
        assert persisted.output["github_run_id"] == "123"
        raise render.RealRenderDispatchError("timeout")
    monkeypatch.setattr(render, "wait_for_run", timeout)
    dept = render.RenderDept()
    with pytest.raises(render.RealRenderDispatchError):
        dept.execute(task, ledger, mock=False, ref="branch")
    assert task.status == "blocked"
    monkeypatch.setattr(render, "wait_for_run", lambda *a: {"conclusion": "success"})
    monkeypatch.setattr(render, "fetch_eval_result", lambda *a: {"ok": True})
    dept.execute(task, ledger, mock=False, ref="branch")
    assert len(calls) == 1
    assert task.status == "completed"


def test_unknown_dispatch_outcome_blocks_resubmission(tmp_path, monkeypatch):
    ledger, task = setup_task(tmp_path)
    def unknown(*args):
        raise render.RealRenderDispatchError("connection lost")
    monkeypatch.setattr(render, "dispatch_real_render", unknown)
    dept = render.RenderDept()
    with pytest.raises(render.RealRenderDispatchError):
        dept.execute(task, ledger, mock=False, ref="branch")
    monkeypatch.setattr(render, "dispatch_real_render",
                        lambda *args: pytest.fail("must not dispatch again"))
    with pytest.raises(render.RealRenderDispatchError, match="outcome unknown"):
        dept.execute(task, ledger, mock=False, ref="branch")
    assert task.status == "blocked"


def test_failed_ci_never_marks_render_completed(tmp_path, monkeypatch):
    ledger, task = setup_task(tmp_path)
    monkeypatch.setattr(render, "dispatch_real_render", lambda *a: "123")
    monkeypatch.setattr(render, "wait_for_run", lambda *a: {"conclusion": "failure"})
    monkeypatch.setattr(render, "fetch_eval_result",
                        lambda *a: pytest.fail("failed CI is not a QA pass"))
    render.RenderDept().execute(task, ledger, mock=False, ref="branch")
    assert task.status == "failed"


def test_missing_ref_does_not_leave_running_task(tmp_path):
    ledger, task = setup_task(tmp_path)
    with pytest.raises(ValueError):
        render.RenderDept().execute(task, ledger, mock=False)
    assert task.status == "assigned"


def test_successful_workflow_with_failed_qa_is_not_complete(tmp_path, monkeypatch):
    ledger, task = setup_task(tmp_path)
    monkeypatch.setattr(render, "dispatch_real_render", lambda *a: "123")
    monkeypatch.setattr(render, "wait_for_run", lambda *a: {"conclusion": "success"})
    monkeypatch.setattr(render, "fetch_eval_result", lambda *a: {"ok": False})
    dept = render.RenderDept()
    dept.execute(task, ledger, mock=False, ref="branch")
    assert task.status == "failed"
    monkeypatch.setattr(render, "dispatch_real_render",
                        lambda *args: pytest.fail("terminal task must not rerender"))
    assert dept.execute(task, ledger, mock=False, ref="branch").status == "failed"
