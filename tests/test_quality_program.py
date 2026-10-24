"""Week-one quality scorecard: measured evidence ≠ an upload-ready Short."""
import json

from shorts_studio.quality_program import (
    EDITORIAL_AXES, build_scorecard, render_metric_stats,
)


def complete_report():
    scenes = [
        "hook_warning", "road_cut", "tire_contact",
        "rumble_mechanism", "shoulder_location", "driver_response",
    ]
    records = [
        {"frame": n, "sha256": f"{n:064x}", "rgb_sha256": f"{n + 1000:064x}"}
        for n in range(1, 901)
    ]
    return {
        "technical_status": "PASS", "frames": 900, "duration": 30,
        "resolution": [1080, 1920], "samples": 32,
        "native_frames": records, "decoded_unique_video_frames": 900,
        "source_sha256": "a" * 64, "sha256": "b" * 64,
        "render_frame_seconds": [4.0] * 900, "sum_native_render_seconds": 3600.0,
        "encode_seconds": 42.0, "maximum_silence_seconds": .31,
        "total_silence_seconds": 1.3, "loudness": {"integrated_lufs": -16.8},
        "semantic_visual_qa": {"status": "PASS", "results": [
            {"shot": scene, "status": "PASS", "margin": .07} for scene in scenes
        ]},
        "original_video_qa": {"status": "PASS", "results": {
            key: {"status": "PASS"}
            for key in ("visual_activity", "black_opening", "captions_visible")
        }},
        "physics_validated": False, "upload_authorized": False,
    }


def test_no_film_evidence_is_not_a_pass():
    output = build_scorecard(None)
    assert output["technical_status"] == "NOT_MEASURED"
    assert output["human_review"]["status"] == "NOT_REVIEWED"
    assert output["editorial_decision"] == "HOLD"
    assert output["upload_authorized"] is False
    assert output["render_metrics"] is None


def test_complete_native_report_is_measured_but_not_editorially_approved():
    snapshot = build_scorecard(complete_report())
    assert snapshot["technical_status"] == "PASS"
    assert snapshot["semantic_status"] == "PASS"
    assert snapshot["viewer_status"] == "PASS"
    assert snapshot["render_metrics"]["p50_frame_seconds"] == 4.0
    assert snapshot["render_metrics"]["p95_frame_seconds"] == 4.0
    assert snapshot["render_metrics"]["total_compute_seconds"] == 3600.0
    assert snapshot["render_metrics"]["encode_seconds"] == 42.0
    assert snapshot["render_metrics"]["wall_clock_seconds"] is None
    assert snapshot["human_review"]["status"] == "NOT_REVIEWED"
    assert snapshot["editorial_decision"] == "HOLD"
    assert snapshot["upload_authorized"] is False
    assert snapshot["limitations"]["physics_validated"] is False


def test_missing_or_inconclusive_semantics_cannot_be_promoted():
    for scenario in ("NOT_EVALUATED", "FAIL"):
        film = complete_report()
        film["semantic_visual_qa"]["results"][1]["status"] = scenario
        result = build_scorecard(film)
        assert result["technical_status"] == "INVALID_EVIDENCE"
        assert result["semantic_status"] != "PASS"
        assert result["editorial_decision"] == "HOLD"


def test_incomplete_or_fake_frame_evidence_is_invalid():
    for corruption in ("frames", "duplicates", "resolution", "viewer"):
        film = complete_report()
        if corruption == "frames":
            film["native_frames"].pop()
        if corruption == "duplicates":
            film["native_frames"][3]["sha256"] = film["native_frames"][2]["sha256"]
        if corruption == "resolution":
            film["resolution"] = [540, 960]
        if corruption == "viewer":
            film["original_video_qa"]["results"]["black_opening"]["status"] = "FAIL"
        scorecard = build_scorecard(film)
        assert scorecard["technical_status"] == "INVALID_EVIDENCE"
        assert scorecard["upload_authorized"] is False


