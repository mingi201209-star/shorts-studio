"""Fail-closed, one-shot adapter. Evidence is retained; source is never promoted."""

import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
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
        "no_black_opening",
        "source_reuse",
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

    # The production semantic provider marks optional per-beat subtests
    # NOT_EVALUATED while the required scene and beat verdicts PASS.
    # The CI contract checks required scene verdicts; never promote a failed
    # or held nested verdict, and reject skips outside optional subtests.
    def walk(value, optional_subtest=False):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("status", "editorial_status", "decision"):
                    blocked = {"HOLD", "FAIL", "SKIP", "SKIPPED", "REQUIRES_VISUAL_REVIEW"}
                    if not optional_subtest:
                        blocked.add("NOT_EVALUATED")
                    require(child not in blocked, "unresolved QA/editorial review")
                walk(child, optional_subtest or key == "sub_results")
        elif isinstance(value, list):
            for child in value:
                walk(child, optional_subtest)

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


class BudgetExhausted(ValueError):
    pass


def reserve(config, job, root):
    """Charge worst-case authorized spend/time before any external work; never refund."""
    require(type(job["iteration"]) is int and job["iteration"] > 0, "invalid iteration")
    for key in (
        "max_attempts_per_day",
        "max_cost_microusd_per_day",
        "max_seconds_per_day",
        "attempt_cost_microusd",
        "timeout_seconds",
    ):
        require(type(config[key]) is int and config[key] > 0, f"invalid {key}")
    require(config["max_attempts_per_day"] <= 24, "daily attempt ceiling is 24")
    require(
        config["timeout_seconds"] <= min(3600, config["max_seconds_per_day"]), "invalid time budget"
    )
    require(
        config["attempt_cost_microusd"] <= config["max_cost_microusd_per_day"],
        "attempt cost exceeds daily ceiling",
    )
    require(
        config["paid_execution"] is False,
        "paid execution unsupported: no provider-enforced monetary cap",
    )
    require(config["push_authorized"] is True, "draft push authorization required")
    require(
        re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["github_repository"]),
        "invalid repository",
    )
    require(
        re.fullmatch(r"shorts-draft/[a-z0-9-]+", config["draft_branch_prefix"]),
        "unsafe draft branch prefix",
    )
    for key in ("review_command", "render_command", "editor_command"):
        require(
            isinstance(config[key], list)
            and config[key]
            and all(isinstance(x, str) and x for x in config[key]),
            f"missing {key}",
        )
    require(
        config["required_checks"]
        and all(isinstance(x, str) and x for x in config["required_checks"]),
        "required CI names missing",
    )
    require(
        type(config["ci_timeout_seconds"]) is int
        and 1 <= config["ci_timeout_seconds"] <= config["timeout_seconds"],
        "invalid CI bound",
    )
    # Local-only commands must have no metered API credentials/network. This is an
    # operator trust boundary, like the renderer; do not substitute a paid CLI.
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with sqlite3.connect(root / "budget.sqlite3", timeout=30) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS reservations (iteration INTEGER PRIMARY KEY, "
            "created REAL, cost INTEGER, seconds INTEGER)"
        )
        db.execute("CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY, digest TEXT)")
        db.execute("BEGIN IMMEDIATE")
        policy = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        old = db.execute("SELECT digest FROM policy WHERE id=1").fetchone()
        require(
            old is None or old[0] == policy, "campaign configuration changed; new campaign required"
        )
        db.execute("INSERT OR IGNORE INTO policy VALUES(1,?)", (policy,))
        count, cost, seconds = db.execute(
            "SELECT count(*),coalesce(sum(cost),0),coalesce(sum(seconds),0) "
            "FROM reservations WHERE created > ?",
            (time.time() - 86400,),
        ).fetchone()
        if count >= config["max_attempts_per_day"]:
            raise BudgetExhausted("rolling day attempts exhausted")
        if cost + config["attempt_cost_microusd"] > config["max_cost_microusd_per_day"]:
            raise BudgetExhausted("rolling day cost exhausted")
        if seconds + config["timeout_seconds"] > config["max_seconds_per_day"]:
            raise BudgetExhausted("rolling day time exhausted")
        db.execute(
            "INSERT INTO reservations VALUES(?,?,?,?)",
            (
                job["iteration"],
                time.time(),
                config["attempt_cost_microusd"],
                config["timeout_seconds"],
            ),
        )


