from dataclasses import FrozenInstanceError, replace

import pytest

from shorts_studio.asset_factory.controller.contracts import ArtifactReceipt, Claim, JobSpec


def spec(**changes):
    fields = {"job_id": "job", "asset_id": "asset", "asset_version": "v1",
              "source_sha": "a" * 40, "input_digest": "b" * 64, "stage": "queued",
              "worker_kind": "mock", "payload_json": "{}"}
    return JobSpec(**(fields | changes))


def test_bad_digests_and_payload_rejected():
    for changes in (
        {"source_sha": "a" * 39}, {"source_sha": "A" * 40},
        {"input_digest": "B" * 64}, {"input_digest": "g" * 64},
        {"payload_json": "{"}, {"payload_json": '{"x": NaN}'},
        {"worker_kind": "renderer"}, {"budget_usd": "-1"},
        {"budget_usd": "NaN"}, {"budget_usd": "Infinity"},
        {"max_attempts": 0}, {"max_attempts": True}, {"job_id": ""},
    ):
        with pytest.raises(ValueError):
            spec(**changes)
    receipt = ArtifactReceipt("job", "a" * 40, "b" * 64, "c" * 64, "sha256/blob", 1)
    for path in ("../blob", "/blob", "safe/../blob", r"..\blob", ""):
        with pytest.raises(ValueError):
            replace(receipt, relative_path=path)
    for changes in ({"byte_count": -1}, {"artifact_sha256": "C" * 64}):
        with pytest.raises(ValueError):
            replace(receipt, **changes)
    claim = Claim("job", "a" * 40, "b" * 64, "owner", 1, 1, 100.0)
    for changes in ({"owner": ""}, {"attempt": 0}, {"fencing_token": 0},
                    {"lease_until": float("nan")}, {"source_sha": "bad"}):
        with pytest.raises(ValueError):
            replace(claim, **changes)


def test_valid_mock_spec():
    job = spec()
    assert job.max_attempts == 2
    assert job.budget_usd == "0"
    assert spec(worker_kind="codex", budget_usd="0.50").worker_kind == "codex"
    records = (job, Claim("job", "a" * 40, "b" * 64, "owner", 1, 1, 100.0),
               ArtifactReceipt("job", "a" * 40, "b" * 64, "c" * 64, "sha256/blob", 0))
    for record in records:
        with pytest.raises(FrozenInstanceError):
            record.job_id = "changed"
