# VPS Asset Controller Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed, durable, low-cost Shorts Studio task controller on the existing VPS, verify restart recovery with fake workers, and prove a safely gated Codex adapter without dispatching real rendering or paying for other services.

**Architecture:** Introduce an independent `shorts_studio/asset_factory/controller/` package that works against the currently verified `main` even though PR #51–56 Factory code remains unmerged. Python stdlib SQLite WAL handles idempotent queue state and fencing; a local checksum-verified object store and mock worker establish recovery correctness. A separately gated Codex subprocess adapter and optional systemd unit come last; live B2 and renderer workers are subsequent independently approved plans.

**Tech Stack:** Python >=3.11, stdlib `sqlite3`/`dataclasses`/`hashlib`/`json`/`subprocess`/`pathlib`, existing `pytest>=8` and `ruff>=0.6` via `pip install -e '.[dev]'`, Linux systemd and Ubuntu 24.04 on the *existing* OVHcloud VPS.

**Spec:** [Approved asset-factory design](../specs/2026-10-20-always-on-asset-factory-design.md), commit `952a3faca7a6254af9d81dbbb730b0ae6161bd55`. Read spec sections 1–8 before starting.

## Global Constraints

- The actual provisioned controller is OVHcloud VPS-1, Singapore, **2 vCore / 4 GiB / 40 GiB NVMe**, Ubuntu 24.04, displayed **USD 5.35/month**. It is a controller, **not** a high-throughput native Blender renderer.
- Existing `main` must remain intact; its verified starting SHA was `fcd20fd78851b18c550b1e433bee46ee34313c1d`. Refresh remote `main`, PR #51–56, and the branch status before implementation. The approved spec and this plan live on the `design/always-on-asset-factory-20261020` branch.
- Create **one clean, isolated worktree/branch** from the approved design+plan commit, after authorization to implement. Never edit the Android Nightshift's dirty PR #56 worktree or rewrite its checkpoint.
- Do not import or reimplement `shorts_studio.factory.contracts`/`planner` from draft PRs. The controller's identity fields must be compatible with their future hashes, but final Factory integration is a separate dependency-aware plan.
- Preserve the production contract unchanged: **1080×1920**, **30 fps**, **Cycles32**, **original unique native frames**, **English narration**, video/audio/caption quality gates. No frame interpolation, repeated filler, crop/zoom shortcuts, automatic YouTube upload, automatic merge, or `main` push.
- **No B2 bucket, GPU, VPS #2, paid model API, unattended `workflow_dispatch`, or external spend** in this pilot. The existing VPS purchase is not blanket approval for additional charges. Use a local storage double only.
- Keep SSH public-key-only access, the active UFW rule, and the enforced AppArmor/Bubblewrap sandbox. Never use `--dangerously-bypass-approvals-and-sandbox` or globally disable user namespace restrictions.
- Codex `codex-cli 0.163.0` was observed logged in using ChatGPT and completed scratch coding tests (**4/4**). Subscription refresh and unattended quota are **not** guaranteed; simulate limits before enabling any live Codex dispatch.
- Do not copy the phone's private SSH key, ChatGPT auth cache, cloud secrets or OTPs into the repository. No hard-coded public server address or customer/account identifiers in code, tests, logs or documentation.
- Source code, tests, and a unit-file *template* may be committed. A permanent service, automatic remote dispatch, production Codex worker, and 24-hour soak all require their own reviewed execution approval.

## Scope and File Map

This plan delivers **Milestone A: persisted controller + audited dry-run behavior**, plus a **disabled-by-default Codex adapter probe**. It does not claim to finish Milestone B (3D asset library), C (seven video candidates/week) or D (24-hour soak). Make separate plans for (1) PR #51–56 Factory integration and native video QA, (2) approved B2 storage/backups, and (3) distributed render workers after benchmark/budget review. The code is a new package, but not a new product/repository.

