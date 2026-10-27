import hashlib
import json

import pytest

from shorts_studio.improvement_adapter import MANDATORY
from shorts_studio.improvement_review import assess


def report(first=2, static=3.5, reuse=0.625, ending=0.5):
    return {
        "status": "PASS",
        "output": "final.mp4",
        "semantic_required": True,
        "visual_qa": {"structural_status": "PASS"},
        "semantic_visual_qa": {"status": "PASS", "results": [{"status": "PASS"}]},
        "subtitle_reports": [{"status": "PASS"}],
        "final_video_qa": {
            "status": "PASS",
            "checks": {name: {"status": "PASS"} for name in MANDATORY},
            "metrics": {
                "first_5s_visual_changes": first,
                "max_static_visual_seconds": static,
                "global_source_reuse_ratio": reuse,
                "ending_new_ratio": ending,
            },
        },
    }


def setup(tmp_path, candidate_report, baseline_report=None):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (baseline / "final.mp4").write_bytes(b"actual baseline bytes")
    (candidate / "final.mp4").write_bytes(b"different candidate bytes")
    (baseline / "qa_report.json").write_text(json.dumps(baseline_report or report()))
    (candidate / "qa_report.json").write_text(json.dumps(candidate_report))

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    return {
        "commit_sha": "a" * 40,
        "video_sha256": digest(candidate / "final.mp4"),
        "qa_sha256": digest(candidate / "qa_report.json"),
        "baseline_video_sha256": digest(baseline / "final.mp4"),
        "comparison_video_sha256": digest(baseline / "final.mp4"),
        "comparison_video_path": str(baseline / "final.mp4"),
        "video_path": str(candidate / "final.mp4"),
        "qa_path": str(candidate / "qa_report.json"),
    }


def test_same_metrics_hold_despite_different_video_bytes(tmp_path):
    result = assess(setup(tmp_path, report()))
    assert result["decision"] == "HOLD"
    assert result["regression"] is False


def test_first_five_gain_with_no_loss_is_internal_pass(tmp_path):
    result = assess(setup(tmp_path, report(first=3)))
    assert result["decision"] == "PASS"
    assert result["regression"] is False


@pytest.mark.parametrize(
    "candidate",
    [
        report(first=1),
        report(static=4.0),
        report(reuse=0.7),
        report(ending=0.3),
        report(first=3, reuse=0.8),
    ],
)
def test_any_regression_blocks_even_when_other_metric_improves(tmp_path, candidate):
    result = assess(setup(tmp_path, candidate))
    assert result["decision"] == "HOLD"
    assert result["regression"] is True


def test_tampered_media_or_qa_fails(tmp_path):
    binding = setup(tmp_path, report(first=3))
    video = tmp_path / "candidate/final.mp4"
    video.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="video changed"):
        assess(binding)


def test_optional_semantic_holds_are_not_promoted(tmp_path):
    bad = report(first=3)
    bad["semantic_visual_qa"]["results"][0]["status"] = "NOT_EVALUATED"
    with pytest.raises(ValueError):
        assess(setup(tmp_path, bad))


def test_report_pointing_to_another_video_rejected(tmp_path):
    candidate = report(first=3)
    candidate["output"] = "other.mp4"
    with pytest.raises(ValueError, match="another video"):
        assess(setup(tmp_path, candidate))