def handoff(config, commit, workspace, repo, evidence, run):
    """One create-only push; ambiguous outcomes are quarantined, never retried."""
    remote = f"https://github.com/{config['github_repository']}.git"
    branch = f"{config['draft_branch_prefix']}/attempt-{evidence.name.removeprefix('attempt-')}"
    ref = f"refs/heads/{branch}"
    require(not run(["git", "ls-remote", remote, ref], repo).strip(), "draft ref already exists")
    with (evidence / "push-intent.json").open("x") as stream:
        json.dump({"commit": commit, "ref": ref, "remote": remote}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "push",
            "--porcelain",
            f"--force-with-lease={ref}:",
            remote,
            f"{commit}:{ref}",
        ],
        workspace,
    )
    require(
        run(["git", "ls-remote", remote, ref], repo).strip() == f"{commit}\t{ref}",
        "remote draft SHA mismatch",
    )
    deadline = min(
        time.monotonic() + config["ci_timeout_seconds"], getattr(run, "deadline", float("inf"))
    )
    while True:
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
        require(ci.get("total_count") == len(ci.get("check_runs", [])), "CI pagination incomplete")
        require(all(x["head_sha"] == commit for x in ci["check_runs"]), "wrong CI SHA")
        require(
            not any(
                x["status"] == "completed" and x["conclusion"] != "success"
                for x in ci["check_runs"]
            ),
            "CI rejected candidate",
        )
        require(
            all(x["state"] in ("pending", "success") for x in statuses["statuses"]),
            "commit status failed",
        )
        try:
            validate_ci(ci, commit, config["required_checks"])
            require(all(x["state"] == "success" for x in statuses["statuses"]), "status pending")
            break
        except ValueError:
            require(time.monotonic() < deadline, "CI timeout")
            time.sleep(min(5, max(0, deadline - time.monotonic())))
    require(
        run(["git", "ls-remote", remote, ref], repo).strip() == f"{commit}\t{ref}",
        "remote draft moved during CI",
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
    try:
        reserve(config, job, root)
    except BudgetExhausted as exc:
        return {"state": "deferred", "failure": str(exc)}
    except sqlite3.IntegrityError:
        return {"state": "rejected", "failure": "attempt already claimed; no replay"}
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
            not run(["git", "status", "--porcelain"], repo).strip(), "source checkout must be clean"
        )
        source = repo
        if job.get("previous_source"):
            source = Path(job["previous_source"]).resolve()
            require(
                source.is_relative_to(root) and source.name == "workspace" and source != workspace,
                "previous source outside campaign",
            )
            require(
                not run(["git", "status", "--porcelain", "--untracked-files=no"], source).strip(),
                "previous candidate source changed",
            )
        base = run(["git", "rev-parse", "HEAD"], source).strip()
        if source != repo:
            require(base == job["previous_commit"], "previous commit mismatch")
        run(["git", "clone", "--no-hardlinks", "--no-local", str(source), str(workspace)], root)
        run(["git", "remote", "remove", "origin"], workspace)
        run(["git", "checkout", "--detach", base], workspace)
        prompt = (
            config["task"]
            + "\nEdit and render exactly one candidate in this checkout. Do not push, upload, merge, or start services. Do not modify QA implementations, tests, workflows, or fabricate reviews. Leave edits uncommitted. Produce dist/final.mp4 and dist/qa_report.json with production semantic QA enabled. Automated internal review is supplied independently; human approval is final only."
        )
        run(
            [
                "bwrap",
                "--die-with-parent",
                "--unshare-net",
                "--unshare-pid",
                "--new-session",
                "--ro-bind",
                "/",
                "/",
                "--bind",
                str(workspace),
                str(workspace),
                "--tmpfs",
                "/tmp",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--chdir",
                str(workspace),
                "--",
                *config["editor_command"],
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
        require(
            commit != base and re.fullmatch(r"[0-9a-f]{40}", commit),
            "candidate source commit missing",
        )
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
        # Trusted local reviewer runs after the editor exits, from the source
        # checkout, and receives exact immutable bindings. It may reject freely.
        binding = {
            "commit_sha": commit,
            "video_sha256": video_sha,
            "qa_sha256": digest(qa),
            "baseline_video_sha256": baseline,
            "comparison_video_sha256": job.get("last_good_sha") or baseline,
            "comparison_video_path": job.get("previous_video_path"),
            "video_path": str(video),
            "qa_path": str(qa),
        }
        if binding["comparison_video_path"]:
            require(
                digest(Path(binding["comparison_video_path"]))
                == binding["comparison_video_sha256"],
                "previous verified video changed",
            )
        review = json.loads(run(config["review_command"], repo, json.dumps(binding)))
        (evidence / "internal-review.json").write_text(json.dumps(review))
        require(
            all(
                review[k] == binding[k]
                for k in (
                    "commit_sha",
                    "video_sha256",
                    "qa_sha256",
                    "baseline_video_sha256",
                    "comparison_video_sha256",
                )
            ),
            "internal review binding mismatch",
        )
        require(
            review["decision"] == "PASS"
            and review["regression"] is False
            and review["visual_notes"]
            and review["audio_notes"],
            "internal review rejected",
        )
        require(
            digest(video) == video_sha and digest(qa) == binding["qa_sha256"],
            "review changed artifacts",
        )
        handoff(config, commit, workspace, repo, evidence, run)
        require(digest(video) == video_sha, "video changed during verification")
        result.update(
            state="verified",
            candidate_sha=video_sha,
            candidate_commit_sha=commit,
            video_path=str(video),
            source_path=str(workspace),
            qa_pass=True,
            ci_pass=True,
            regression=False,
        )
        return result
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        result["failure"] = str(exc)
        return result
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
