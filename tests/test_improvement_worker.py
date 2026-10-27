import hashlib
import json
import sys

import pytest

from shorts_studio.improvement_worker import approve, connect, step


def adapter(tmp_path, result):
    script = tmp_path / "adapter.py"
    script.write_text(
        "import json,sys\njob=json.load(sys.stdin)\nprint(json.dumps(" + repr(result) + "))\n"
    )
    return [sys.executable, str(script)]


def test_approval_is_bound_to_verified_candidate_and_survives_restart(tmp_path):
    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"example")
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    db = connect(tmp_path / "state.db")
    assert (
        step(
            db,
            adapter(
                tmp_path,
                {
                    "candidate_sha": sha,
                    "video_path": str(video),
                    "qa_pass": True,
                    "ci_pass": True,
                    "regression": False,
                },
            ),
            10,
        )
        == "running"
    )
    with pytest.raises(ValueError):
        approve(db, "b" * 64)
    approve(db, sha)
    db.close()
    reopened = connect(tmp_path / "state.db")
    assert step(reopened, ["no-such-adapter"], 10) == "accepted"


@pytest.mark.parametrize(
    "overrides",
    [
        {"qa_pass": False},
        {"ci_pass": False},
        {"regression": True},
        {"video_path": "/does/not/exist.mp4"},
        {"candidate_sha": "fake"},
    ],
)
def test_unverified_result_blocks_without_replacing_good_version(tmp_path, overrides):
    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"example")
    result = {
        "candidate_sha": hashlib.sha256(video.read_bytes()).hexdigest(),
        "video_path": str(video),
        "qa_pass": True,
        "ci_pass": True,
        "regression": False,
    }
    result.update(overrides)
    db = connect(tmp_path / "state.db")
    assert step(db, adapter(tmp_path, result), 10) == "blocked"
    assert db.execute("SELECT last_good_sha FROM campaign").fetchone()[0] is None


def test_crashed_adapter_blocks_and_records_failure(tmp_path):
    db = connect(tmp_path / "state.db")
    assert step(db, [sys.executable, "-c", "raise RuntimeError('boom')"], 10) == "blocked"
    assert db.execute("SELECT count(*) FROM events WHERE kind='blocked'").fetchone()[0] == 1


def test_repeated_candidate_blocks_instead_of_claiming_improvement(tmp_path):
    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"example")
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    result = {
        "candidate_sha": sha,
        "video_path": str(video),
        "qa_pass": True,
        "ci_pass": True,
        "regression": False,
    }
    db = connect(tmp_path / "state.db")
    assert step(db, adapter(tmp_path, result), 10) == "running"
    assert step(db, adapter(tmp_path, result), 10) == "blocked"


def test_internal_rejection_continues_without_human_or_losing_good_candidate(tmp_path):
    db = connect(tmp_path / "state.db")
    command = adapter(tmp_path, {"state": "rejected", "failure": "internal comparison failed"})
    assert step(db, command, 10) == "running"
    assert step(db, command, 10) == "running"
    assert db.execute("SELECT iteration,last_good_sha FROM campaign").fetchone() == (2, None)
    assert db.execute("SELECT count(*) FROM events WHERE kind='rejected'").fetchone()[0] == 2


def test_deferred_budget_does_not_consume_iteration(tmp_path):
    db = connect(tmp_path / "state.db")
    assert step(db, adapter(tmp_path, {"state": "deferred"}), 10) == "running"
    assert db.execute("SELECT iteration FROM campaign").fetchone()[0] == 0


def test_approval_rechecks_exact_video_bytes(tmp_path):
    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"example")
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    db = connect(tmp_path / "state.db")
    assert (
        step(
            db,
            adapter(
                tmp_path,
                {
                    "candidate_sha": sha,
                    "video_path": str(video),
                    "qa_pass": True,
                    "ci_pass": True,
                    "regression": False,
                },
            ),
            10,
        )
        == "running"
    )
    video.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA256"):
        approve(db, sha)


def test_rejection_rolls_back_to_verified_source_for_next_iteration(tmp_path):
    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"verified")
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    db = connect(tmp_path / "state.db")
    result = {
        "candidate_sha": sha,
        "video_path": str(video),
        "qa_pass": True,
        "ci_pass": True,
        "regression": False,
        "source_path": "/evidence/good/workspace",
        "candidate_commit_sha": "a" * 40,
    }
    assert step(db, adapter(tmp_path, result), 10) == "running"
    assert step(db, adapter(tmp_path, {"state": "rejected"}), 10) == "running"
    assert db.execute("SELECT candidate_sha,last_good_sha FROM campaign").fetchone() == (sha, sha)
    script = tmp_path / "inspect_job.py"
    script.write_text(
        "import json,sys\njob=json.load(sys.stdin)\n"
        "assert job['previous_source']=='/evidence/good/workspace'\n"
        "assert job['previous_commit']=='" + "a" * 40 + "'\n"
        "print(json.dumps({'state':'rejected'}))\n"
    )
    assert step(db, [sys.executable, str(script)], 10) == "running"


def test_approval_during_iteration_cannot_be_overwritten(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from shorts_studio import improvement_worker as module

    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"verified")
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    db = connect(tmp_path / "state.db")
    result = {
        "candidate_sha": sha,
        "video_path": str(video),
        "qa_pass": True,
        "ci_pass": True,
        "regression": False,
    }
    assert step(db, adapter(tmp_path, result), 10) == "running"
    newer = tmp_path / "new.mp4"
    newer.write_bytes(b"newer")
    result.update(
        candidate_sha=hashlib.sha256(newer.read_bytes()).hexdigest(), video_path=str(newer)
    )

    def complete(*args, **kwargs):
        approve(db, sha)
        return SimpleNamespace(stdout=json.dumps(result))

    monkeypatch.setattr(module.subprocess, "run", complete)
    assert step(db, ["adapter"], 10) == "accepted"
    assert db.execute("SELECT state,accepted_sha,candidate_sha FROM campaign").fetchone() == (
        "accepted",
        sha,
        sha,
    )
