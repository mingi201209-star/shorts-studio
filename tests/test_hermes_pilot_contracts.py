import hashlib
import json
from dataclasses import FrozenInstanceError

import pytest

from shorts_studio.asset_factory.integrations.hermes_pilot.contracts import (
    ParsedIntent,
    parse_intent,
    to_mock_job,
)

HEAD = "a" * 40


def proposal(**changes):
    item = {"schema": "hermes-controller-pilot/v1", "intent_id": "first-job",
            "origin_task_id": "kanban-1", "source_sha": HEAD, "kind": "mock_proof",
            "requested_by": "hermes-proposal", "payload": {}}
    item.update(changes)
    return json.dumps(item, ensure_ascii=False).encode()


def test_valid_intent_canonical_identity():
    parsed = parse_intent(proposal(), expected_head=HEAD)
    assert isinstance(parsed, ParsedIntent)
    assert parsed.input_digest == hashlib.sha256(parsed.canonical_bytes).hexdigest()
    assert parsed.job_id == "hp-" + parsed.input_digest[:40]
    assert parsed.canonical_bytes == json.dumps(json.loads(proposal()), sort_keys=True,
                                                separators=(",", ":"), ensure_ascii=False).encode()
    job = to_mock_job(parsed)
    assert (job.job_id, job.asset_id, job.asset_version, job.stage, job.worker_kind,
            job.payload_json, job.budget_usd, job.max_attempts) == (
                parsed.job_id, "hermes-pilot", "v1", "mock-proof", "mock", "{}", "0", 1)
    assert (job.source_sha, job.input_digest) == (HEAD, parsed.input_digest)
    with pytest.raises(FrozenInstanceError):
        parsed.intent_id = "modified"


@pytest.mark.parametrize("raw", [
    b"\xef\xbb\xbf" + proposal(), proposal() + b"\xff", b"\xf0\x9f\x92",
    b'{"a":1}' + (b" " * 4090), proposal() + b"{}",
    b'{"schema":"hermes-controller-pilot/v1","schema":"duplicate"}',
    b'{"x":NaN}', b'{"x":Infinity}',
])
def test_rejects_utf8_bom_truncated_multibyte_and_4097_bytes(raw):
    with pytest.raises(ValueError):
        parse_intent(raw, expected_head=HEAD)


@pytest.mark.parametrize("change", [
    {"intent_id": "Upper-Case"}, {"intent_id": "bad/route"},
    {"intent_id": "한글문자-1234"}, {"intent_id": "short"},
    {"origin_task_id": "../../escape"}, {"origin_task_id": "x\ncontrol"},
    {"requested_by": "owner-reviewed"}, {"kind": "execute_shell"},
    {"payload": {"command": "rm -rf /"}}, {"source_sha": "b" * 40},
    {"source_sha": "A" * 40}, {"schema": "hermes-controller-pilot/v2"},
    {"approved": True}, {"input_digest": "a" * 64},
])
def test_rejects_duplicate_unknown_control_and_unicode_identifiers(change):
    with pytest.raises(ValueError):
        parse_intent(proposal(**change), expected_head=HEAD)


def test_rejects_non_mock_command_and_fake_approval():
    assert parse_intent(proposal(), expected_head=HEAD).intent_id == "first-job"
    for changed in [{"kind": "codex"}, {"requested_by": "approved"},
                    {"payload": {"shell": "pwd"}}, {"authority": "owner"}]:
        with pytest.raises(ValueError):
            parse_intent(proposal(**changed), expected_head=HEAD)


def test_exact_sha_required():
    with pytest.raises(ValueError):
        parse_intent(proposal(), expected_head="b" * 40)
    assert parse_intent(proposal(), expected_head=HEAD).source_sha == HEAD


def test_reordered_fields_do_not_change_hash_and_origin_change_does():
    original = json.loads(proposal())
    reversed_bytes = json.dumps(dict(reversed(list(original.items())))).encode()
    assert parse_intent(reversed_bytes, expected_head=HEAD).input_digest == (
        parse_intent(proposal(), expected_head=HEAD).input_digest)
    assert parse_intent(proposal(origin_task_id="kanban-2"), expected_head=HEAD).input_digest != (
        parse_intent(proposal(), expected_head=HEAD).input_digest)
