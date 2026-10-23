"""Wrangler OAuth R2 pilot, tested without network or real credentials."""
from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from shorts_studio.r2_wrangler_pilot import upload_via_wrangler
from shorts_studio.r2_verified_transfer import IntegrityError


class FakeCLI:
    def __init__(self, *, corrupt_reads=False, error=None):
        self.store = {}
        self.calls = []
        self.corrupt_reads = corrupt_reads
        self.error = error

    def __call__(self, argv, *, env, timeout, capture_output, text):
        assert capture_output and text and timeout <= 90
        assert env["CLOUDFLARE_API_TOKEN"] == "test-oauth"
        assert "test-oauth" not in str(argv)
        self.calls.append(argv[3])
        op, key = argv[3], argv[4]
        path = Path(argv[argv.index("--file") + 1])
        if self.error is not None:
            return subprocess.CompletedProcess(argv, 1, "", self.error)
        if op == "get":
            if key not in self.store:
                return subprocess.CompletedProcess(argv, 1, "", "The specified key does not exist.")
            raw = self.store[key]
            if self.corrupt_reads:
                raw += b"corrupt"
            path.write_bytes(raw)
            return subprocess.CompletedProcess(argv, 0, "", "")
        if op == "put":
            self.store[key] = path.read_bytes()
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(op)


@pytest.fixture
def input_file(tmp_path):
    f = tmp_path / "native-shard.mkv"
    f.write_bytes(b"native-unique-source" * 30)
    return f


@pytest.fixture
def oauth_file(tmp_path):
    c = tmp_path / "default.toml"
    c.write_text('oauth_token = "test-oauth"\nexpiration_time = "2099-10-23T20:00:00Z"\n')
    c.chmod(0o600)
    return c


def invoke(file, oauth, *, apply=True, client=None, bucket="shorts-studio-media",
           limit=4096, now=None):
    return upload_via_wrangler(
        file, bucket=bucket, prefix="episode2/sha256", max_bytes=limit,
        oauth_config=oauth, wrangler="/opt/wrangler", apply=apply,
        runner=client, now=now or datetime(2026, 10, 24, tzinfo=timezone.utc),
    )


def test_dry_run_has_zero_network_or_secret_dependency(input_file, tmp_path):
    out = invoke(input_file, tmp_path / "missing.toml", apply=False)
    assert out["status"] == "DRY_RUN"
    assert out["authorized_to_cleanup_local"] is False


def test_put_then_get_verified_and_original_unchanged(input_file, oauth_file):
    cloud = FakeCLI()
    before = input_file.read_bytes()
    result = invoke(input_file, oauth_file, client=cloud)
    assert result["status"] == "VERIFIED"
    assert result["verified_remote_sha256"] == result["sha256"]
    assert result["authorized_to_cleanup_local"] is False
    assert cloud.calls == ["get", "put", "get"]
    assert input_file.read_bytes() == before


def test_same_object_second_time_not_overwritten(input_file, oauth_file):
    cloud = FakeCLI()
    first = invoke(input_file, oauth_file, client=cloud)
    second = invoke(input_file, oauth_file, client=cloud)
    assert second["status"] == "VERIFIED_EXISTING"
    assert second["sha256"] == first["sha256"]
    assert cloud.calls.count("put") == 1


def test_existing_different_object_is_blocked_without_put(input_file, oauth_file):
    cloud = FakeCLI()
    plan = invoke(input_file, oauth_file, apply=False)
    cloud.store["shorts-studio-media/" + plan["key"]] = b"wrong-remote"
    with pytest.raises(IntegrityError):
        invoke(input_file, oauth_file, client=cloud)
    assert cloud.calls == ["get"]


def test_corrupt_remote_readback_is_never_success(input_file, oauth_file):
    cloud = FakeCLI(corrupt_reads=True)
    with pytest.raises(IntegrityError):
        invoke(input_file, oauth_file, client=cloud)
    assert cloud.calls == ["get", "put", "get"]
    assert input_file.exists()


@pytest.mark.parametrize("err", ["AccessDenied", "timeout", "unauthorized", "429", "Unexpected error"])
def test_unknown_get_error_never_falls_through_to_put(input_file, oauth_file, err):
    cloud = FakeCLI(error=err)
    with pytest.raises(RuntimeError):
        invoke(input_file, oauth_file, client=cloud)
    assert cloud.calls == ["get"]


def test_expired_oauth_is_blocked_before_any_network(input_file, oauth_file):
    oauth_file.write_text('oauth_token = "test-oauth"\nexpiration_time = "2026-10-23T20:00:00Z"\n')
    cloud = FakeCLI()
    with pytest.raises(ValueError, match="expired"):
        invoke(input_file, oauth_file, client=cloud)
    assert cloud.calls == []


def test_world_readable_oauth_config_refused(input_file, oauth_file):
    oauth_file.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        invoke(input_file, oauth_file, client=FakeCLI())


def test_missing_token_does_not_try_network(input_file, tmp_path):
    cloud = FakeCLI()
    with pytest.raises(ValueError):
        invoke(input_file, tmp_path / "missing.toml", client=cloud)
    assert cloud.calls == []


def test_oversize_source_fails_closed(input_file, oauth_file):
    with pytest.raises(ValueError):
        invoke(input_file, oauth_file, limit=100, client=FakeCLI())


def test_android_is_not_used_as_file_storage(input_file, oauth_file, monkeypatch):
    cloud = FakeCLI()
    monkeypatch.setattr("shorts_studio.r2_wrangler_pilot._is_android", lambda: True)
    with pytest.raises(ValueError, match="Android"):
        invoke(input_file, oauth_file, client=cloud)
    assert cloud.calls == []
