"""Reject noncanonical identities, unsafe sources and insufficient transfer budgets."""
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from shorts_studio.r2_handoff.contracts import (
    HandoffError,
    Limits,
    canonical_manifest,
    manifest_key,
    parse_manifest,
    plan_source,
)

ACCOUNT = "a" * 32
SHA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def limits(**kw):
    values = {"max_bytes": 1024, "max_data_ops": 320, "max_token_fetches": 320,
                  "deadline_utc": datetime.now(UTC) + timedelta(minutes=30)}
    return Limits(**(values | kw))


def plan(tmp_path, raw=b"abc", **kw):
    source = tmp_path / "sample.json"
    source.write_bytes(raw)
    return plan_source(source, account_id=ACCOUNT, bucket="shorts-studio-media",
                       namespace="episode2", limits=limits(**kw), expected_sha256=None,
                       provenance={})


def test_manifest_is_canonical_and_has_gap_free_offsets(tmp_path):
    m = plan(tmp_path)
    assert m.sha256 == SHA_ABC
    assert m.chunks[0].key == f"shorts-studio/episode2/v1/chunks/{SHA_ABC}.bin"
    raw = canonical_manifest(m)
    assert canonical_manifest(parse_manifest(raw, account_id=ACCOUNT,
           bucket=m.bucket, namespace=m.namespace)) == raw
    assert b"created_at" not in raw
    assert manifest_key(m).startswith("shorts-studio/episode2/v1/manifests/")
    for change in [{"offset": 1}, {"index": 1}, {"size_bytes": 0}, {"key": "other"},
                   {"sha256": "bad"}]:
        with pytest.raises(HandoffError):
            canonical_manifest(replace(m, chunks=(replace(m.chunks[0], **change),)))
    multi = plan(tmp_path, raw=b"abc", chunk_bytes=1)
    for chunks in [tuple(reversed(multi.chunks)), (multi.chunks[0],)*3]:
        with pytest.raises(HandoffError):
            canonical_manifest(replace(multi, chunks=chunks))


@pytest.mark.parametrize("field,value", [("account_id", "b"*32), ("bucket", "other-bucket"),
                                         ("namespace", "other")])
def test_cross_namespace_manifest_is_rejected(tmp_path, field, value):
    m = plan(tmp_path)
    args = {"account_id": ACCOUNT, "bucket": m.bucket, "namespace": m.namespace}
    args[field] = value
    with pytest.raises(HandoffError):
        parse_manifest(canonical_manifest(m), **args)


def test_plan_is_offline_and_enforces_v1_limits(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("network/secret child"))
    m = plan(tmp_path)
    assert m.chunk_bytes == 33554432
    limits(max_bytes=2**31, max_data_ops=260).validate_for(64, mode="upload")
    limits(max_data_ops=65).validate_for(64, mode="verify")
    with pytest.raises(HandoffError):
        limits(max_data_ops=259).validate_for(64, mode="upload")
    for kw in [{"max_bytes": 2**31+1}, {"max_bytes": True}, {"max_data_ops": 1025},
               {"max_token_fetches": 0}, {"chunk_bytes": 2**27+1}, {"max_retries": 3}]:
        with pytest.raises(HandoffError):
            limits(**kw)
    for raw, kw in [(b"", {}), (b"a"*65, {"chunk_bytes": 1})]:
        with pytest.raises(HandoffError):
            plan(tmp_path, raw=raw, **kw)
    f = tmp_path / "huge.json"
    with f.open("wb") as h:
        h.truncate(2**31+1)
    with pytest.raises(HandoffError):
        plan_source(f, account_id=ACCOUNT, bucket="shorts-studio-media", namespace="e",
                    limits=limits(max_bytes=2**31), expected_sha256=None, provenance={})


def test_manifest_rejects_unknown_oversized_or_duplicate_json(tmp_path):
    m = plan(tmp_path)
    args = {"account_id": ACCOUNT, "bucket": m.bucket, "namespace": m.namespace}
    data = json.loads(canonical_manifest(m))
    for raw in [b"x"*(2**20+1), b'{"a":1,"a":2}',
                json.dumps(data | {"unexpected": True}).encode()]:
        with pytest.raises(HandoffError):
            parse_manifest(raw, **args)


def test_symlink_or_wrong_expected_digest_never_plans(tmp_path):
    m = plan(tmp_path)
    f = tmp_path / "sample.json"
    link = tmp_path / "link.json"
    link.symlink_to(f)
    for source, expected in [(link, None), (f, "0"*64)]:
        with pytest.raises(HandoffError):
            plan_source(source, account_id=ACCOUNT, bucket=m.bucket, namespace=m.namespace,
                        limits=limits(), expected_sha256=expected, provenance={})
