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
