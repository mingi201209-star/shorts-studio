"""Wrangler boundary rejects ambiguous errors, oversized files and changed snapshots."""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from shorts_studio.r2_handoff.contracts import HandoffError
from shorts_studio.r2_handoff.oauth import OAuthGrant
from shorts_studio.r2_handoff.process import bounded_run
from shorts_studio.r2_handoff.wrangler import RemoteMissing, WranglerBackend
from test_r2_handoff_contracts import ACCOUNT, SHA_ABC

KEY = f"shorts-studio/episode2/v1/chunks/{SHA_ABC}.bin"


def backend(tmp_path, runner, **kw):
    return WranglerBackend(Path("/usr/bin/wrangler"), account_id=ACCOUNT,
        bucket="shorts-studio-media", home=tmp_path,
        acquire=lambda: OAuthGrant("never-in-argv", datetime(2099,1,1,tzinfo=timezone.utc)),
        before_call=lambda op: None, runner=runner, **kw)


@pytest.mark.parametrize("err", ["AccessDenied", "Unauthorized", "The specified key does not",
    "The specified key does not exist.\nAccessDenied", "NoSuchBucket", "HTTP 404"])
def test_unknown_or_truncated_errors_never_mean_missing(tmp_path, err):
    cli = backend(tmp_path, lambda argv, **kw: subprocess.CompletedProcess(argv,1,"",err),
                  missing_key_verified=True)
    with pytest.raises(HandoffError) as failure:
        cli.get(KEY, tmp_path / "download", expected_size=3)
    assert not isinstance(failure.value, RemoteMissing)


def test_missing_bucket_is_not_missing_object(tmp_path):
    cli = backend(tmp_path, lambda argv, **kw: subprocess.CompletedProcess(argv,1,"","NoSuchBucket"))
    with pytest.raises(HandoffError) as failure:
        cli.get(KEY, tmp_path / "download", expected_size=3)
    assert failure.value.code == "REMOTE_UNKNOWN"


def test_only_audited_exact_missing_fixture_authorizes_creation(tmp_path):
    runner = lambda argv, **kw: subprocess.CompletedProcess(argv,1,"","The specified key does not exist.")
    with pytest.raises(RemoteMissing):
        backend(tmp_path, runner, missing_key_verified=True).get(KEY, tmp_path/"a", expected_size=3)
    with pytest.raises(HandoffError, match="REMOTE_UNKNOWN"):
        backend(tmp_path, runner).get(KEY, tmp_path/"b", expected_size=3)


def test_giant_existing_remote_object_hits_output_limit(tmp_path):
    script = tmp_path / "oversize-wrangler"
    script.write_text(f'#!{sys.executable}\nimport sys\nfrom pathlib import Path\n'
        'Path(sys.argv[sys.argv.index("--file")+1]).write_bytes(b"x"*100000)\n')
    script.chmod(0o700)
    cli = backend(tmp_path, bounded_run)
    cli.wrangler = script
    dest = tmp_path / "download"
    with pytest.raises(HandoffError):
        cli.get(KEY, dest, expected_size=3)
    assert dest.stat().st_size <= 4


def test_put_uses_verified_snapshot_not_replaced_original_path(tmp_path):
    source = tmp_path / "snapshot.bin"
    source.write_bytes(b"wrong")
    cli = backend(tmp_path, lambda *a, **kw: pytest.fail("changed source reached network"))
    with pytest.raises(HandoffError, match="INTEGRITY_FAILED"):
        cli.put(KEY, source, expected_sha256=SHA_ABC, expected_size=3)
    source.write_bytes(b"abc")
    calls = []
    def runner(argv, **kw):
        assert "never-in-argv" not in str(argv)
        assert kw["env"]["CLOUDFLARE_ACCOUNT_ID"] == ACCOUNT
        assert kw["max_file_bytes"] == 4
        calls.append(argv)
        return subprocess.CompletedProcess(argv,0,"","")
    backend(tmp_path, runner).put(KEY, source, expected_sha256=SHA_ABC, expected_size=3)
    assert calls and source.read_bytes() == b"abc"


def test_timeout_does_not_claim_put_failed_without_reconciliation(tmp_path):
    source = tmp_path / "snapshot.bin"
    source.write_bytes(b"abc")
    def timeout(*a, **kw):
        raise HandoffError("CHILD_TIMEOUT")
    with pytest.raises(HandoffError, match="PUT_UNCERTAIN"):
        backend(tmp_path, timeout).put(KEY, source, expected_sha256=SHA_ABC, expected_size=3)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SHA_ABC


def test_traversal_and_readback_destination_symlinks_block(tmp_path):
    cli = backend(tmp_path, lambda *a, **kw: pytest.fail("unsafe request"))
    with pytest.raises(HandoffError):
        cli.get("../other", tmp_path / "d", expected_size=3)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "outside")
    with pytest.raises(HandoffError):
        cli.get(KEY, link, expected_size=3)
