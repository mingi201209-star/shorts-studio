"""External responses below are deliberately fake; they are not quality receipts."""

import hashlib
import json

import pytest

from shorts_studio.improvement_adapter import MANDATORY, attempt, validate_ci, validate_qa


def good_qa():
    return {
        "status": "PASS",
        "semantic_required": True,
        "visual_qa": {"structural_status": "PASS"},
        "subtitle_reports": [{"status": "PASS"}],
        "semantic_visual_qa": {"status": "PASS", "results": [{"status": "PASS"}]},
        "final_video_qa": {"status": "PASS", "checks": {k: {"status": "PASS"} for k in MANDATORY}},
    }


@pytest.mark.parametrize("attack", ["hold", "skip", "semantic", "empty", "missing"])
def test_rejects_quality_claims(attack):
    qa = good_qa()
    if attack == "hold":
        qa["editorial_status"] = "HOLD"
    elif attack == "skip":
        qa["final_video_qa"]["checks"]["no_semantic_skip"]["status"] = "NOT_EVALUATED"
    elif attack == "semantic":
        qa["semantic_visual_qa"]["results"][0]["status"] = "SKIPPED"
    elif attack == "empty":
        qa["semantic_visual_qa"]["results"] = []
    else:
        qa["final_video_qa"]["checks"].pop("captions_visible")
    with pytest.raises(ValueError):
        validate_qa(qa)


@pytest.mark.parametrize(
    "status,conclusion,sha",
    [
        ("queued", None, "a" * 40),
        ("in_progress", "success", "a" * 40),
        ("completed", "skipped", "a" * 40),
        ("completed", "neutral", "a" * 40),
        ("completed", "failure", "a" * 40),
        ("completed", "success", "b" * 40),
    ],
)
def test_fake_gh_responses_fail_closed(status, conclusion, sha):
    with pytest.raises(ValueError):
        validate_ci(
            {
                "total_count": 1,
                "check_runs": [
                    {"name": "render", "head_sha": sha, "status": status, "conclusion": conclusion}
                ],
            },
            "a" * 40,
            ["render"],
        )


@pytest.mark.parametrize(
    "response",
    [
        {"total_count": 0, "check_runs": []},
        {"total_count": 101, "check_runs": []},
    ],
)
def test_missing_or_paginated_ci_rejected(response):
    with pytest.raises(ValueError):
        validate_ci(response, "a" * 40, ["render"])


@pytest.mark.parametrize(
    "attack",
    [
        "timeout",
        "process",
        "unchanged",
        "not_mp4",
        "qa",
        "review",
        "ci",
        "pending",
        "success",
        "push",
    ],
)
def test_attempt_quarantines_and_never_retries(tmp_path, attack):
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "examples").mkdir()
    source = repo / "examples/project.json"
    source.write_text("original")
    baseline = hashlib.sha256(b"fake-video").hexdigest() if attack == "unchanged" else "0" * 64
    config = {
        "repository": str(repo),
        "evidence_root": str(tmp_path / "evidence"),
        "max_attempts_per_day": 2,
        "max_cost_microusd_per_day": 200,
        "max_seconds_per_day": 120,
        "attempt_cost_microusd": 100,
        "paid_execution": False,
        "push_authorized": True,
        "draft_branch_prefix": "shorts-draft/test",
        "ci_timeout_seconds": 1,
        "editor_command": ["local-editor"],
        "review_command": ["local-review"],
        "timeout_seconds": 60,
        "task": "Improve",
        "editable_paths": ["examples/project.json"],
        "render_command": ["trusted-render"],
        "baseline_video_sha256": baseline,
        "github_repository": "owner/repo",
        "required_checks": ["render"],
    }
    calls = []

    class FakeRunner:
        def __init__(self, evidence, seconds):
            self.workspace = evidence / "workspace"
            self.head_reads = 0

        def __call__(self, argv, cwd, stdin=None):
            calls.append(argv)
            if argv[:2] == ["git", "clone"]:
                self.workspace.mkdir()
                (self.workspace / "examples").mkdir()
            if argv[0] == "bwrap":
                if attack == "timeout":
                    raise TimeoutError("bounded fake timeout")
                if attack == "process":
                    raise ValueError("fake external process failed")
                (cwd / "examples/project.json").write_text("candidate")
            if argv[:3] == ["git", "rev-parse", "HEAD"]:
                self.head_reads += 1
                return ("b" if self.head_reads == 3 else "a") * 40
            if argv[:4] == ["git", "diff", "--name-only", "a" * 40]:
                return "examples/project.json\n"
            if argv[:2] == ["git", "ls-files"]:
                return "examples/project.json\n"
            if argv[0] == "trusted-render":
                (cwd / "dist").mkdir()
                (cwd / "dist/final.mp4").write_bytes(b"fake-video")
                qa = good_qa()
                qa["output"] = str(cwd / "dist/final.mp4")
                if attack == "qa":
                    qa["editorial_status"] = "HOLD"
                (cwd / "dist/qa_report.json").write_text(json.dumps(qa))
            if argv[0] == "ffprobe":
                return json.dumps(
                    {
                        "format": {
                            "format_name": "png" if attack == "not_mp4" else "mov,mp4",
                            "duration": "2",
                        },
                        "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
                    }
                )
            if argv[0] == "local-review":
                binding = json.loads(stdin)
                return json.dumps(
                    {
                        **binding,
                        "decision": "HOLD" if attack == "review" else "PASS",
                        "regression": False,
                        "visual_notes": "compared",
                        "audio_notes": "compared",
                    }
                )
            if argv[:2] == ["git", "ls-remote"]:
                if sum(c[:2] == ["git", "ls-remote"] for c in calls) == 1:
                    return ""
                return "b" * 40 + "\trefs/heads/shorts-draft/test/attempt-0001"
            if "push" in argv and attack == "push":
                raise ValueError("ambiguous push failure")
            if argv[0] == "gh" and "/status?" in argv[-1]:
                return json.dumps({"sha": "b" * 40, "total_count": 0, "statuses": []})
            if argv[0] == "gh":
                return json.dumps(
                    {
                        "total_count": 1,
                        "check_runs": [
                            {
                                "name": "render",
                                "head_sha": ("c" if attack == "ci" else "b") * 40,
                                "status": "queued" if attack == "pending" else "completed",
                                "conclusion": "success",
                            }
                        ],
                    }
                )
            return ""

    job = {"iteration": 1, "last_good_sha": None, "previous_candidate_sha": None}
    result = attempt(config, job, FakeRunner)
    assert source.read_text() == "original"
    evidence = tmp_path / "evidence/attempt-0001"
    if attack == "success":
        assert result["state"] == "verified"
        assert result["candidate_commit_sha"] == "b" * 40
        assert any("push" in c for c in calls)
    else:
        assert result["state"] == "rejected"
    if attack in ("qa", "review", "timeout", "process", "not_mp4", "unchanged"):
        assert not any("push" in c for c in calls)
    assert json.loads((evidence / "result.json").read_text()) == result
    before = len(calls)
    assert attempt(config, job, FakeRunner)["state"] == "rejected"
    assert len(calls) == before
    assert sum(c[0] == "bwrap" for c in calls) == 1
    assert sum("push" in c for c in calls) <= 1


