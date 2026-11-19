import json

import pytest

from shorts_studio.studio_org.driver_review import inspect_pilot, record_review
from shorts_studio.studio_org.ledger import TaskLedger


def test_changed_renderer_cannot_receive_pilot_integrity_pass(tmp_path):
    renderer = tmp_path / "renderer.py"
    renderer.write_text("changed source")
    (tmp_path / "driver-pilot.json").write_text(
        json.dumps({"renderer_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="source changed"):
        inspect_pilot(tmp_path, renderer)


def test_pilot_review_cannot_complete_a_final_cut_task(tmp_path):
    ledger = TaskLedger()
    task = ledger.create(department="렌더부", division="렌더실행",
                         requirements={"kind": "final-cut"}, completion_criteria="real cut",
                         status="blocked", output={"github_run_id": 123})
    with pytest.raises(AssertionError):
        record_review(tmp_path, tmp_path / "renderer.py", ledger, task.task_id)
    assert task.status == "blocked"
    assert ledger.find_evaluation_for(task.task_id) is None