def test_human_ratings_require_actual_reviewer_and_evidence():
    valid = {
        "reviewer": "editorial QA",
        "evidence": ["https://github.com/example/repo/actions/runs/123"],
        "ratings": dict.fromkeys(EDITORIAL_AXES, 3),
        "notes": "Direct inspection: wheel and road visible in all critical beats.",
    }
    snapshot = build_scorecard(complete_report(), valid)
    assert snapshot["human_review"]["status"] == "REVIEWED"
    assert snapshot["editorial_decision"] == "HOLD"
    assert not snapshot["upload_authorized"]

    for invalid in (
        {**valid, "reviewer": ""},
        {**valid, "evidence": []},
        {**valid, "ratings": {**valid["ratings"], "subject_legibility": True}},
    ):
        assert build_scorecard(complete_report(), invalid)["human_review"]["status"] == "INCOMPLETE"

    low = {**valid, "ratings": {**valid["ratings"], "visual_realism": 1}}
    assert build_scorecard(complete_report(), low)["human_review"]["status"] == "NEEDS_REVISION"


def test_renderer_time_stats_rejects_missing_nan_and_invalid_values():
    assert render_metric_stats([2.0, 4.0, 5.0, 6.0])["p50_frame_seconds"] == 4.5
    assert render_metric_stats([]) is None
    for invalid in ([0], [-1.0], [float("nan")], [True]):
        assert render_metric_stats(invalid) is None


def test_snapshot_has_no_unmeasured_performance_claim_or_fake_retention_metric():
    result = build_scorecard(complete_report())
    assert "view_count" not in json.dumps(result)
    assert "retention_rate" not in json.dumps(result)
    assert result["metrics_need_real_youtube_analytics"] is True