| Location | Single responsibility |
| --- | --- |
| `shorts_studio/asset_factory/__init__.py`, `controller/__init__.py` | Separate controller namespace from unmerged `shorts_studio/factory` |
| `shorts_studio/asset_factory/controller/contracts.py` | Strict, immutable job, claim and receipt records; input/digest validation |
| `shorts_studio/asset_factory/controller/database.py` | SQLite connection settings, WAL schema and migrations for pilot version 1 |
| `shorts_studio/asset_factory/controller/queue.py` | Atomic enqueue, claim, fencing, completion, blocked/uncertain transitions |
| `shorts_studio/asset_factory/controller/artifacts.py` | Local content-addressed staging and verified receipts (B2 filesystem double) |
| `shorts_studio/asset_factory/controller/recovery.py` | Reconciliation of expired leases and externally ambiguous results; checkpoint/snapshot |
| `shorts_studio/asset_factory/controller/workers.py` | Bounded deterministic mock worker; disabled-by-default Codex subprocess adapter |
| `shorts_studio/asset_factory/controller/runner.py` | One-cycle controller and explicit no-spend admission gates |
| `shorts_studio/asset_factory/controller/__main__.py` | Human-invoked `init`, `enqueue-mock`, `step`, `status`, `snapshot`, `recover` commands |
| `deploy/systemd/shorts-asset-controller.service` | Inert, reviewable mock-only service template; **do not install/enable it in this plan** |
| `tests/test_asset_controller_*.py` | Unit and local integration tests per task |
| `docs/operations/asset-controller-pilot.md` | Security, operator commands, rollback, incidents and out-of-scope policy |

**Existing files intentionally unchanged:** `shorts_studio/cli.py`, `shorts_studio/render.py`, `shorts_studio/final_video_qa.py`, `pyproject.toml` (already packages `shorts_studio*` and provides pytest/ruff), `.github/workflows/test.yml` (already runs `pytest -q`), `main` and all video assets.

## Review Focus

The top five easy-to-miss cases are explicitly covered in task tests:

1. **Identical `job_id` with changed source/input digest** must fail rather than silently reuse old frames — `test_duplicate_identity_conflict_rejected` (Task 2).
2. **Delayed old worker receipt after a new fencing token** must not mark the job complete — `test_stale_fencing_token_cannot_complete` (Task 2).
3. **Lease expiry with unknown external-worker status** must block safely, never relaunch a potentially billable render — `test_unknown_expired_job_is_blocked_without_retry` (Task 4).
4. **Corrupted or cross-job artifact with a valid-looking filename** must fail SHA256 and ownership verification, retaining the last verified copy — `test_corrupt_or_foreign_artifact_rejected` (Task 3).
5. **Codex returns code 0 but produced no file, had a quota failure, or has SHA drift** must be recorded as blocked/failed, not PASS — `test_zero_exit_without_receipt_is_not_success` and `test_quota_or_sha_drift_blocks` (Task 5).

---

### Task 1: Strict Contracts and Durable SQLite Schema

**Files:**
- Create: `shorts_studio/asset_factory/__init__.py`
- Create: `shorts_studio/asset_factory/controller/__init__.py`
- Create: `shorts_studio/asset_factory/controller/contracts.py`
- Create: `shorts_studio/asset_factory/controller/database.py`
- Test: `tests/test_asset_controller_contracts.py`
- Test: `tests/test_asset_controller_database.py`

**Interfaces:**
- Produces immutable `JobSpec(job_id: str, asset_id: str, asset_version: str, source_sha: str, input_digest: str, stage: str, worker_kind: str, payload_json: str, max_attempts: int = 2, budget_usd: str = "0")` and `Claim(job_id: str, source_sha: str, input_digest: str, owner: str, attempt: int, fencing_token: int, lease_until: float)`.
- Produces immutable `ArtifactReceipt(job_id: str, source_sha: str, input_digest: str, artifact_sha256: str, relative_path: str, byte_count: int)`.
- Produces `open_controller_db(path: Path) -> sqlite3.Connection` with schema version 1, tables `jobs`, `attempts`, `leases`, `receipts`, `events` and schema metadata. `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=FULL`; no external database dependency.
- Accept canonical lowercase 64-character SHA256 input digests and full lowercase 40-character Git source SHA. Fail on invalid JSON, path traversal, unknown job kinds (pilot: `mock` or `codex`), negative budgets or nonpositive attempt limits.

