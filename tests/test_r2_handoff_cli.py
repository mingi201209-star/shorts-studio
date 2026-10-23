"""Explicit CLI gates and sanitized output, with real private local job state."""
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from test_r2_handoff_contracts import ACCOUNT


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

from shorts_studio.r2_handoff import cli
from shorts_studio.r2_handoff.state import StateStore


def plan_args(tmp_path):
    source = tmp_path / "input.json"
    source.write_bytes(b"abcdef")
    return ["plan", "--file", str(source), "--account", ACCOUNT,
            "--bucket", "shorts-studio-media", "--namespace", "episode2",
            "--max-bytes", "1024", "--max-data-ops", "320", "--max-token-fetches", "320",
            "--deadline", (datetime.now(UTC)+timedelta(minutes=30)).isoformat(),
            "--state-root", str(tmp_path / "state")]


def test_cli_defaults_to_no_network_no_secret_access(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("child executed"))
    assert cli.main(plan_args(tmp_path)) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "DRY_RUN" and out["authorized_to_cleanup_local"] is False
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("op", ["apply", "resume"])
def test_apply_and_resume_require_explicit_flag_and_recorded_job(tmp_path, capsys, op):
    assert cli.main([op,"--job","unrecorded","--state-root",str(tmp_path/"state")]) == 2
    assert "BLOCKED:" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_verify_requires_read_remote_and_has_no_put_path(tmp_path, capsys):
    sha = "a"*64
    args = plan_args(tmp_path)
    file_index = args.index("--file")
    del args[file_index:file_index+2]
    args[0] = "verify"
    args += ["--manifest-key",f"shorts-studio/episode2/v1/manifests/{sha}.json",
             "--expected-manifest-sha",sha,"--destination",str(tmp_path/"restored.json")]
    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out)["operation"] == "verify"
    assert not (tmp_path / "state").exists() and not (tmp_path / "restored.json").exists()


def test_status_does_not_resume_work(tmp_path, monkeypatch, capsys):
    args = plan_args(tmp_path) + ["--save-plan"]
    assert cli.main(args) == 0
    job = json.loads(capsys.readouterr().out)["plan_id"]
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("child executed"))
    assert cli.main(["status","--job",job,"--state-root",str(tmp_path/"state")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["state"] == "STAGED" and out["data_used"] == 0


@pytest.mark.parametrize("command", ["plan", "apply", "resume", "verify"])
def test_android_blocks_media_commands(tmp_path, monkeypatch, capsys, command):
    args = plan_args(tmp_path)
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    if command != "plan":
        args = [command]
    assert cli.main(args) == 2
    assert "ANDROID_BLOCKED" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_every_error_is_sanitized_and_all_permission_flags_are_false(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli,"plan_source",lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("private-secret-sentinel")))
    assert cli.main(plan_args(tmp_path)) == 2
    captured = capsys.readouterr()
    assert "private-secret-sentinel" not in captured.err+captured.out
    assert "INTERNAL_ERROR" in captured.err


def test_resume_extension_requires_reason_and_preserves_identity_and_consumption(tmp_path,
                                                                                monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(plan_args(tmp_path)+["--save-plan"]) == 0
    job = json.loads(capsys.readouterr().out)["plan_id"]
    with StateStore(tmp_path/"state/jobs.sqlite") as s:
        s.reserve(job,kind="data",operation_id="prior",utc_now=datetime.now(UTC),
                  monotonic_now=0)
    args = ["resume","--job",job,"--state-root",str(tmp_path/"state"),"--apply",
            "--wrangler","/nonexistent/wrangler", "--new-max-bytes","1024",
            "--new-max-data-ops","500","--new-max-token-fetches","500",
            "--new-deadline",(datetime.now(UTC)+timedelta(hours=1)).isoformat()]
    assert cli.main(args) == 2
    capsys.readouterr()
    assert cli.main(args+["--reason","approved bounded retry"]) == 2  # missing audited OAuth
    assert "AUTH_REQUIRED" in capsys.readouterr().err
    with StateStore(tmp_path/"state/jobs.sqlite") as s:
        assert s.status(job)["id"] == job and s.status(job)["data_used"] >= 1
        assert s.limits_for(job).max_data_ops == 500


def test_help_lists_commands_and_verify_expected_digest():
    p = subprocess.run([sys.executable,"-m","shorts_studio.r2_handoff","--help"],
                       check=False, capture_output=True,text=True)
    assert p.returncode == 0
    assert all(word in p.stdout for word in ["plan", "apply", "status", "resume", "verify"])
