# Bounded unattended Shorts improvement

The adapter is proposed in draft PR #82. The service remains disabled and has not been deployed. The adapter
supports autonomous intermediate iterations; human approval is exclusively
`improvement_worker approve EXACT_VIDEO_SHA256`. Approval rehashes the current
verified video before accepting it. There is no merge, release, upload, publication,
or service enablement operation in this path.

The trusted controller invokes a local editor in a bubblewrap namespace with no
network and a read-only host filesystem except its isolated checkout and temporary
files. The operator must supply a local, unmetered editor; paid execution fails
closed because this repository has no provider-enforced monetary cap. After edits,
only explicitly allowed JSON/images in examples/assets are committed. The editor's
entire checkout is retained. A pristine clone of that commit is rendered using an
operator command, decoded with ffmpeg, checked with ffprobe, and required to pass
all structural, semantic, subtitle, and final-video gates. Trusted commands must be
operator-owned and must not invoke candidate-provided executables or metered APIs.

A separate automated review command runs from the trusted source checkout. It reads
JSON on stdin with `commit_sha`, `video_sha256`, `qa_sha256`,
`baseline_video_sha256`, `comparison_video_sha256`, `comparison_video_path`,
`video_path`, and `qa_path`. The comparison is the last verified candidate when
available, otherwise the configured baseline (whose media the reviewer must know). It must inspect the actual
video and compare visual/audio quality with the baseline. Its JSON stdout repeats
the five hash bindings and contains `decision: "PASS"`, `regression: false`,
nonempty `visual_notes`, and `audio_notes` to pass. Any other decision rejects the
attempt and the controller continues without a human. This interface does not
invent a production quality comparator: an audited local implementation is still
required. Missing commands/configuration block the campaign.

Only after trusted rendering, QA and internal review does the adapter perform one
create-only push to `shorts-draft/CAMPAIGN/attempt-NNNN` at the explicitly authorized
GitHub repository. An empty force-with-lease prevents overwriting any existing ref.
A durable push intent precedes the single push. The remote ref is checked against
the exact local commit before and after bounded CI polling. Every returned check
must be successful and terminal on that commit, all configured required names must
exist, all commit statuses must succeed, and incomplete pagination fails closed.
No candidate registers before those checks. Failed or ambiguous pushes are never
retried for that attempt. Draft refs remain as evidence after rejection.

`shorts-draft.yml` provides a read-only, ten-minute `draft-test` job for these
branches. The existing general test/render push workflows exclude this namespace.
This check tests source; production media QA and review still run locally against
the pristine candidate. There is no CI media upload in this workflow. Branch policy,
other installed GitHub Apps and account billing/quota must be audited before use;
the adapter cannot enforce a GitHub account's dollar spend. Do not authorize paid
CI overages for this unmetered-only campaign.

Each attempt reserves its full worst-case local cost allowance and execution time
in a persistent SQLite ledger before any external command. Counts, time and cost
are capped over a rolling 86400 seconds, including failures and crashes, without
refunds. Daily exhaustion defers work until capacity returns. A consumed iteration
cannot run or push again after restart. Subprocesses share an attempt deadline and
are killed as a process group on timeout. The worker timeout must exceed that
deadline to permit evidence finalization. Use one worker per database/campaign.
Do not delete the budget ledger or reuse a campaign directory with different limits.

Verified iterations seed the next isolated clone from the previous exact source
commit. Rejected edits never become that seed. The original source checkout is
never changed: retaining/quarantining each rejected clone implements source
rollback. Commands, stdout/stderr, editor artifacts, source diff, pristine render,
internal review, CI responses, push intent and result remain under the private
evidence root. Storage retention must be provisioned separately.

Required operator configuration example (all values must be real and reviewed):

```json
{
  "repository": "/srv/shorts-studio",
  "evidence_root": "/var/lib/shorts-improvement/campaign-001",
  "max_attempts_per_day": 24,
  "max_seconds_per_day": 86400,
  "max_cost_microusd_per_day": 24000000,
  "attempt_cost_microusd": 1000000,
  "paid_execution": false,
  "timeout_seconds": 3300,
  "ci_timeout_seconds": 900,
  "push_authorized": true,
  "draft_branch_prefix": "shorts-draft/campaign-001",
  "github_repository": "owner/repository",
  "required_checks": ["draft-test"],
  "task": "Improve the selected manifest and assets using the editorial brief.",
  "editable_paths": ["examples/selected.json"],
  "editor_command": ["/opt/local-editor"],
  "render_command": ["/srv/venv/bin/python", "-m", "shorts_studio", "render", "examples/selected.json"],
  "review_command": ["/opt/local-video-review"],
  "baseline_video_sha256": "REPLACE_WITH_ACTUAL_BASELINE_SHA256"
}
```

The allowance is an authorization reservation, not a measurement of actual spend.
All metered execution is unsupported; using a paid CLI behind a trusted command
violates the execution contract. Configuration, commands and evidence ledger must
be outside the editor's writable namespace. The renderer must require semantic QA
(`SHORTS_REQUIRE_SEMANTIC_QA=1`); missing semantic evaluation cannot pass.

Run the adapter with `python -m shorts_studio.improvement_adapter --config CONFIG`.
It consumes the worker job on stdin and returns verified/rejected/deferred JSON.
The worker records rejections, advances iterations, retains the last verified
candidate and continues. Infrastructure/configuration errors block until repaired
and explicitly resumed; budget exhaustion does not require human intervention.

Before any activation, supply and audit the actual local editor, automated
visual/audio comparator, selected production manifest, baseline, runtime tools,
GitHub draft-branch permissions, quota and required checks. Server GitHub CLI login has been verified, but a candidate push has not. Run a real end-to-end canary
on the target host. These production components are not available/configured here;
there is no claim of successful unattended production rendering. Service enablement
and any candidate push remain untested. No service was enabled.