def test_real_runner_timeout_preserves_process_logs(tmp_path):
    import subprocess
    import sys

    from shorts_studio.improvement_adapter import Runner

    run = Runner(tmp_path, 0.1)
    with pytest.raises(subprocess.TimeoutExpired):
        run(
            [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(20)"],
            tmp_path,
        )
    assert (tmp_path / "process-001.json").is_file()
    assert (tmp_path / "process-001.stdout").is_file()
    assert (tmp_path / "process-001.stderr").is_file()


def budget_config():
    return {
        "max_attempts_per_day": 2,
        "max_cost_microusd_per_day": 20,
        "max_seconds_per_day": 120,
        "attempt_cost_microusd": 10,
        "timeout_seconds": 60,
        "paid_execution": False,
        "push_authorized": True,
        "github_repository": "owner/repo",
        "draft_branch_prefix": "shorts-draft/test",
        "review_command": ["review"],
        "render_command": ["render"],
        "editor_command": ["editor"],
        "required_checks": ["draft-test"],
        "ci_timeout_seconds": 10,
    }


@pytest.mark.parametrize("bound", ["attempts", "cost", "time"])
def test_persistent_rolling_day_reservations(tmp_path, monkeypatch, bound):
    from shorts_studio import improvement_adapter as module

    config = budget_config()
    if bound == "cost":
        config["max_cost_microusd_per_day"] = 10
    elif bound == "time":
        config["max_seconds_per_day"] = 60
    else:
        config["max_attempts_per_day"] = 1
    monkeypatch.setattr(module.time, "time", lambda: 100000)
    module.reserve(config, {"iteration": 1}, tmp_path)
    with pytest.raises(module.BudgetExhausted):
        module.reserve(config, {"iteration": 2}, tmp_path)
    monkeypatch.setattr(module.time, "time", lambda: 186401)
    module.reserve(config, {"iteration": 2}, tmp_path)


@pytest.mark.parametrize("key", list(budget_config()))
def test_missing_policy_fails_before_external_work(tmp_path, key):
    from shorts_studio.improvement_adapter import reserve

    config = budget_config()
    del config[key]
    with pytest.raises((KeyError, ValueError)):
        reserve(config, {"iteration": 1}, tmp_path)


def test_budget_policy_cannot_be_raised_after_restart(tmp_path):
    from shorts_studio.improvement_adapter import reserve

    config = budget_config()
    reserve(config, {"iteration": 1}, tmp_path)
    config["max_attempts_per_day"] = 3
    with pytest.raises(ValueError, match="configuration changed"):
        reserve(config, {"iteration": 2}, tmp_path)


def test_paid_execution_fails_closed(tmp_path):
    from shorts_studio.improvement_adapter import reserve

    config = budget_config()
    config["paid_execution"] = True
    with pytest.raises(ValueError, match="paid execution unsupported"):
        reserve(config, {"iteration": 1}, tmp_path)