- [ ] **Step 1: Write failing contract and schema tests** — `test_bad_digests_and_payload_rejected`, `test_valid_mock_spec`, `test_schema_v1_and_wal_persist_after_reopen`, `test_unknown_schema_version_refused`; use `tmp_path` and assert five tables + metadata exist.
- [ ] **Step 2: Run targeted tests and observe RED** — `pytest -q tests/test_asset_controller_contracts.py tests/test_asset_controller_database.py`; expected import/behavior failure, not collection of unrelated product regressions.
- [ ] **Step 3: Implement the frozen contracts and `open_controller_db`** — validate before any write; increment schema only through an explicit versioned migration; do not infer workers or costs from free-form payload JSON.
- [ ] **Step 4: Run the same tests and observe GREEN** — expected all targeted tests pass. Also run `ruff check shorts_studio/asset_factory tests/test_asset_controller_contracts.py tests/test_asset_controller_database.py`.
- [ ] **Step 5: Commit isolated task** — `git add shorts_studio/asset_factory tests/test_asset_controller_contracts.py tests/test_asset_controller_database.py && git commit -m "feat(controller): add strict job contracts and durable schema"`.

### Task 2: Idempotent Queue, Leases and Fencing

**Files:**
- Create: `shorts_studio/asset_factory/controller/queue.py`
- Test: `tests/test_asset_controller_queue.py`

**Interfaces:**
- Consumes `JobSpec`, `Claim`, `ArtifactReceipt`, `open_controller_db` from Task 1.
- Produces `enqueue(conn: sqlite3.Connection, job: JobSpec) -> bool` (True = inserted, False = byte-identical job exists; identity conflict raises `ValueError`).
- Produces `claim_next(conn: sqlite3.Connection, owner: str, now: float, lease_seconds: float) -> Claim | None`, `complete_claim(conn: sqlite3.Connection, claim: Claim, receipt: ArtifactReceipt, now: float) -> bool`, `block_claim(conn: sqlite3.Connection, claim: Claim, reason: str, now: float) -> bool`. All mutating transitions occur in `BEGIN IMMEDIATE`; tokens increase monotonically; accepted completion checks full job/source/input identity and unexpired matching lease.
- Pilot admissions: only `worker_kind="mock"` is claimable automatically; `codex` jobs remain blocked until explicitly enabled later. An empty queue is normal, not a failure.

- [ ] **Step 1: Write failing tests** — `test_duplicate_identity_conflict_rejected`, `test_simultaneous_claimers_only_one_wins` (two SQLite connections to one DB), `test_stale_fencing_token_cannot_complete`, `test_different_source_sha_cannot_complete`, `test_codex_not_automatically_claimable`.
- [ ] **Step 2: Run RED** — `pytest -q tests/test_asset_controller_queue.py`; verify the absent functions cause the expected failure.
- [ ] **Step 3: Implement atomic queue operations** — validate `lease_seconds > 0`, nonempty owner/reason, exact lease and token match, keep immutable events/attempt receipts. Treat repeat identical completion as a no-op, not another side effect.
- [ ] **Step 4: Verify GREEN** — same targeted test command, then `ruff check shorts_studio/asset_factory/controller/queue.py tests/test_asset_controller_queue.py`.
- [ ] **Step 5: Commit** — `git add shorts_studio/asset_factory/controller/queue.py tests/test_asset_controller_queue.py && git commit -m "feat(controller): fence claims and reject duplicate dispatch"`.

### Task 3: Immutable Local Artifacts and Source Proof

**Files:**
- Create: `shorts_studio/asset_factory/controller/artifacts.py`
- Test: `tests/test_asset_controller_artifacts.py`

**Interfaces:**
- Consumes `ArtifactReceipt` and the validated job fields from Task 1.
- Produces `LocalArtifactStore(root: Path)` with `put(job: JobSpec, content: bytes) -> ArtifactReceipt` and `verify(job: JobSpec, receipt: ArtifactReceipt) -> bool`.
- Use `root / "sha256" / digest[:2] / digest` for content blobs; write to a private temp file, flush/fsync and atomically rename; never accept caller-provided absolute/parent-escaping receipt paths. Verify hash, length, and job/source/input identity on read; never mistake an upload, filename or partial proof for native 3D QA.

