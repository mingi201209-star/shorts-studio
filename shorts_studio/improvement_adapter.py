"""Fail-closed, one-shot adapter. Evidence is retained; source is never promoted."""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

MANDATORY = frozenset(
    [
        "composition_9x16",
        "scenes_present",
        "visual_cut_cadence",
        "no_semantic_skip",
        "narration_continuity",
        "visual_activity_real",
        "meaningful_visual_changes",
        "no_black_opening",
        "source_reuse",
        "global_source_reuse",
        "visual_novelty",
        "first_5s_coverage",
        "ending_novelty",
        "title_visible",
        "captions_visible",
        "safe_area_clean",
        "picture_caption_gutter",
    ]
)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text())


def validate_qa(report):
    require(report["status"] == "PASS", "local QA failed")
    require(report["semantic_required"] is True, "semantic QA not required")
    require(report["visual_qa"]["structural_status"] == "PASS", "structural QA failed")
    semantic = report["semantic_visual_qa"]
    require(semantic["status"] == "PASS" and semantic["results"], "missing semantic evaluation")
    require(
        all(x["status"] == "PASS" for x in semantic["results"]), "skipped/failed semantic scene"
    )
    require(
        report["subtitle_reports"]
        and all(x["status"] == "PASS" for x in report["subtitle_reports"]),
        "subtitle QA missing/failed",
    )
    final = report["final_video_qa"]
    require(final["status"] == "PASS", "final video QA failed")
    require(MANDATORY <= final["checks"].keys(), "mandatory video gates missing")
    require(
        all(x["status"] == "PASS" for x in final["checks"].values()), "skipped/failed video gate"
    )

    # Optional editorial layers become mandatory when present. Never accept HOLD.
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("status", "editorial_status", "decision"):
                    require(
                        child
                        not in (
                            "HOLD",
                            "FAIL",
                            "SKIP",
                            "SKIPPED",
                            "NOT_EVALUATED",
                            "REQUIRES_VISUAL_REVIEW",
                        ),
                        "unresolved QA/editorial review",
                    )
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(report)


def validate_ci(data, sha, required):
    require(data.get("total_count") == len(data.get("check_runs", [])), "CI pagination incomplete")
    runs = data["check_runs"]
    require(runs and required, "no required CI checks")
    require(set(required) <= {x["name"] for x in runs}, "required CI checks missing")
    require(
        all(
            x["head_sha"] == sha and x["status"] == "completed" and x["conclusion"] == "success"
            for x in runs
        ),
        "CI not terminal success on exact commit",
    )


class Runner:
    def __init__(self, evidence, seconds):
        self.evidence = evidence
        self.deadline = time.monotonic() + seconds
        self.index = 0

    def __call__(self, argv, cwd, stdin=None):
        self.index += 1
        prefix = self.evidence / f"process-{self.index:03}"
        prefix.with_suffix(".json").write_text(
            json.dumps({"argv": argv, "cwd": str(cwd), "stdin": stdin})
        )
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "attempt budget exhausted")
        with (
            prefix.with_suffix(".stdout").open("w+") as out,
            prefix.with_suffix(".stderr").open("w") as err,
        ):
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                text=True,
                start_new_session=True,
            )
            try:
                proc.communicate(stdin, timeout=min(remaining, 1800))
            except BaseException:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                raise
            require(proc.returncode == 0, f"process failed: {argv[0]} ({proc.returncode})")
            out.seek(0)
            return out.read()