def test_weekly_scorecard_cli_runs_in_clean_python_without_factory_dependencies(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    target = tmp_path / "week01.json"
    process = subprocess.run(
        [sys.executable, "-S", "-m", "shorts_studio.quality_program",
         "--out", str(target)],
        cwd=root, capture_output=True, text=True, timeout=20,
    )
    assert process.returncode == 0, process.stderr
    data = json.loads(target.read_text())
    assert data["technical_status"] == "NOT_MEASURED"
    assert data["upload_authorized"] is False


def test_scorecard_shot_ids_match_authoritative_episode_contract():
    from shorts_studio.quality_program import SHOT_IDS
    from shorts_studio.factory.rumble_episode2 import SHOT_IDS as AUTHORITATIVE
    assert SHOT_IDS == AUTHORITATIVE


def _job(name, start, end, *, status="completed", conclusion="success"):
    return {
        "name": name, "status": status, "conclusion": conclusion,
        "started_at": start, "completed_at": end,
    }


def test_real_workflow_job_summary_rejects_premature_completion():
    from shorts_studio.quality_program import summarize_workflow_jobs
    jobs = [
        _job("guard", "2026-10-24T10:10:20Z", "2026-10-24T10:10:30Z"),
        _job("speech", "2026-10-24T10:10:30Z", "2026-10-24T10:11:00Z"),
    ] + [
        _job(f"native ({1 + 30 * i})", "2026-10-24T10:11:00Z",
             "2026-10-24T10:13:00Z") for i in range(25)
    ] + [
        _job(f"native ({1 + 30 * i})", "2026-10-24T10:15:00Z", None,
             status="in_progress", conclusion=None) for i in range(25, 30)
    ]
    data = summarize_workflow_jobs({"id": 40084843910, "status": "in_progress"}, jobs)
    assert data["native"]["success"] == 25
    assert data["native"]["in_progress"] == 5
    assert data["native"]["total"] == 30
    assert data["workflow_elapsed_seconds"] is None
    assert data["native"]["measured_p50_completed_job_seconds"] == 120.0
    assert data["upload_authorized"] is False
    assert data["status"] == "IN_PROGRESS"
    assert data["native"]["mean_real_render_seconds"] is None  # includes setup


def test_completed_workflow_timing_is_wall_clock_not_sum_of_parallel_jobs():
    from shorts_studio.quality_program import summarize_workflow_jobs
    jobs = [
        _job("guard", "2026-10-24T10:00:00Z", "2026-10-24T10:00:10Z"),
        _job("speech", "2026-10-24T10:00:10Z", "2026-10-24T10:00:20Z"),
    ] + [
        _job(f"native ({1 + 30 * i})", "2026-10-24T10:01:00Z",
             "2026-10-24T10:03:00Z") for i in range(30)
    ] + [_job("assemble", "2026-10-24T10:03:00Z", "2026-10-24T10:04:00Z")]
    data = summarize_workflow_jobs({"id": 1, "status": "completed", "conclusion": "success"}, jobs)
    assert data["status"] == "PASS_WORKFLOW"
    assert data["workflow_elapsed_seconds"] == 240.0
    assert data["native"]["sum_completed_job_seconds"] == 3600.0
    assert data["native"]["wall_clock_span_seconds"] == 120.0
    assert data["native"]["peak_parallel_jobs"] == 30
    assert data["stages"]["speech_seconds"] == 10.0
    assert data["stages"]["assemble_seconds"] == 60.0
    assert data["upload_authorized"] is False


def test_workflow_timing_fails_closed_on_missing_shards_failing_jobs_and_invalid_times():
    from shorts_studio.quality_program import summarize_workflow_jobs
    completed = [_job(f"native ({1 + 30 * i})",
                       "2026-10-24T10:00:00Z", "2026-10-24T10:05:00Z")
                 for i in range(30)]
    assert summarize_workflow_jobs(
        {"status": "completed", "conclusion": "success"}, completed
    )["status"] == "INVALID_EVIDENCE"  # missing assembler/guard/speech
    jobs = completed + [
        _job("guard", "2026-10-24T09:59:00Z", "2026-10-24T09:59:10Z"),
        _job("speech", "2026-10-24T09:59:10Z", "2026-10-24T09:59:30Z"),
        _job("assemble", "2026-10-24T10:05:00Z", "2026-10-24T10:06:00Z"),
    ]
    failing = [*jobs[:-1], {**jobs[-1], "conclusion": "failure"}]
    assert summarize_workflow_jobs(
        {"status": "completed", "conclusion": "failure"}, failing
    )["status"] == "FAILED"
    wrong = [*jobs[:-1], {**jobs[-1], "completed_at": "2026-10-24T09:59:00Z"}]
    assert summarize_workflow_jobs(
        {"status": "completed", "conclusion": "success"}, wrong
    )["status"] == "INVALID_EVIDENCE"


def test_workflow_timing_duplicate_native_names_and_empty_jobs_are_not_valid():
    from shorts_studio.quality_program import summarize_workflow_jobs
    assert summarize_workflow_jobs({"status": "completed", "conclusion": "success"}, [])["status"] == "INVALID_EVIDENCE"
    duplicates = [
        _job("native (1)", "2026-10-24T10:00:00Z", "2026-10-24T10:00:02Z"),
        _job("native (1)", "2026-10-24T10:00:00Z", "2026-10-24T10:00:04Z"),
    ]
    assert summarize_workflow_jobs(
        {"status": "completed", "conclusion": "success"}, duplicates
    )["status"] == "INVALID_EVIDENCE"


def test_weekly_cli_can_emit_real_workflow_job_progress_separately(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    run = tmp_path / "run.json"
    jobs = tmp_path / "jobs.json"
    result_file = tmp_path / "workflow.json"
    scorecard = tmp_path / "baseline.json"
    run.write_text(json.dumps({"id": 40084843910, "status": "in_progress"}))
    jobs.write_text(json.dumps({"jobs": [
        _job("native (1)", "2026-10-24T10:11:00Z", "2026-10-24T10:40:00Z"),
        _job("native (31)", "2026-10-24T10:11:00Z", None,
             status="in_progress", conclusion=None),
    ]}))
    p = subprocess.run([sys.executable, "-S", "-m", "shorts_studio.quality_program",
        "--out", str(scorecard), "--workflow-run-json", str(run),
        "--workflow-jobs-json", str(jobs), "--workflow-out", str(result_file)],
        cwd=root, capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stderr
    report = json.loads(result_file.read_text())
    assert report["status"] == "IN_PROGRESS"
    assert report["native"]["success"] == 1
    assert report["native"]["in_progress"] == 1
    assert report["native"]["queued"] == 28
    assert report["workflow_elapsed_seconds"] is None
    assert json.loads(scorecard.read_text())["technical_status"] == "NOT_MEASURED"