- [ ] **Step 1: Write failing tests** — `test_bytes_are_durable_and_sha_verified`, `test_corrupt_or_foreign_artifact_rejected`, `test_same_content_is_deduplicated_safely`, `test_path_traversal_and_symlink_rejected`. Verify unchanged previously good blob after rejecting a corrupted sidecar.
- [ ] **Step 2: Run RED** — `pytest -q tests/test_asset_controller_artifacts.py`.
- [ ] **Step 3: Implement `LocalArtifactStore`** — store immutable blobs and receipt fields separately; do not delete or overwrite the last verified object. **No actual B2 credentials/API calls**.
- [ ] **Step 4: Verify GREEN** — tests above and `ruff check shorts_studio/asset_factory/controller/artifacts.py tests/test_asset_controller_artifacts.py`.
- [ ] **Step 5: Commit** — `git add shorts_studio/asset_factory/controller/artifacts.py tests/test_asset_controller_artifacts.py && git commit -m "feat(controller): verify immutable local artifact receipts"`.

### Task 4: Fail-Closed Recovery and SQLite Snapshots

**Files:**
- Create: `shorts_studio/asset_factory/controller/recovery.py`
- Test: `tests/test_asset_controller_recovery.py`

**Interfaces:**
- Consumes `open_controller_db`, `Claim`, `LocalArtifactStore` and Task 2 transitions.
- Produces `reconcile_expired(conn: sqlite3.Connection, store: LocalArtifactStore, now: float, lookup: Callable[[Claim], str]) -> list[str]`, where lookup status is `"running"`, `"completed"`, `"not_started"` or `"unknown"`. For `"completed"`, read the persisted job receipt from `receipts` and check it through `store.verify(...)` before completion; if absent/unverified, block. Unknown/unreachable external status moves job to `blocked` with an event; it is never automatically redispatched. For `"not_started"`, a new claim is allowed only after explicit evidence-based transition respecting `max_attempts`.
- Produces `snapshot_db(conn: sqlite3.Connection, dest: Path) -> str` (SQLite backup API + SHA256 digest sidecar) and `restore_db(src: Path, dest: Path, expected_sha256: str) -> None`; verify checksum **before** touching the destination; refuse open/wrong schema/corrupt snapshots and retain last good DB.

- [ ] **Step 1: Write failing tests** — `test_unknown_expired_job_is_blocked_without_retry`, `test_completed_external_result_must_have_verified_receipt`, `test_known_not_started_respects_attempt_budget`, `test_snapshot_restore_survives_reopen`, `test_corrupt_snapshot_does_not_overwrite_good_db`. Restore must reject a live/locked destination and preserve a prior verified database on failure.
- [ ] **Step 2: Run RED** — `pytest -q tests/test_asset_controller_recovery.py`.
- [ ] **Step 3: Implement reconciliation and offline restore** — deterministic injected clock/status lookup; never simply rerun a timed-out paid job; use SQLite backup API, not copying a live WAL database file.
- [ ] **Step 4: Verify GREEN** — tests above; reopen restored DB and inspect queued and blocked counts; `ruff check shorts_studio/asset_factory/controller/recovery.py tests/test_asset_controller_recovery.py`.
- [ ] **Step 5: Commit** — `git add shorts_studio/asset_factory/controller/recovery.py tests/test_asset_controller_recovery.py && git commit -m "feat(controller): reconcile uncertain jobs and restore snapshots"`.

### Task 5: Bounded Mock Runner and Disk/Spend Guards

**Files:**
- Create: `shorts_studio/asset_factory/controller/workers.py`
- Create: `shorts_studio/asset_factory/controller/runner.py`
- Test: `tests/test_asset_controller_runner.py`

**Interfaces:**
- Consumes the Task 1–4 APIs.
- Produces `MockWorker.run(job: JobSpec) -> bytes` (stable deterministic proof bytes, **not** a real frame or video) and `run_once(conn: sqlite3.Connection, store: LocalArtifactStore, *, worker: MockWorker, now: float, disk_free_ratio: float, approved_budget_usd: str = "0") -> str` returning one of `"idle"`, `"blocked"`, `"completed_mock"`. `"completed_mock"` is a diagnostic return label; DB state stays explicitly mock-verified, never `library_ready` or production QA PASS.
- No model/API/GitHub/renderer calls; mock-only worker admission, one claim per tick, `disk_free_ratio >= 0.10` threshold, worker timeout/error -> explicit blocked/error receipt without deleting previous data. Budget `0` disallows all billable kinds.

