"""Weekly evidence scorecard for the eight-week quality program.

This summarizes *existing* native, semantic and final-video QA. It does not
replace any gate or independently attest provenance of a supplied JSON file.
Editorial value and YouTube retention require human/released-video evidence.
Nothing in this module authorizes publication, billing, merging, or upload.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections.abc import Mapping
from pathlib import Path

# Snapshot is intentionally stdlib-only, including on a clean GitHub runner.
# A regression test checks these stable episode-2 IDs against the canonical
# factory contract so drift fails CI instead of silently changing QA evidence.
SHOT_IDS = (
    "hook_warning", "road_cut", "tire_contact",
    "rumble_mechanism", "shoulder_location", "driver_response",
)

EDITORIAL_AXES = (
    "subject_legibility",
    "visual_realism",
    "physical_contact",
    "motion_variety",
    "voice_naturalness",
    "narrative_retention",
)
VIDEO_CHECKS = ("visual_activity", "black_opening", "captions_visible")


def _number(value, *, positive=False) -> bool:
    return (type(value) in (int, float)
            and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def _hash(value) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(ch in "0123456789abcdef" for ch in value.lower()))


def render_metric_stats(values) -> dict | None:
    """Report compute-time, not misleading wall-clock time or runner ETA."""
    if not isinstance(values, list) or not values or any(
        not _number(v, positive=True) for v in values
    ):
        return None
    seconds = sorted(values)
    p95 = seconds[math.ceil(.95 * len(seconds)) - 1]
    return {
        "sampled_native_frames": len(seconds),
        "p50_frame_seconds": round(statistics.median(seconds), 3),
        "p95_frame_seconds": round(p95, 3),
        "total_compute_seconds": round(sum(seconds), 3),
        "wall_clock_seconds": None,
    }


def _semantic(report):
    data = report.get("semantic_visual_qa") if isinstance(report, Mapping) else None
    if not isinstance(data, Mapping):
        return "NOT_EVALUATED", None
    results = data.get("results")
    if not isinstance(results, list) or len(results) != len(SHOT_IDS):
        return "NOT_EVALUATED", None
    if [r.get("shot") if isinstance(r, Mapping) else None for r in results] != list(SHOT_IDS):
        return "NOT_EVALUATED", None
    if any(r.get("status") == "FAIL" for r in results):
        return "FAIL", None
    if data.get("status") != "PASS" or any(r.get("status") != "PASS" for r in results):
        return "NOT_EVALUATED", None
    margins = [r.get("margin") for r in results]
    if any(not _number(x, positive=True) for x in margins):
        return "NOT_EVALUATED", None
    return "PASS", round(min(margins), 6)


def _viewer(report):
    data = report.get("original_video_qa") if isinstance(report, Mapping) else None
    if not isinstance(data, Mapping):
        return "NOT_EVALUATED"
    checks = data.get("results")
    if not isinstance(checks, Mapping) or set(checks) != set(VIDEO_CHECKS):
        return "NOT_EVALUATED"
    if any(isinstance(checks[x], Mapping) and checks[x].get("status") == "FAIL"
           for x in VIDEO_CHECKS):
        return "FAIL"
    return ("PASS" if data.get("status") == "PASS"
            and all(isinstance(checks[x], Mapping)
                    and checks[x].get("status") == "PASS" for x in VIDEO_CHECKS)
            else "NOT_EVALUATED")


def _human_review(review):
    if review is None:
        return {"status": "NOT_REVIEWED", "ratings": None, "evidence": []}
    if not isinstance(review, Mapping):
        return {"status": "INCOMPLETE", "ratings": None, "evidence": []}
    ratings = review.get("ratings")
    evidence = review.get("evidence")
    valid = (isinstance(review.get("reviewer"), str)
             and bool(review["reviewer"].strip())
             and isinstance(review.get("notes"), str)
             and bool(review["notes"].strip())
             and isinstance(evidence, list)
             and bool(evidence)
             and all(isinstance(x, str) and bool(x.strip()) for x in evidence)
             and isinstance(ratings, Mapping)
             and set(ratings) == set(EDITORIAL_AXES)
             and all(type(x) is int and 0 <= x <= 3 for x in ratings.values()))
    if not valid:
        return {"status": "INCOMPLETE", "ratings": None, "evidence": []}
    return {
        "status": "NEEDS_REVISION" if any(x < 2 for x in ratings.values()) else "REVIEWED",
        "ratings": dict(ratings),
        "evidence": list(evidence),
        "reviewer": review["reviewer"],
        "notes": review["notes"],
    }


def _native_records_valid(report):
    frames = report.get("native_frames")
    if not isinstance(frames, list) or len(frames) != 900:
        return False
    hashes = []
    rgbs = []
    for index, record in enumerate(frames, 1):
        if not isinstance(record, Mapping) or type(record.get("frame")) is not int:
            return False
        if record["frame"] != index:
            return False
        if not _hash(record.get("sha256")) or not _hash(record.get("rgb_sha256")):
            return False
        hashes.append(record["sha256"])
        rgbs.append(record["rgb_sha256"])
    return len(set(hashes)) == len(set(rgbs)) == 900


def build_scorecard(film: dict | None, human: dict | None = None) -> dict:
    """Conservative wrapper over prior evidence; a scorecard is never a gate bypass."""
    reviewer = _human_review(human)
    report = film if isinstance(film, Mapping) else {}
    has_report = film is not None
    stats = render_metric_stats(report.get("render_frame_seconds"))
    semantic, margin = _semantic(report)
    viewer = _viewer(report)
    valid = (
        has_report
        and report.get("technical_status") == "PASS"
        and type(report.get("frames")) is int and report["frames"] == 900
        and type(report.get("duration")) in (int, float) and report["duration"] == 30
        and report.get("resolution") == [1080, 1920]
        and type(report.get("samples")) is int and report["samples"] == 32
        and type(report.get("decoded_unique_video_frames")) is int
        and report["decoded_unique_video_frames"] == 900
        and _native_records_valid(report)
        and _hash(report.get("source_sha256")) and _hash(report.get("sha256"))
        and stats is not None and stats["sampled_native_frames"] == 900
        and _number(report.get("sum_native_render_seconds"), positive=True)
        and abs(stats["total_compute_seconds"]
                - report["sum_native_render_seconds"]) <= .1
        and _number(report.get("encode_seconds"), positive=True)
        and _number(report.get("maximum_silence_seconds"))
        and _number(report.get("total_silence_seconds"))
        and isinstance(report.get("loudness"), Mapping)
        and semantic == "PASS" and viewer == "PASS"
        and report.get("upload_authorized") is False
    )
    performance = None
    if stats is not None:
        performance = {
            **stats,
            "encode_seconds": report.get("encode_seconds"),
            "total_silence_seconds": report.get("total_silence_seconds"),
            "maximum_silence_seconds": report.get("maximum_silence_seconds"),
            "runner_parallelism": None,
            "measurement_note": (
                "Native render seconds are SUMMED CPU work across runners, "
                "not elapsed workflow time; runner start/end timestamps required."
            ),
        }
    return {
        "program_version": "2026-10-24-v1",
        "technical_status": ("NOT_MEASURED" if not has_report
                             else "PASS" if valid else "INVALID_EVIDENCE"),
        "semantic_status": semantic if has_report else "NOT_MEASURED",
        "viewer_status": viewer if has_report else "NOT_MEASURED",
        "min_semantic_margin": margin,
        "render_metrics": performance,
        "source_scene_sha256": report.get("source_sha256"),
        "finished_video_sha256": report.get("sha256"),
        "limitations": {
            "physics_validated": report.get("physics_validated") is True,
            "human_review_required": True,
            "scorecard_independently_verifies_mp4": False,
        },
        "human_review": reviewer,
        "editorial_decision": "HOLD",
        "upload_authorized": False,
        "metrics_need_real_youtube_analytics": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--film-validation", type=Path, help="Original film_validation.json")
    parser.add_argument("--review", type=Path, help="Optional actual human-review JSON")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # Explicitly provided missing files fail hard, rather than becoming 'not measured'.
    film = json.loads(args.film_validation.read_text()) if args.film_validation else None
    review = json.loads(args.review.read_text()) if args.review else None
    report = build_scorecard(film, review)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("QUALITY_PROGRAM_WEEKLY_SCORECARD "
          + json.dumps({"technical_status": report["technical_status"],
                        "human_review": report["human_review"]["status"],
                        "editorial_decision": report["editorial_decision"]}), flush=True)


if __name__ == "__main__":
    main()