def attempt(config, job, run_factory=Runner):
    repo = Path(config["repository"]).resolve()
    root = Path(config["evidence_root"]).resolve()
    require(not root.is_relative_to(repo), "evidence must be outside source repository")
    require(
        type(job["iteration"]) is int and 1 <= job["iteration"] <= config["max_attempts"] <= 24,
        "attempt limit exceeded",
    )
    require(1 <= config["timeout_seconds"] <= 3600, "invalid time budget")
    # Atomic persistent claim: crashed/rejected jobs cannot be executed twice, even after resume.
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    evidence = root / f"attempt-{job['iteration']:04}"
    evidence.mkdir(mode=0o700)
    run = run_factory(evidence, config["timeout_seconds"])
    workspace = evidence / "workspace"
    result = {"state": "rejected", "evidence_path": str(evidence)}
    try:
        (evidence / "job.json").write_text(json.dumps(job))
        baseline = config["baseline_video_sha256"]
        require(
            isinstance(baseline, str)
            and len(baseline) == 64
            and all(c in "0123456789abcdef" for c in baseline),
            "invalid baseline SHA256",
        )
        require(
            not Path(config["human_review"]).resolve().is_relative_to(evidence),
            "review inbox must be outside attempt",
        )
        require(
            not run(["git", "status", "--porcelain"], repo).strip(), "source checkout must be clean"
        )
        base = run(["git", "rev-parse", "HEAD"], repo).strip()
        run(["git", "clone", "--no-hardlinks", "--no-local", str(repo), str(workspace)], root)
        run(["git", "remote", "remove", "origin"], workspace)
        run(["git", "checkout", "--detach", base], workspace)
        prompt = (
            config["task"]
            + "\nEdit and render exactly one candidate in this checkout. Do not push, upload, merge, or start services. Do not modify QA implementations, tests, workflows, or fabricate reviews. Leave edits uncommitted. Produce dist/final.mp4 and dist/qa_report.json with production semantic QA enabled. Human review is supplied independently."
        )
        run(
            [
                "codex",
                "exec",
                "--ignore-user-config",
                "--sandbox",
                "workspace-write",
                "-c",
                'approval_policy="never"',
                "-c",
                "sandbox_workspace_write.network_access=false",
                "--json",
                "-",
            ],
            workspace,
            prompt,
        )
        # Operator allowlist prevents candidate changes to the verifier, workflows and arbitrary code.
        require(
            run(["git", "rev-parse", "HEAD"], workspace).strip() == base,
            "editor changed commit history",
        )
        changed = run(
            ["git", "ls-files", "--modified", "--deleted", "--others", "--exclude-standard"],
            workspace,
        ).splitlines()
        require(
            not run(["git", "diff", "--cached", "--name-only"], workspace).strip(),
            "editor staged source changes",
        )
        allowed = config["editable_paths"]
        require(
            changed and all(p in allowed or p.startswith("dist/") for p in changed),
            "source changes outside explicit allowlist",
        )
        require(
            allowed
            and all(
                p.startswith(("examples/", "assets/"))
                and ".." not in Path(p).parts
                and Path(p).suffix.lower() in (".json", ".png", ".jpg", ".jpeg", ".webp")
                for p in allowed
            ),
            "unsafe edit allowlist",
        )
        require(
            all(
                not (workspace / p).is_symlink()
                and (workspace / p).resolve().is_relative_to(workspace)
                for p in allowed
            ),
            "symlinked editable input",
        )
        run(["git", "diff", "--binary"], workspace)  # retained before any rejection
        run(["git", "add", "--", *allowed], workspace)
        run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=Shorts adapter",
                "-c",
                "user.email=shorts-adapter@localhost",
                "commit",
                "-m",
                "Isolated Shorts candidate",
            ],
            workspace,
        )
        commit = run(["git", "rev-parse", "HEAD"], workspace).strip()
        require(commit != base and len(commit) == 40, "candidate source commit missing")
        committed_paths = run(["git", "diff", "--name-only", base, commit], workspace).splitlines()
        require(
            committed_paths and all(p in allowed for p in committed_paths),
            "candidate commit escaped allowlist",
        )
        # Retain every model artifact, then render from a pristine candidate clone.
        editor_workspace = evidence / "editor-workspace"
        workspace.rename(editor_workspace)
        run(
            ["git", "clone", "--no-hardlinks", "--no-local", str(editor_workspace), str(workspace)],
            root,
        )
        run(["git", "remote", "remove", "origin"], workspace)
        run(["git", "checkout", "--detach", commit], workspace)
        render_command = config["render_command"]
        require(
            isinstance(render_command, list) and render_command, "trusted render command required"
        )
        run(render_command, workspace)
        require(
            not run(["git", "diff", "HEAD", "--name-only"], workspace).strip(),
            "renderer changed tracked source",
        )
        video = workspace / "dist/final.mp4"
        qa = workspace / "dist/qa_report.json"
        require(
            video.is_file() and not video.is_symlink() and qa.is_file() and not qa.is_symlink(),
            "missing local media/QA",
        )
        video_sha = digest(video)
        require(
            video_sha
            not in (
                job.get("previous_candidate_sha"),
                job.get("last_good_sha"),
                config["baseline_video_sha256"],
            ),
            "unchanged video",
        )
        probe = json.loads(
            run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_format",
                    "-show_streams",
                    "-of",
                    "json",
                    str(video),
                ],
                workspace,
            )
        )
        require(
            "mp4" in probe["format"]["format_name"].split(",")
            and float(probe["format"]["duration"]) > 0
            and any(s["codec_type"] == "video" for s in probe["streams"])
            and any(s["codec_type"] == "audio" for s in probe["streams"]),
            "not an actual audiovisual MP4",
        )
        run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"], workspace)
        report = load(qa)
        validate_qa(report)
        require((workspace / report["output"]).resolve() == video.resolve(), "QA output mismatch")
        # Trusted review inbox is outside the model-writable workspace. Hashes prevent stale approval.
        review = load(Path(config["human_review"]))
        require(
            review["commit_sha"] == commit
            and review["video_sha256"] == video_sha
            and review["qa_sha256"] == digest(qa),
            "human proof not bound to candidate",
        )
        require(
            review["decision"] == "PASS"
            and review["regression"] is False
            and review["baseline_video_sha256"] == config["baseline_video_sha256"],
            "human HOLD/regression",
        )
        require(
            review["reviewer"]
            and review["reviewed_at"]
            and review["visual_notes"]
            and review["audio_notes"],
            "missing human visual/audio proof",
        )
        proof = Path(review["proof_path"]).resolve()
        require(
            not proof.is_relative_to(workspace)
            and proof.is_file()
            and digest(proof) == review["proof_sha256"],
            "missing human visual proof artifact",
        )
        (evidence / "human-review.json").write_text(json.dumps(review))
        shutil.copyfile(proof, evidence / "human-proof")
        ci = json.loads(
            run(
                [
                    "gh",
                    "api",
                    f"repos/{config['github_repository']}/commits/{commit}/check-runs?per_page=100",
                ],
                repo,
            )
        )
        validate_ci(ci, commit, config["required_checks"])
        statuses = json.loads(
            run(
                [
                    "gh",
                    "api",
                    f"repos/{config['github_repository']}/commits/{commit}/status?per_page=100",
                ],
                repo,
            )
        )
        require(
            statuses["sha"] == commit and statuses["total_count"] == len(statuses["statuses"]),
            "commit statuses incomplete or wrong SHA",
        )
        require(
            all(x["state"] == "success" for x in statuses["statuses"]),
            "commit status not successful",
        )
        require(digest(video) == video_sha, "video changed during verification")
        result.update(
            state="verified",
            candidate_sha=video_sha,
            candidate_commit_sha=commit,
            video_path=str(video),
            qa_pass=True,
            ci_pass=True,
            regression=False,
        )
        return result
    except BaseException as exc:
        result["failure"] = str(exc)
        raise
    finally:
        # Quarantine is rollback: no changes are ever copied into the source checkout.
        (evidence / "result.json").write_text(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(attempt(load(args.config), json.load(sys.stdin))))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