- [ ] **Step 1: Write failing tests** — `test_mock_job_finishes_with_verified_receipt`, `test_empty_queue_is_idle`, `test_disk_pressure_blocks_before_work`, `test_billable_job_never_dispatches_at_zero_budget`, `test_unhandled_worker_failure_keeps_checkpoint`, `test_model_cooldown_blocks_until_allowed` (injected clock and retry-after timestamp).
- [ ] **Step 2: Run RED** — `pytest -q tests/test_asset_controller_runner.py`.
- [ ] **Step 3: Implement one-cycle runner and mock worker** — no infinite background loop, minimal dependencies; require verified receipt **before** `complete_claim`; persist event and stable terminal state.
- [ ] **Step 4: Verify GREEN** — targeted tests plus `pytest -q tests/test_asset_controller_*.py` (or discover matching tests if glob behavior varies); `ruff check shorts_studio/asset_factory tests/test_asset_controller_*.py`.
- [ ] **Step 5: Commit** — `git add shorts_studio/asset_factory/controller/workers.py shorts_studio/asset_factory/controller/runner.py tests/test_asset_controller_runner.py && git commit -m "feat(controller): dispatch mock jobs behind safety guards"`.

### Task 6: Optional Codex Adapter — Tested, Disabled by Default

**Files:**
- Modify: `shorts_studio/asset_factory/controller/workers.py`
- Test: `tests/test_asset_controller_codex.py`

**Interfaces:**
- Consumes `JobSpec` from Task 1; **does not change** default `run_once` mock-only behavior.
- Produces immutable `CodexProbeResult(status: str, reason: str, output_sha256: str | None, expected_head: str, tests_passed: bool, changed_files: tuple[str, ...])`. `CodexWorker.run(job: JobSpec, *, workspace: Path, expected_head: str, expected_files: tuple[str, ...], test_command: tuple[str, ...], timeout_seconds: int, enabled: bool = False, run_process: Callable[..., object] = subprocess.run) -> CodexProbeResult`. The return value is a **probe result**, not a production `ArtifactReceipt` and does not mark a queue job complete. Caller owns a fresh isolated git worktree; invoke `codex exec --sandbox workspace-write --ephemeral` with no bypass, finite timeout, explicit task prompt, and no unapproved paid APIs. Use per-run isolated output paths and `--output-last-message` only as a *diagnostic*, not success proof.
- When `enabled=False`, never invoke subprocess. When enabled in a separately authorized **scratch probe**, require exact HEAD before/after, expected file existence, audited diff, successful required tests, approved task scope and independent file SHA256. Git HEAD is expected **unchanged** during the probe (uncommitted workspace changes only). A no-file exit 0 or expired ChatGPT/quota status is **blocked**, not success. No queue/runner integration of this adapter until separately authorized.

- [ ] **Step 1: Write failing tests with a fake `run_process`** — `test_codex_disabled_never_invokes_process`, `test_zero_exit_without_receipt_is_not_success`, `test_quota_or_sha_drift_blocks`, `test_codex_timeout_is_checkpointed`, `test_valid_scratch_outputs_require_verified_tests_and_diff`.
- [ ] **Step 2: Run RED** — `pytest -q tests/test_asset_controller_codex.py`.
- [ ] **Step 3: Implement the adapter behind the explicit opt-in flag** — no read of ChatGPT tokens into logs; sanitize external process output; do not allow a Codex job to gain publish/merge/spend permissions or silently fall back to Anthropic billing.
- [ ] **Step 4: Verify GREEN** — targeted tests and `ruff check shorts_studio/asset_factory/controller/workers.py tests/test_asset_controller_codex.py`; **optional** one manual, no-spend scratch probe after separate operator approval, never start a daemon here.
- [ ] **Step 5: Commit** — `git add shorts_studio/asset_factory/controller/workers.py tests/test_asset_controller_codex.py && git commit -m "feat(controller): gate Codex subprocess and require independent receipts"`.

### Task 7: Operator CLI, Inert Service Template and VPS Recovery Runbook

**Files:**
- Create: `shorts_studio/asset_factory/controller/__main__.py`
- Create: `deploy/systemd/shorts-asset-controller.service`
- Create: `docs/operations/asset-controller-pilot.md`
- Test: `tests/test_asset_controller_cli.py`

