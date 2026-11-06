import hashlib

import pytest

from shorts_studio.studio_org.asset_registry import AssetRegistry
from shorts_studio.studio_org.departments.editing import EditingDept
from shorts_studio.studio_org.departments.management import ManagementDept
from shorts_studio.studio_org.ledger import TaskLedger


def test_planned_role_is_not_a_rendered_clip():
    registry = AssetRegistry(known_roles={"driver_response"})
    ledger = TaskLedger()
    need = EditingDept().request_cut(
        {"shot": "driver_response"}, ManagementDept(ledger, registry), ledger)
    assert registry.find_clip("driver_response") is None
    assert ledger.get(need.predecessors[0]).department == "렌더부"
    assert need.status == "blocked"


def test_clip_digest_is_checked_again_on_reuse(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture bytes, not a production QA pass")
    registry = AssetRegistry()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    registry.register_clip("driver_response", path, digest)
    assert registry.find_clip("driver_response")["sha256"] == digest
    path.write_bytes(b"changed")
    assert registry.find_clip("driver_response") is None
    with pytest.raises(ValueError, match="SHA256"):
        registry.register_clip("driver_response", path, digest)


def test_available_file_does_not_claim_assembled_video(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture bytes")
    registry = AssetRegistry()
    registry.register_clip("driver_response", path, hashlib.sha256(path.read_bytes()).hexdigest())
    ledger = TaskLedger()
    editing = EditingDept()
    need = editing.request_cut(
        {"shot": "driver_response"}, ManagementDept(ledger, registry), ledger)
    assert ledger.get(need.predecessors[0]).status == "completed"
    resumed = editing.resume_assembly(need.task_id, ledger)
    assert resumed.status == "blocked"
    assert not resumed.output
