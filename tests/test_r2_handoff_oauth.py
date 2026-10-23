"""Secret sentinels stay inside a bounded, owner-only OAuth subprocess boundary."""
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest

from shorts_studio.r2_handoff.contracts import HandoffError
from shorts_studio.r2_handoff.oauth import OAuthConfig, data_environment, obtain_grant
from shorts_studio.r2_handoff.process import bounded_run

TOKEN = "private-test-sentinel"
NOW = datetime(2026, 10, 24, tzinfo=UTC)


def config(tmp_path, *, seconds=3600):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    parent = home
    for part in (".config", ".wrangler", "config"):
        parent /= part
        parent.mkdir(mode=0o700)
    f = parent / "default.toml"
    f.write_text(f'oauth_token = "{TOKEN}"\nrefresh_token = "private-refresh"\n'
                 f'expiration_time = "{(NOW+timedelta(seconds=seconds)).isoformat()}"\n'
                 'unrelated = "preserve"\n')
    f.chmod(0o600)
    binary = home / "wrangler"
    binary.write_text("fixture tool, never executed")
    binary.chmod(0o700)
    audit = home / "audit.json"
    audit.write_text(json.dumps({"version": "4.152.0",
        "entrypoint_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "credentials_write_private": True, "secrets_logging_safe": True}))
    audit.chmod(0o600)
    return OAuthConfig(home, f, home / "locks", "default", binary, audit)


def ok_runner(argv, **kw):
    assert argv[-3:] == ["auth", "token", "--json"]
    assert TOKEN not in str(argv)
    assert kw["timeout"] == 30
    return subprocess.CompletedProcess(argv, 0, json.dumps({"type":"oauth","token":TOKEN}), "")


def test_token_command_captures_oauth_and_never_echoes_it(tmp_path, capsys):
    cfg = config(tmp_path)
    grant = obtain_grant(cfg, now=NOW, runner=ok_runner)
    assert TOKEN not in repr(grant)
    with pytest.raises(TypeError):
        asdict(grant)
    assert data_environment(grant, home=cfg.home)["CLOUDFLARE_API_TOKEN"] == TOKEN
    assert capsys.readouterr() == ("", "")


def test_ambient_credentials_do_not_override_profile(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    for key in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_API_KEY", "CLOUDFLARE_EMAIL", "WRANGLER_LOG"):
        monkeypatch.setenv(key, TOKEN)
    def runner(argv, **kw):
        assert not any(k.startswith("CLOUDFLARE_") for k in kw["env"])
        assert TOKEN not in str(kw["env"])
        return subprocess.CompletedProcess(argv, 0, json.dumps({"type":"api_token","token":TOKEN}), "")
    with pytest.raises(HandoffError, match="AUTH_REQUIRED"):
        obtain_grant(cfg, now=NOW, runner=runner)


@pytest.mark.parametrize("mode", ["file", "parent", "symlink", "audit"])
def test_config_replacement_and_permissions_block(tmp_path, mode):
    cfg = config(tmp_path)
    if mode == "file":
        cfg.config_file.chmod(0o644)
    elif mode == "parent":
        cfg.config_file.parent.chmod(0o755)
    elif mode == "audit":
        cfg.audit_file.unlink()
    else:
        other = cfg.config_file.with_suffix(".other")
        cfg.config_file.rename(other)
        cfg.config_file.symlink_to(other)
    with pytest.raises(HandoffError):
        obtain_grant(cfg, now=NOW, runner=lambda *a, **k: pytest.fail("unsafe auth call"))


@pytest.mark.parametrize("seconds,allowed", [(119, False), (120, True)])
def test_token_with_less_than_120_seconds_enters_wait_auth_window(tmp_path, seconds, allowed):
    cfg = config(tmp_path, seconds=seconds)
    if allowed:
        assert obtain_grant(cfg, now=NOW, runner=ok_runner)
    else:
        with pytest.raises(HandoffError, match="WAIT_AUTH_WINDOW"):
            obtain_grant(cfg, now=NOW, runner=ok_runner)


@pytest.mark.parametrize("raw,code", [("not JSON",0), ('{"type":"oauth"}',0), (TOKEN,1)])
def test_revoked_or_malformed_refresh_returns_auth_required_without_login(tmp_path, raw, code):
    cfg = config(tmp_path)
    original = cfg.config_file.read_bytes()
    def runner(argv, **kw):
        assert "login" not in argv
        return subprocess.CompletedProcess(argv, code, raw, TOKEN)
    with pytest.raises(HandoffError, match="AUTH_REQUIRED") as err:
        obtain_grant(cfg, now=NOW, runner=runner)
    assert TOKEN not in str(err.value)
    assert cfg.config_file.read_bytes() == original


def test_atomic_token_rotation_keeps_private_file_and_uses_fresh_expiry(tmp_path):
    cfg = config(tmp_path, seconds=-1)
    def runner(argv, **kw):
        replacement = cfg.config_file.with_suffix(".new")
        replacement.write_text(cfg.config_file.read_text().replace(
            (NOW-timedelta(seconds=1)).isoformat(), (NOW+timedelta(hours=1)).isoformat()))
        replacement.chmod(0o600)
        os.replace(replacement, cfg.config_file)
        return ok_runner(argv, **kw)
    assert obtain_grant(cfg, now=NOW, runner=runner)
    assert 'unrelated = "preserve"' in cfg.config_file.read_text()


def test_bounded_child_output_and_timeout_are_sanitized():
    with pytest.raises(HandoffError, match="CHILD_OUTPUT_LIMIT"):
        bounded_run([sys.executable,"-c","print('x'*1100000)"], env=dict(os.environ), timeout=5)
    with pytest.raises(HandoffError, match="CHILD_TIMEOUT"):
        bounded_run([sys.executable,"-c","import time; time.sleep(3)"],
                    env=dict(os.environ), timeout=0.05)
