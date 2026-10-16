"""Nightshift development checkpoints must fail closed and survive restarts."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shorts_studio import nightshift as ns

SHA = "a" * 40


def create_state(tmp_path):
    path = tmp_path / "state.json"
    ns.initialize(path, baseline_sha=SHA, goal="stabilize existing Shorts QA")
    return path


def passing_report():
    return {
        "status": "PASS",
        "semantic_required": True,
        "semantic_visual_qa": {"results": [{"scene": "s1", "status": "PASS"}]},
        "visual_qa": {"structural_status": "PASS"},
        "final_video_qa": {"status": "PASS", "checks": {"timing": {"status": "PASS"}}},
        "subtitle_reports": [{"status": "PASS"}],
        "captions": {"status": "PASS"},
    }


def prepare_render(tmp_path, report=None):
    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "final.mp4").write_bytes(b"video")
    (dist / "qa_report.json").write_text(
        json.dumps(passing_report() if report is None else report), encoding="utf-8"
    )
    return dist


def passing_probe(*_args, **_kwargs):
    return SimpleNamespace(
        returncode=0,
        stdout=json.dumps({
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1080,
                 "height": 1920, "r_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "32.4"},
        }),
    )


def test_initialization_is_idempotent_and_atomic(tmp_path):
    path = create_state(tmp_path)
    assert ns.read_state(path)["baseline_sha"] == SHA
    assert ns.initialize(path, baseline_sha=SHA, goal="stabilize existing Shorts QA")["steps"] == {}
    with pytest.raises(ns.GateError, match="another goal"):
        ns.initialize(path, baseline_sha=SHA, goal="different job")
    assert path.stat().st_mode & 0o777 == 0o600


def test_sha_and_goal_are_required(tmp_path):
    with pytest.raises(ns.GateError, match="40-character"):
        ns.initialize(tmp_path / "bad", baseline_sha="short", goal="task")
    with pytest.raises(ns.GateError, match="Goal"):
        ns.initialize(tmp_path / "bad", baseline_sha=SHA, goal=" ")


def test_render_requires_same_sha_full_regression(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    monkeypatch.setattr(ns, "current_head", lambda: SHA)
    with pytest.raises(ns.GateError, match="full regression"):
        ns.run_stage(path, "render", head_sha=SHA)
    assert ns.read_state(path)["steps"] == {}


def test_branch_drift_blocks_work_before_execution(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    monkeypatch.setattr(ns, "current_head", lambda: "b" * 40)
    with pytest.raises(ns.GateError, match="HEAD changed"):
        ns.run_stage(path, "tests", head_sha=SHA)
    assert not ns.read_state(path)["steps"]


def test_failed_tests_remain_failed_and_retry_is_bounded(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    monkeypatch.setattr(ns, "current_head", lambda: SHA)
    monkeypatch.setattr(
        ns.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1)
    )
    for _ in range(2):
        with pytest.raises(ns.GateError, match="exited"):
            ns.run_stage(path, "tests", head_sha=SHA)
    with pytest.raises(ns.GateError, match="Retry budget"):
        ns.run_stage(path, "tests", head_sha=SHA)
    state = ns.read_state(path)
    assert state["steps"]["tests"]["status"] == "FAIL"
    assert state["steps"]["tests"]["attempts"] == 2
    assert state["decision"] == "not_ready"


def test_previous_running_step_is_recorded_as_interrupted(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    data = ns.read_state(path)
    data["steps"]["tests"] = {"status": "RUNNING", "sha": SHA, "attempts": 1}
    ns.write_state(path, data)
    monkeypatch.setattr(ns, "current_head", lambda: SHA)
    monkeypatch.setattr(
        ns.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0)
    )
    result = ns.run_stage(path, "tests", head_sha=SHA)
    assert result["steps"]["tests"]["status"] == "PASS"
    assert result["steps"]["tests"]["attempts"] == 2
    assert {"stage": "tests", "result": "INTERRUPTED"} in result["history"]


def test_renderer_never_runs_when_test_results_are_from_another_sha(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    data = ns.read_state(path)
    data["steps"]["tests"] = {"status": "PASS", "sha": "b" * 40}
    ns.write_state(path, data)
    monkeypatch.setattr(ns, "current_head", lambda: SHA)
    with pytest.raises(ns.GateError, match="this exact HEAD"):
        ns.run_stage(path, "render", head_sha=SHA)


@pytest.mark.parametrize("mutator", [
    lambda r: r.update(semantic_required=False),
    lambda r: r["semantic_visual_qa"]["results"][0].update(status="NOT_EVALUATED"),
    lambda r: r["visual_qa"].update(structural_status="FAIL"),
    lambda r: r["final_video_qa"]["checks"]["timing"].update(status="FAIL"),
    lambda r: r["subtitle_reports"][0].update(status="FAIL"),
    lambda r: r["captions"].update(status="FAIL"),
])
def test_quality_gates_cannot_be_weakened(tmp_path, monkeypatch, mutator):
    report = passing_report()
    mutator(report)
    outdir = prepare_render(tmp_path, report)
    monkeypatch.setattr(ns.subprocess, "run", passing_probe)
    with pytest.raises(ns.GateError):
        ns.verify_render_evidence(outdir)


def test_probe_validates_real_media_requirements(tmp_path, monkeypatch):
    outdir = prepare_render(tmp_path)
    monkeypatch.setattr(ns.subprocess, "run", passing_probe)
    proof = ns.verify_render_evidence(outdir)
    assert proof["fps"] == 30
    assert proof["semantic_scenes"] == 1

    def missing_audio(*_args, **_kwargs):
        probe = passing_probe()
        payload = json.loads(probe.stdout)
        payload["streams"].pop()
        return SimpleNamespace(stdout=json.dumps(payload))
    monkeypatch.setattr(ns.subprocess, "run", missing_audio)
    with pytest.raises(ns.GateError, match="AAC audio"):
        ns.verify_render_evidence(outdir)


def test_stale_render_artifact_cannot_prove_new_run(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    data = ns.read_state(path)
    data["steps"]["tests"] = {"status": "PASS", "sha": SHA}
    ns.write_state(path, data)
    dist = prepare_render(tmp_path)
    monkeypatch.setattr(ns, "current_head", lambda: SHA)
    monkeypatch.setattr(
        ns.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0)
    )
    for artifact in ("final.mp4", "qa_report.json"):
        import os
        os.utime(dist / artifact, (100, 100))
    with pytest.raises(ns.GateError, match="not generated by this run"):
        ns.run_stage(path, "render", head_sha=SHA, outdir=dist)
    assert ns.read_state(path)["steps"]["render"]["status"] == "FAIL"


def test_human_review_required_for_final_decision(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    data = ns.read_state(path)
    data["steps"]["tests"] = {"status": "PASS", "sha": SHA}
    data["steps"]["render"] = {"status": "PASS", "sha": SHA}
    data["decision"] = "awaiting_human_video_review"
    ns.write_state(path, data)
    monkeypatch.setattr(ns, "current_head", lambda: SHA)
    with pytest.raises(ns.GateError, match="notes"):
        ns.record_review(path, head_sha=SHA, outcome="pass", notes="")
    state = ns.record_review(
        path, head_sha=SHA, outcome="fail", notes="Narration still robotic"
    )
    assert state["decision"] == "reviewed_fail"
    assert state["last_verified_sha"] is None
    with pytest.raises(ns.GateError, match="fresh verified render"):
        ns.record_review(path, head_sha=SHA, outcome="pass", notes="changed my mind")
    state = ns.read_state(path)
    state["decision"] = "awaiting_human_video_review"  # after separate verified rerender
    ns.write_state(path, state)
    state = ns.record_review(
        path, head_sha=SHA, outcome="pass",
        notes="Listened to narration and compared visual output against baseline",
    )
    assert state["decision"] == "reviewed_pass"
    assert state["last_verified_sha"] == SHA


def test_render_run_honors_strict_semantic_gate_env(tmp_path, monkeypatch):
    path = create_state(tmp_path)
    data = ns.read_state(path)
    data["steps"]["tests"] = {"status": "PASS", "sha": SHA}
    ns.write_state(path, data)
    dist = tmp_path / "dist"
    seen = []

    def fake_run(argv, **kwargs):
        seen.append((argv, kwargs.get("env", {}).get("SHORTS_REQUIRE_SEMANTIC_QA")))
        if argv[1:3] == ["-m", "shorts_studio"]:
            prepare_render(tmp_path)
            return SimpleNamespace(returncode=0)
        return passing_probe()
    monkeypatch.setattr(ns, "current_head", lambda: SHA)
    monkeypatch.setattr(ns.subprocess, "run", fake_run)
    state = ns.run_stage(path, "render", head_sha=SHA, outdir=dist)
    assert seen[0][1] == "1"
    assert state["decision"] == "awaiting_human_video_review"
    assert state["last_verified_sha"] is None
