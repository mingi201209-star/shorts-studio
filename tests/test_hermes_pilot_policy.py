"""Local-only admission gates do not loosen the Controller's mock policy."""

from dataclasses import replace

import pytest

from shorts_studio.asset_factory.integrations.hermes_pilot.policy import (
    ResourceView,
    assess_ingress,
)

GIB = 1024**3
MIB = 1024**2


@pytest.fixture
def ok():
    return ResourceView(2*GIB, 0.50, 0, 0, 0, 0)


def test_resource_thresholds_and_unknown_metrics_fail_closed(ok):
    assert assess_ingress(ok) == "allow"
    assert assess_ingress(replace(ok, mem_available_bytes=GIB-1)) == "warn_memory"
    assert assess_ingress(replace(ok, mem_available_bytes=512*MIB)) == "warn_memory"
    assert assess_ingress(replace(ok, mem_available_bytes=512*MIB-1)) == "blocked_memory"
    assert assess_ingress(replace(ok, disk_free_ratio=0.15)) == "allow"
    assert assess_ingress(replace(ok, disk_free_ratio=0.14999)) == "blocked_disk"
    assert assess_ingress(replace(ok, pending_proposals=20)) == "blocked_capacity"
    assert assess_ingress(replace(ok, accepted_this_session=3)) == "blocked_capacity"
    assert assess_ingress(replace(ok, active_mock_workers=1)) == "blocked_worker"
    assert assess_ingress(replace(ok, codex_processes=1)) == "blocked_worker"
    for changed in [
        {"mem_available_bytes": -1}, {"mem_available_bytes": None},
        {"disk_free_ratio": float("nan")}, {"disk_free_ratio": float("inf")},
        {"disk_free_ratio": -0.01}, {"disk_free_ratio": 1.01},
        {"pending_proposals": -1}, {"accepted_this_session": None},
        {"active_mock_workers": -1}, {"codex_processes": 1.5},
    ]:
        with pytest.raises(ValueError):
            assess_ingress(replace(ok, **changed))
