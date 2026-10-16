"""Crash-safe checkpoints for the existing Shorts Studio development gates.

This is a local supervisor primitive, not an AI model, uploader, merger, or
replacement renderer. External Termux/cloud supervisors may relaunch the CLI.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

STAGES = ("tests", "render")
MAX_ATTEMPTS = 2
STATE_VERSION = 1


class GateError(RuntimeError):
    """A required proof is missing or invalid; do not accept the change."""


def _require_sha(sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise GateError("A full, lowercase 40-character commit SHA is required")
    return sha


def current_head() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return _require_sha(process.stdout.strip())


def read_state(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != STATE_VERSION:
        raise GateError("Unsupported checkpoint version")
    _require_sha(data["baseline_sha"])
    if not isinstance(data.get("steps"), dict):
        raise GateError("Malformed steps in checkpoint")
    return data


def write_state(path: Path, state: dict) -> None:
    """Replace one complete checkpoint atomically; never store credentials."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".checkpoint-",
            delete=False
        ) as handle:
            temp_name = handle.name
            os.fchmod(handle.fileno(), 0o600)
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def initialize(path: Path, *, baseline_sha: str, goal: str) -> dict:
    _require_sha(baseline_sha)
    if not goal.strip():
        raise GateError("Goal cannot be empty")
    path = Path(path)
    if path.exists():
        saved = read_state(path)
        if saved["baseline_sha"] != baseline_sha or saved["goal"] != goal:
            raise GateError("Existing checkpoint belongs to another goal or SHA")
        return saved
    state = {
        "version": STATE_VERSION,
        "goal": goal,
        "baseline_sha": baseline_sha,
        "last_verified_sha": None,
        "steps": {},
        "history": [],
        "decision": "not_ready",
    }
    write_state(path, state)
    return state