**Interfaces:**
- `python3 -m shorts_studio.asset_factory.controller init --db <path>`
- `python3 -m shorts_studio.asset_factory.controller enqueue-mock --db <path> --id <id> --source-sha <40-hex> --input-digest <64-hex>` (fixed test asset/version/payload only in mock mode)
- `python3 -m shorts_studio.asset_factory.controller step --db <path> --storage <dir> --mock-only`
- `python3 -m shorts_studio.asset_factory.controller serve --db <path> --storage <dir> --mock-only --poll-seconds 60` runs a single-process mock-only loop with SIGTERM-safe shutdown; tests invoke `--max-ticks 2` so they terminate deterministically.
- `python3 -m shorts_studio.asset_factory.controller status --db <path> --json`
- `python3 -m shorts_studio.asset_factory.controller snapshot --db <path> --dest <path>`; `recover --source <path> --expected-sha256 <hex> --db <path>`.
- `deploy/systemd/shorts-asset-controller.service` is **not to be enabled** during plan implementation; make it explicitly mock-only and dependent on a dedicated non-login service account, local state directory, conservative resource limits, `Restart=on-failure` and no persistent Codex auth in the service user's home. Installation and 24-hour burn-in need separate owner approval.
- A CLI status report includes `queued`, `blocked`, `completed_mock`, receipt counts, last event and database schema version; no passwords, tokens, public server IP or secrets.

- [ ] **Step 1: Write failing subprocess CLI tests** — `test_init_enqueue_step_status_roundtrip`, `test_status_without_db_fails_cleanly`, `test_recover_bad_digest_keeps_original`, `test_cli_never_dispatches_codex_or_renderer_by_default`, `test_mock_serve_stops_after_two_ticks`, `test_no_secret_in_status_or_runbook`.
- [ ] **Step 2: Run RED** — `pytest -q tests/test_asset_controller_cli.py`.
- [ ] **Step 3: Implement commands and documented inert systemd template** — `ExecStart` must invoke the new `serve --mock-only --poll-seconds 60` command exactly, never `codex`, B2 or an external renderer. The runbook gives install/disable/rollback/checkpoint steps and reminds the operator **not to install or enable** the service automatically during this plan. Avoid changing the existing `shorts_studio/cli.py` entrypoint or `.github/workflows/operator-bridge.yml`.
- [ ] **Step 4: Verify GREEN and whole-repo regressions** — `pytest -q tests/test_asset_controller_*.py` and `pytest -q`; `ruff check shorts_studio/asset_factory tests/test_asset_controller_*.py`. On VPS, use an approved isolated test worktree, only mock work, `python3 -m shorts_studio.asset_factory.controller --help`, and a local snapshot/restore rehearsal. Full product CI `test.yml` must be green at the exact branch SHA before claiming compatibility.
- [ ] **Step 5: Commit** — `git add shorts_studio/asset_factory/controller/__main__.py deploy/systemd/shorts-asset-controller.service docs/operations/asset-controller-pilot.md tests/test_asset_controller_cli.py && git commit -m "docs(controller): add mock-only operator CLI and recovery runbook"`.

## Final Review and Execution Handoff

- [ ] **Compare completed changes to approved spec sections 1–8.** This plan covers Milestone A and the reversible Codex **adapter**, not live video, B2, provider fallback, or commercial renderer provisioning.
- [ ] **Run all exact verification commands fresh**, read full exit codes/logs; record real test counts and the commit SHA. Ensure `git status --short` is clean, production video files/PRs remain unchanged, source SHA/renderer contracts aren't weakened, and no secrets are staged.
- [ ] **Require a reviewer gate before each task's commit** and a final whole-branch reviewer. If a test or policy fails, revert only scoped changes; never erase existing Nightshift records or native frame caches.
- [ ] **Create a draft PR for owner review only after approved implementation and green exact-head CI**; do not merge automatically. A successful scratch unit test does **not** justify deploying a real controller or cancelling Claude Pro.
- [ ] **After implementation review**, submit follow-on narrowly scoped plans for (a) versioned Factory manifest adapter after reconciling PR #51–56, (b) B2 encrypted off-host snapshots and retention with separately approved account costs, and (c) safe render worker leases and a finite 24-hour soak.

**Recommended execution method:** **Native / inline** under Superpowers `executing-plans`, with one fresh independent final review, because the controller tasks share SQLite interfaces and a single sequential implementer minimizes mismatched schema and state transitions. The owner may instead choose **subagent-driven** for a fresh implementer and reviewer on every task, at higher context/usage cost. Both approaches require the user to review **this plan** and select the method before editing product code or deploying services.
