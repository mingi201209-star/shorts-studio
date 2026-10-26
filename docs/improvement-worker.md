# Persistent Shorts improvement worker (foundation)

Run this under a dedicated server account using `systemd` with `Restart=on-failure`
and a persistent SQLite path. It is currently **not deployed**. The worker
invokes an external adapter every interval, records verified versions, and
stops only when the current candidate hash is explicitly approved. A failed
adapter, missing video, failed QA/CI or detected regression blocks the campaign
until its root cause is fixed and `resume` is called. The service stays alive,
but blocked work is never reported as active improvement.

```bash
python -m shorts_studio.improvement_worker --database /var/lib/shorts-improvement/state.db run --interval 300 --timeout 3600 /opt/shorts-improvement/adapter
python -m shorts_studio.improvement_worker --database /var/lib/shorts-improvement/state.db status
python -m shorts_studio.improvement_worker --database /var/lib/shorts-improvement/state.db approve ACTUAL_VERIFIED_SHA256
```

Adapter stdin: `{ "iteration": 1, "last_good_sha": null, "previous_candidate_sha": null }`.
It must return JSON containing the lowercase SHA256 of the exact review video,
an absolute `video_path` and independently verified booleans `qa_pass=true`,
`ci_pass=true`, `regression=false`. It must itself verify source/main/PR status,
render real media, compare visual and audio quality, poll CI to terminal, and
restore the last good code when quality regresses. The worker does not grant
deployment, publication, purchasing or merge authority. An adapter that falsely
claims verification defeats this boundary; production requires an audited
adapter which checks video hash and CI receipts rather than trusting claims.

The next integration step is to connect the existing Shorts Studio production
and quality reports to that adapter, then deploy and verify `systemd` restart on
the user's existing server. SSH access to the existing Ubuntu server was
verified using its already running phone SSH agent; the reviewed branch is
checked out in an isolated server worktree and its eight tests pass there.
The existing server has no Blender binary or GitHub CLI/credential helper and
the existing Hermes controller only runs mock jobs. `deploy/systemd/shorts-improvement.service`
is intentionally gated on the adapter executable existing; it must not be
enabled until real media and CI receipts can be verified end to end.

## Fail-closed one-shot adapter

`python -m shorts_studio.improvement_adapter --config /absolute/operator-config.json`
implements the worker stdin/stdout protocol. Configuration and human-review inbox
must be operator-owned, outside the candidate sandbox. Run as a dedicated account
with Codex workspace-write sandbox support; do not grant extra writable roots,
network access, hooks, upload credentials, or privileged execution to the editor.
The source checkout must be clean. A separate local clone has its origin removed;
rejected clones are quarantined, never copied back into source. A verified result
also does not promote source. This is an asset/manifest improvement adapter:
only explicit `examples/` and `assets/` JSON/image paths may be edited. Changes to
Python, tests, workflows, deleted inputs, or candidate history block the attempt.

Example operator configuration (paths and task must be chosen for the campaign):

```json
{
  "repository": "/srv/shorts-studio",
  "evidence_root": "/var/lib/shorts-improvement/campaign-001",
  "max_attempts": 24,
  "timeout_seconds": 3300,
  "task": "Improve the selected manifest and assets using the supplied editorial brief.",
  "editable_paths": ["examples/selected.json"],
  "render_command": ["/srv/venv/bin/python", "-m", "shorts_studio", "render", "examples/selected.json"],
  "baseline_video_sha256": "REPLACE_WITH_ACTUAL_BASELINE_SHA256",
  "human_review": "/var/lib/shorts-review/current.json",
  "github_repository": "owner/repository",
  "required_checks": ["REPLACE_WITH_EXACT_REQUIRED_RENDER_CHECK_NAME"]
}
```

Set `SHORTS_REQUIRE_SEMANTIC_QA=1` in the adapter environment. Validate the exact
render command against the selected project before activation. Each process has
at most 1800 seconds and the entire subprocess sequence at most the configured
3600-second ceiling. Timeout kills the process group. The persistent atomic
`attempt-NNNN` claim prevents rerunning an iteration, including after crashes or
worker `resume`; investigate failures rather than deleting claims. Use a fresh,
explicitly reviewed campaign directory for a new campaign. The outer worker
must have a longer timeout than the adapter, allowing evidence finalization.

The model's entire checkout is archived separately; a pristine clone of the
candidate commit and a fresh operator command
must produce the local MP4 and QA report. ffprobe validates audiovisual MP4
streams and ffmpeg decodes the entire file. The adapter hashes the actual bytes,
requires every mandatory final-video gate, all semantic scenes and subtitles to
PASS, rejects unresolved editorial states, and checks all returned GitHub check
runs and commit statuses on the exact candidate source commit. Empty, paginated,
missing required checks, pending, skipped, neutral or failed results block; there
is one bounded query per endpoint, no polling or automatic reattempt. Logs,
commands, stdout/stderr, source diff, candidate clone, model output, review proof
and outcome remain in the evidence directory. These may contain sensitive data;
restrict directory access and plan disk retention externally.

Human review JSON must contain `commit_sha`, `video_sha256`, `qa_sha256`,
`baseline_video_sha256`, `decision: "PASS"`, `regression: false`, `reviewer`,
`reviewed_at`, `visual_notes`, `audio_notes`, `proof_path`, and `proof_sha256`.
Proof must be a real review artifact outside the model workspace. The reviewer
must inspect the exact video and compare it to the baseline, supplying evidence
for both visual and audio quality before verification reaches the review gate.
The adapter verifies bindings and presence; it cannot authenticate a human's
identity or judge whether their written claims are truthful. Protect this inbox
with a separate trusted review process. It never manufactures a review.

Before 24-hour activation, still required:

* Install and verify sandboxed Codex, rendering/semantic dependencies, ffmpeg,
  ffprobe, and read-only authenticated `gh` on the target server.
* Select real baseline media, its SHA256, explicit editable inputs, the trusted
  render command, exact required CI check names, and a bounded campaign policy.
* Establish the external human visual/audio comparison and proof handoff.
* Arrange independently authorized CI for the **exact local candidate commit**.
  This adapter never pushes or dispatches workflows; a commit absent from GitHub
  will fail closed. No CI receipt is synthesized to bridge this gap.
* Run a real end-to-end canary with actual MP4, local QA, human proof and terminal
  exact-commit CI; test rejection, timeout recovery, evidence retention and service
  restart on the target host. Then separately authorize service enablement and
  a 24-hour monitored run. Nothing here starts the daemon, uploads to YouTube,
  merges, pushes, or publishes.