def verify_render_evidence(outdir: Path) -> dict:
    """Fail closed on skipped QA, missing video, or invalid encoding."""
    outdir = Path(outdir)
    report_path = outdir / "qa_report.json"
    video_path = outdir / "final.mp4"
    if not report_path.is_file() or not video_path.is_file():
        raise GateError("Required qa_report.json or final.mp4 is missing")
    if video_path.stat().st_size <= 0:
        raise GateError("final.mp4 is empty")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("semantic_required") is not True:
        raise GateError("Production semantic QA must be required and PASS")
    semantic = report.get("semantic_visual_qa", {}).get("results", [])
    if not semantic or any(r.get("status") != "PASS" for r in semantic):
        raise GateError("Every required semantic scene must be evaluated and PASS")
    if report.get("visual_qa", {}).get("structural_status") != "PASS":
        raise GateError("Visual structural QA did not PASS")
    final = report.get("final_video_qa", {})
    checks = final.get("checks", {})
    if final.get("status") != "PASS" or not checks or any(
        check.get("status") != "PASS" for check in checks.values()
    ):
        raise GateError("Final viewer-facing video QA did not PASS")
    subtitles = report.get("subtitle_reports", [])
    if not subtitles or any(item.get("status") != "PASS" for item in subtitles):
        raise GateError("Subtitle QA did not PASS")
    if report.get("captions", {}).get("status") != "PASS":
        raise GateError("Caption export QA did not PASS")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration",
         "-of", "json", str(video_path)],
        check=True, capture_output=True, text=True,
    )
    metadata = json.loads(probe.stdout)
    streams = metadata.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video or not audio or video.get("codec_name") != "h264" or audio.get("codec_name") != "aac":
        raise GateError("final.mp4 must include H.264 video and AAC audio")
    if (video.get("width"), video.get("height")) != (1080, 1920):
        raise GateError("final.mp4 must be 1080x1920")
    try:
        num, den = map(int, video["r_frame_rate"].split("/"))
        fps = num / den
        duration = float(metadata["format"]["duration"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise GateError("Invalid MP4 frame rate or duration") from exc
    if fps < 30 or duration <= 1:
        raise GateError("Insufficient final MP4 frame rate or duration")
    return {
        "report": str(report_path),
        "video": str(video_path),
        "semantic_scenes": len(semantic),
        "final_checks": len(checks),
        "fps": fps,
        "duration": duration,
    }


def run_stage(
    path: Path, stage: str, *, head_sha: str, project: str = "examples/comet.json",
    outdir: Path = Path("dist"),
) -> dict:
    """One bounded attempt per call; safely resume after an interrupted process.

    A file lock prevents competing agents from executing the same phase.
    The lock is released by the OS if the supervisor process is killed.
    """
    if stage not in STAGES:
        raise GateError("Unknown stage")
    _require_sha(head_sha)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / (path.name + ".lock")).open("a+") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        if state["baseline_sha"] != head_sha or current_head() != head_sha:
            raise GateError("HEAD changed: create a new baseline and rerun all gates")
        if stage == "render":
            tests = state["steps"].get("tests", {})
            if tests.get("status") != "PASS" or tests.get("sha") != head_sha:
                raise GateError("Successful full regression on this exact HEAD is required")
        prior = state["steps"].get(stage, {})
        if prior.get("status") == "RUNNING":
            state["history"].append({"stage": stage, "result": "INTERRUPTED"})
        attempts = int(prior.get("attempts", 0))
        if attempts >= MAX_ATTEMPTS:
            raise GateError("Retry budget exhausted; diagnose before a fresh baseline")
        state["steps"][stage] = {
            "status": "RUNNING", "sha": head_sha, "attempts": attempts + 1,
        }
        # A new verification run invalidates any earlier acceptance for this SHA.
        # Preserve external known-good artifacts; only revoke this candidate's approval.
        state["decision"] = "not_ready"
        if state.get("last_verified_sha") == head_sha:
            state["last_verified_sha"] = None
        write_state(path, state)
        started = time.time()
        cmd = (
            [sys.executable, "-m", "pytest", "-q"] if stage == "tests" else
            [sys.executable, "-m", "shorts_studio", "render", project]
        )
        environment = os.environ.copy()
        if stage == "render":
            environment["SHORTS_REQUIRE_SEMANTIC_QA"] = "1"
        proof = None
        try:
            result = subprocess.run(cmd, check=False, env=environment)
            if result.returncode != 0:
                raise GateError(f"{stage} command exited with {result.returncode}")
            if stage == "render":
                for filename in ("final.mp4", "qa_report.json"):
                    item = Path(outdir) / filename
                    if not item.exists() or item.stat().st_mtime + 2 < started:
                        raise GateError(f"{filename} was not generated by this run")
                proof = verify_render_evidence(outdir)
            status, error = "PASS", None
        except (OSError, ValueError, GateError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
            status, error = "FAIL", str(exc)
        state["steps"][stage].update(status=status, error=error, proof=proof)
        state["history"].append({"stage": stage, "result": status, "sha": head_sha})
        if stage == "render" and status == "PASS":
            state["decision"] = "awaiting_human_video_review"
        write_state(path, state)
        if status != "PASS":
            raise GateError(error or "Gate failed")
        return state


def record_review(path: Path, *, head_sha: str, outcome: str, notes: str) -> dict:
    """Explicit reviewer decision only. Never publishes or merges."""
    if outcome not in ("pass", "fail") or not notes.strip():
        raise GateError("Explicit pass/fail and substantive review notes are required")
    state = read_state(path)
    render = state["steps"].get("render", {})
    if state["baseline_sha"] != head_sha or current_head() != head_sha:
        raise GateError("Review SHA does not match the tested baseline")
    if render.get("status") != "PASS" or render.get("sha") != head_sha:
        raise GateError("Cannot review without real passing render evidence")
    tests = state["steps"].get("tests", {})
    if tests.get("status") != "PASS" or tests.get("sha") != head_sha:
        raise GateError("Current full regression on this HEAD must PASS before review")
    if state.get("decision") not in (
        "awaiting_human_video_review", "reviewed_pass", "reviewed_fail"
    ):
        raise GateError("Candidate is not ready for human video review")
    if outcome == "pass" and state["decision"] == "reviewed_fail":
        raise GateError("Failed human review requires a fresh verified render")
    state["decision"] = "reviewed_pass" if outcome == "pass" else "reviewed_fail"
    if outcome == "pass":
        state["last_verified_sha"] = head_sha
    elif state.get("last_verified_sha") == head_sha:
        # A later rejection must revoke approval of this exact candidate.
        # Otherwise a stale last_verified_sha could authorize a failed video.
        state["last_verified_sha"] = None
    state["history"].append({"stage": "human_review", "result": outcome, "notes": notes})
    write_state(path, state)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path(".nightshift/devloop.json"))
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init")
    init.add_argument("--goal", required=True)
    commands.add_parser("status")
    commands.add_parser("run-tests")
    render = commands.add_parser("run-render")
    render.add_argument("--project", default="examples/comet.json")
    render.add_argument("--outdir", type=Path, default=Path("dist"))
    review = commands.add_parser("review")
    review.add_argument("--result", choices=("pass", "fail"), required=True)
    review.add_argument("--notes", required=True)
    args = parser.parse_args()
    try:
        if args.action == "init":
            state = initialize(args.state, baseline_sha=current_head(), goal=args.goal)
        elif args.action == "status":
            state = read_state(args.state)
        elif args.action in ("run-tests", "run-render"):
            stage = "tests" if args.action == "run-tests" else "render"
            state = run_stage(
                args.state, stage, head_sha=current_head(),
                project=getattr(args, "project", "examples/comet.json"),
                outdir=getattr(args, "outdir", Path("dist")),
            )
        else:
            state = record_review(
                args.state, head_sha=current_head(),
                outcome=args.result, notes=args.notes,
            )
    except (GateError, FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        print(f"NOT READY: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
