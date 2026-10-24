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
import re
from datetime import datetime
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


def _utc_seconds(raw) -> float | None:
    """Read GitHub REST timestamp, never guess for unstarted or ongoing jobs."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.timestamp() if dt.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def summarize_workflow_jobs(run: dict, jobs: list) -> dict:
    """GitHub job timing evidence. NEVER call job elapsed time 'frame render time'.

    Each native GitHub job includes download, Blender setup, rendering, lossless
    encoding, QA and upload. The real per-frame times come only from validated
    film_validation.json via render_metric_stats().
    """
    result = {
        "status": "INVALID_EVIDENCE",
        "run_id": run.get("id") if isinstance(run, Mapping) else None,
        "native": {
            "total": 30, "success": 0, "in_progress": 0, "queued": 0,
            "failed": 0, "measured_p50_completed_job_seconds": None,
            "measured_p95_completed_job_seconds": None,
            "sum_completed_job_seconds": None,
            "wall_clock_span_seconds": None,
            "peak_parallel_jobs": None,
            "mean_real_render_seconds": None,
            "time_kind": "GitHub job elapsed including setup, encode and upload",
        },
        "stages": {"guard_seconds": None, "speech_seconds": None,
                   "assemble_seconds": None},
        "workflow_elapsed_seconds": None,
        "upload_authorized": False,
    }
    if not isinstance(run, Mapping) or not isinstance(jobs, list) or not jobs:
        return result
    native_by_name = {}
    all_by_name = {}
    completed = []
    for job in jobs:
        if not isinstance(job, Mapping) or not isinstance(job.get("name"), str):
            return result
        name = job["name"]
        if name in all_by_name:
            return result
        all_by_name[name] = job
        match = re.fullmatch(r"native \((\d+)\)", name)
        if match:
            number = int(match.group(1))
            if number not in range(1, 901, 30):
                return result
            native_by_name[number] = job
        if job.get("status") == "completed":
            if job.get("conclusion") not in {"success", "failure", "cancelled",
                                             "timed_out", "skipped", "neutral"}:
                return result
            start = _utc_seconds(job.get("started_at"))
            finish = _utc_seconds(job.get("completed_at"))
            if start is None or finish is None or finish < start:
                return result
            completed.append((name, start, finish, job.get("conclusion")))
        elif job.get("status") not in {"queued", "waiting", "pending", "in_progress"}:
            return result
    counts = result["native"]
    for job in native_by_name.values():
        s = job.get("conclusion") or job.get("status")
        key = ("failed" if s in {"failure", "cancelled", "timed_out"}
               else "queued" if s in {"waiting", "pending"}
               else s)
        if key not in counts or type(counts[key]) is not int:
            return result
        counts[key] += 1
    if not native_by_name:
        return result
    # A GitHub run lists queued matrix jobs progressively. Missing entries
    # are PENDING, not zero-length 'completed' jobs.
    counts["queued"] += 30 - len(native_by_name)
    finished_native = [
        (name, start, stop) for name, start, stop, state in completed
        if name.startswith("native (") and state == "success"
    ]
    durations = sorted(stop - start for _, start, stop in finished_native)
    if durations:
        counts["measured_p50_completed_job_seconds"] = round(statistics.median(durations), 3)
        counts["measured_p95_completed_job_seconds"] = round(
            durations[math.ceil(.95 * len(durations)) - 1], 3)
        counts["sum_completed_job_seconds"] = round(sum(durations), 3)
    for stage in ("guard", "speech", "assemble"):
        match = next(((finish - start) for name, start, finish, state in completed
                      if name == stage and state == "success"), None)
        if match is not None:
            result["stages"][f"{stage}_seconds"] = round(match, 3)

    failed = any(state in {"failure", "cancelled", "timed_out"} for _, _, _, state in completed)
    if failed or run.get("conclusion") in {"failure", "cancelled", "timed_out"}:
        result["status"] = "FAILED"
        return result
    if run.get("status") != "completed":
        result["status"] = "IN_PROGRESS"
        return result
    # A run marked success is not evidence of full 900-frame delivery if the
    # individual matrix/assemble jobs are missing, cancelled, or skipped.
    if (run.get("conclusion") != "success"
            or set(native_by_name) != set(range(1, 901, 30))
            or counts["success"] != 30
            or any(all_by_name.get(stage, {}).get("conclusion") != "success"
                   for stage in ("guard", "speech", "assemble"))):
        return result
    all_native = [
        (start, finish) for name, start, finish, state in completed
        if name.startswith("native (") and state == "success"
    ]
    if len(all_native) != 30:
        return result
    earliest = min(start for start, _ in all_native)
    latest = max(finish for _, finish in all_native)
    counts["wall_clock_span_seconds"] = round(latest - earliest, 3)
    # End times before start times: simultaneous runners sharing a timestamp
    # aren't spuriously double-counted as extra concurrency.
    events = sorted(
        [(s, 1) for s, _ in all_native] +
        [(e, -1) for _, e in all_native],
        key=lambda pair: (pair[0], pair[1]),
    )
    concurrent = 0
    peak = 0
    for _, direction in events:
        concurrent += direction
        peak = max(peak, concurrent)
    if concurrent != 0:
        return result
    counts["peak_parallel_jobs"] = peak
    result["workflow_elapsed_seconds"] = round(
        max(stop for _, _, stop, _ in completed)
        - min(start for _, start, _, _ in completed), 3)
    result["status"] = "PASS_WORKFLOW"
    return result


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
