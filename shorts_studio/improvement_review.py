"""Compare trusted video QA evidence against the exact previous review video.

This is a narrow automated metric review. It does not replace human taste.
"""

import hashlib
import json
import math
import sys
from pathlib import Path

from shorts_studio.improvement_adapter import validate_qa

METRICS = (
    "first_5s_visual_changes",
    "max_static_visual_seconds",
    "global_source_reuse_ratio",
    "ending_new_ratio",
)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metric(report: dict, name: str) -> float:
    value = report["final_video_qa"]["metrics"][name]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"invalid metric: {name}")
    return float(value)


def assess(binding: dict) -> dict:
    candidate = Path(binding["video_path"]).resolve()
    baseline = Path(binding["comparison_video_path"]).resolve()
    qa_path = Path(binding["qa_path"]).resolve()
    if not candidate.is_file() or not baseline.is_file() or not qa_path.is_file():
        raise ValueError("missing comparison media or QA")
    if sha256(candidate) != binding["video_sha256"]:
        raise ValueError("candidate video changed")
    if sha256(baseline) != binding["comparison_video_sha256"]:
        raise ValueError("comparison video changed")
    if sha256(qa_path) != binding["qa_sha256"]:
        raise ValueError("candidate QA changed")

    current = load(qa_path)
    previous_qa = baseline.with_name("qa_report.json")
    if not previous_qa.is_file():
        raise ValueError("comparison QA missing")
    previous = load(previous_qa)
    validate_qa(current)
    validate_qa(previous)
    for report, report_path, video in (
        (current, qa_path, candidate),
        (previous, previous_qa, baseline),
    ):
        declared = Path(report["output"])
        roots = (report_path.parent, report_path.parent.parent)
        if not any((root / declared).resolve() == video for root in roots):
            raise ValueError("QA report points to another video")
    old = {name: metric(previous, name) for name in METRICS}
    new = {name: metric(current, name) for name in METRICS}

    regressions = []
    if new["first_5s_visual_changes"] < old["first_5s_visual_changes"]:
        regressions.append("first five seconds lost visual changes")
    if new["max_static_visual_seconds"] > old["max_static_visual_seconds"] + 0.01:
        regressions.append("longer static hold")
    if new["global_source_reuse_ratio"] > old["global_source_reuse_ratio"] + 0.01:
        regressions.append("more repeated source material")
    if new["ending_new_ratio"] + 0.01 < old["ending_new_ratio"]:
        regressions.append("less novelty near ending")
    improvements = (
        new["first_5s_visual_changes"] > old["first_5s_visual_changes"]
        or new["max_static_visual_seconds"] + 0.25 < old["max_static_visual_seconds"]
        or new["global_source_reuse_ratio"] + 0.05 < old["global_source_reuse_ratio"]
        or new["ending_new_ratio"] > old["ending_new_ratio"] + 0.05
    )
    passed = not regressions and improvements
    return {
        **{
            key: binding[key]
            for key in (
                "commit_sha",
                "video_sha256",
                "qa_sha256",
                "baseline_video_sha256",
                "comparison_video_sha256",
            )
        },
        "decision": "PASS" if passed else "HOLD",
        "regression": bool(regressions),
        "visual_notes": json.dumps(
            {"previous": old, "candidate": new, "regressions": regressions},
            ensure_ascii=False,
            sort_keys=True,
        ),
        "audio_notes": (
            "Decoded audio stream and narration_continuity QA PASS; "
            "subjective voice quality remains for user review."
        ),
    }


def main() -> None:
    try:
        print(json.dumps(assess(json.load(sys.stdin)), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
