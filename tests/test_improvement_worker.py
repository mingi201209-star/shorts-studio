import json
import hashlib
import sys

import pytest

from shorts_studio.improvement_worker import approve, connect, step


def adapter(tmp_path, result):
    script = tmp_path / "adapter.py"
    script.write_text("import json,sys\njob=json.load(sys.stdin)\nprint(json.dumps(" + repr(result) + "))\n")
    return [sys.executable, str(script)]


def test_approval_is_bound_to_verified_candidate_and_survives_restart(tmp_path):
    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"example")
    sha = hashlib.sha256(video.read_bytes()).hexdigest()
    db = connect(tmp_path / "state.db")
    assert step(db, adapter(tmp_path, dict(candidate_sha=sha, video_path=str(video),
                                            qa_pass=True, ci_pass=True, regression=False)), 10) == "running"
    with pytest.raises(ValueError):
        approve(db, "b" * 64)
    approve(db, sha)
    db.close()
    reopened = connect(tmp_path / "state.db")
    assert step(reopened, ["no-such-adapter"], 10) == "accepted"


@pytest.mark.parametrize("overrides", [
    {"qa_pass": False}, {"ci_pass": False}, {"regression": True},
    {"video_path": "/does/not/exist.mp4"}, {"candidate_sha": "fake"},
])
def test_unverified_result_blocks_without_replacing_good_version(tmp_path, overrides):
    video = tmp_path / "candidate.mp4"
    video.write_bytes(b"example")
    result = dict(candidate_sha=hashlib.sha256(video.read_bytes()).hexdigest(), video_path=str(video), qa_pass=True,
                  ci_pass=True, regression=False)
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
    result = dict(candidate_sha=sha, video_path=str(video), qa_pass=True,
                  ci_pass=True, regression=False)
    db = connect(tmp_path / "state.db")
    assert step(db, adapter(tmp_path, result), 10) == "running"
    assert step(db, adapter(tmp_path, result), 10) == "blocked"
