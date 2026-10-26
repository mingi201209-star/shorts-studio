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
    "attack", ["timeout", "process", "unchanged", "not_mp4", "qa", "human", "ci"]
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
        "max_attempts": 2,
        "timeout_seconds": 60,
        "task": "Improve",
        "editable_paths": ["examples/project.json"],
        "render_command": ["trusted-render"],
        "baseline_video_sha256": baseline,
        "human_review": str(tmp_path / "review.json"),
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
            if argv[0] == "codex":
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
                if attack == "ci":
                    proof = tmp_path / "proof.png"
                    proof.write_bytes(b"fake-proof")
                    review = {
                        "commit_sha": "b" * 40,
                        "video_sha256": hashlib.sha256(b"fake-video").hexdigest(),
                        "qa_sha256": hashlib.sha256(
                            (cwd / "dist/qa_report.json").read_bytes()
                        ).hexdigest(),
                        "decision": "PASS",
                        "regression": False,
                        "baseline_video_sha256": baseline,
                        "reviewer": "test",
                        "reviewed_at": "test",
                        "visual_notes": "test",
                        "audio_notes": "test",
                        "proof_path": str(proof),
                        "proof_sha256": hashlib.sha256(b"fake-proof").hexdigest(),
                    }
                    (tmp_path / "review.json").write_text(json.dumps(review))
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
            if argv[0] == "gh":
                return json.dumps(
                    {
                        "total_count": 1,
                        "check_runs": [
                            {
                                "name": "render",
                                "head_sha": "c" * 40,
                                "status": "completed",
                                "conclusion": "success",
                            }
                        ],
                    }
                )
            return ""

    job = {"iteration": 1, "last_good_sha": None, "previous_candidate_sha": None}
    with pytest.raises((ValueError, OSError, TimeoutError)):
        attempt(config, job, FakeRunner)
    assert source.read_text() == "original"
    if attack == "ci":
        assert any(c[0] == "gh" for c in calls)
    if attack == "human":
        assert any(c[0] == "ffmpeg" for c in calls)
    evidence = tmp_path / "evidence/attempt-0001"
    assert json.loads((evidence / "result.json").read_text())["state"] == "rejected"
    before = len(calls)
    with pytest.raises(FileExistsError):
        attempt(config, job, FakeRunner)
    assert len(calls) == before
    assert sum(c[0] == "codex" for c in calls) == 1


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
