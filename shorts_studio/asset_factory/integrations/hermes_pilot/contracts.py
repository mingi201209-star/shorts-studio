"""Strict, non-executable Hermes proposal contract; no provider side effects."""

import hashlib
import json
import re
from dataclasses import dataclass

from shorts_studio.asset_factory.controller.contracts import JobSpec

_KEYS = frozenset({
    "schema", "intent_id", "origin_task_id", "source_sha", "kind",
    "requested_by", "payload",
})
_IDENTIFIER = re.compile(r"[a-z0-9-]{8,64}", flags=re.ASCII)
_ORIGIN = re.compile(r"[a-z0-9-]{1,64}", flags=re.ASCII)
_SHA = re.compile(r"[0-9a-f]{40}", flags=re.ASCII)


@dataclass(frozen=True)
class ParsedIntent:
    intent_id: str
    origin_task_id: str
    source_sha: str
    input_digest: str
    job_id: str
    canonical_bytes: bytes


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate proposal field")
        value[key] = item
    return value


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON value")


def parse_intent(raw: bytes, *, expected_head: str) -> ParsedIntent:
    """Reject any proposal outside an exact finite mock-only wire contract."""
    if type(raw) is not bytes or not raw or len(raw) > 4096 or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("invalid raw proposal")
    try:
        decoded = raw.decode("utf-8", errors="strict")
        item = json.loads(decoded, object_pairs_hook=_unique_pairs,
                          parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid proposal encoding or JSON") from exc
    if type(item) is not dict or set(item) != _KEYS:
        raise ValueError("unexpected proposal shape")
    if (item["schema"] != "hermes-controller-pilot/v1"
            or item["kind"] != "mock_proof"
            or item["requested_by"] != "hermes-proposal"
            or type(item["payload"]) is not dict or item["payload"]):
        raise ValueError("non-mock proposal refused")
    for name, pattern in (("intent_id", _IDENTIFIER),
                          ("origin_task_id", _ORIGIN),
                          ("source_sha", _SHA)):
        value = item[name]
        if type(value) is not str or pattern.fullmatch(value) is None:
            raise ValueError("invalid proposal identifier")
    if (_SHA.fullmatch(expected_head or "") is None
            or item["source_sha"] != expected_head):
        raise ValueError("source HEAD mismatch")
    canonical = json.dumps(item, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return ParsedIntent(item["intent_id"], item["origin_task_id"],
                        item["source_sha"], digest, "hp-" + digest[:40], canonical)


def to_mock_job(parsed: ParsedIntent) -> JobSpec:
    """Map a validated intent onto existing immutable Controller contracts."""
    if not isinstance(parsed, ParsedIntent):
        raise TypeError("unvalidated proposal")
    return JobSpec(
        job_id=parsed.job_id, asset_id="hermes-pilot", asset_version="v1",
        source_sha=parsed.source_sha, input_digest=parsed.input_digest,
        stage="mock-proof", worker_kind="mock", payload_json="{}",
        budget_usd="0", max_attempts=1,
    )
