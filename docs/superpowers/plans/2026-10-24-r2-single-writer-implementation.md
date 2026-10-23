# R2 Single-Writer OAuth and Resumable Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an opt-in, crash-resumable OVH CLI that serializes R2 OAuth transfers and proves complete remote byte integrity without changing video production defaults.

**Architecture:** A new `shorts_studio.r2_handoff` package owns deterministic manifests, private staging, SQLite receipts, host-local locks and a pinned Wrangler subprocess adapter. The coordinator uploads immutable chunk keys, reconciles uncertain writes by GET, then independently reconstructs and hashes the whole file. Existing manual Wrangler and S3 pilots remain separate.

**Tech Stack:** Existing Python >=3.11 / pytest / Ruff; standard-library dataclasses, hashlib, sqlite3, fcntl, resource and subprocess; existing installed Wrangler 4.152.0, subject to compatibility inspection. No new Python runtime dependency or cloud service.

**Spec:** `docs/superpowers/specs/2026-10-24-r2-single-writer-resume-design.md`, approved by owner on 2026-10-24 KST, at design commit `31e53b9c0361b492c0c8f89481b6b44d798c084c`.

## Global Constraints

- Existing OVH VPS and existing `shorts-studio-media` R2 bucket only; Android is a command/control transport only.
- Source files are never automatically deleted. No systemd service, scheduler, renderer hook, public port or other-host writer in this stage.
- Main, existing render/TTS/caption/visual QA and existing S3/manual-pilot APIs remain unchanged. No PR merge or YouTube publication.
- Default proposal: 32 MiB chunks; hard v1 object ceiling 128 MiB, file/job ceiling 2 GiB, maximum 64 chunks per job, manifest ceiling 1 MiB.
- Caller supplies maximum bytes and operation limits; proposed default budget 320 data operations, hard ceiling 1,024; token-fetch hard maximum 1,024; at most two transient retries per operation; proposed deadline 30 minutes. New upload minimum: 4N + 4 data calls; independent verify minimum: N + 1 GETs.
- Data subprocess timeout 90 seconds; credential subprocess timeout 30 seconds. Require OAuth expiry to cover the data timeout plus a 30-second margin. Do not force early renewal by changing expiration data.
- `authorized_to_cleanup_local=false`, `production_concurrent_writes_allowed=false`, `provider_spend_cap_enforced=false`, `upload_authorized=false`.
- No real OAuth refresh test, R2 write batch, controller activation, GPU rental or full 900-frame production is authorized by this plan. Live acceptance needs separate authorization and explicit bounded input.
- Existing monthly KRW 50,000 total / KRW 3,000 R2 allocations remain planning context, never a provider-enforced cap or verified invoice.
- Before execution, reverify main/open PRs/CI and repository instructions; use an isolated worktree through `superpowers:using-git-worktrees`. Preserve concurrent changes. A regression disables/reverts only the new integration to the last verified state and preserves sources/receipts.

## Review Focus

1. UTC clock jumps or a token near expiry: no write starts without lifetime headroom; a backward jump cannot extend an already running job indefinitely (Tasks 3, 4).
2. A destination created by another process during restore: never replace it, even after all hashes match (Task 2).
3. An OAuth file replaced during refresh or unrelated credential environment variables: no secret disclosure or unintended account/type selection (Task 4).
4. Huge remote payloads and truncated/ambiguous Wrangler errors: bounded local disk/output use; unknown errors never authorize PUT (Task 5).
5. A newer schema, corrupted database or quota reservation surviving a crash: block safely, preserve evidence and never reset consumed budget (Task 3).

---

## File Map and Shared Interfaces

Create `shorts_studio/r2_handoff/` with `__init__.py`, `__main__.py`, `contracts.py`, `staging.py`, `state.py`, `oauth.py`, `wrangler.py`, `coordinator.py`, `cli.py`; corresponding focused tests `tests/test_r2_handoff_{contracts,staging,state,oauth,wrangler,coordinator,cli}.py`. Create `docs/r2-handoff-operator.md` with the CLI task. Existing project entry points, dependency configuration, pilots, renderer, workflows and budget estimators do not need modification. If source inspection reveals a necessary compatibility change, document it and keep the old API covered rather than silently changing contracts.

All interfaces below are new. Use frozen dataclasses unless explicitly mutable. `Path` means pathlib.Path; `datetime` values are aware UTC. Digest values are lowercase 64-character hex. Error codes are sanitized enums/strings, never subprocess text. Tests may inject clocks, runners and crash points; production defaults cannot enable a fake-success path.

`contracts.py` defines:

- `Limits(max_bytes: int, max_data_ops: int, max_token_fetches: int, deadline_utc: datetime, chunk_bytes: int = 33554432, max_retries: int = 2)`; constructor rejects bool-as-int and nonfinite/negative/overflow values. `limits.validate_for(chunk_count: int, *, mode: Literal['upload','verify']) -> None` enforces the spec's minimum path and ceilings; caller must supply byte/operation/token budgets.
- `Chunk(index: int, offset: int, size_bytes: int, sha256: str, key: str)`.
- `Manifest(schema_version: int, account_id: str, bucket: str, namespace: str, source_name: str, source_suffix: str, size_bytes: int, sha256: str, chunk_bytes: int, chunks: tuple[Chunk, ...], provenance: dict[str, str])`.
- `RestoreRequest(account_id: str, bucket: str, namespace: str, manifest_key: str, expected_manifest_sha256: str, destination: Path)` is the immutable GET-only restore identity, independent of an upload source.
- `Fingerprint(device: int, inode: int, size_bytes: int, mtime_ns: int, ctime_ns: int)` and `Staged(plan_id: str, source: Path, source_fingerprint: Fingerprint, spool: Path, manifest: Manifest)`.
- `Receipt(status: str, plan_id: str | None, manifest_key: str, sha256: str, size_bytes: int, media_status: Literal['MEDIA_QA_PENDING'], authorized_to_cleanup_local: Literal[False] = False, production_concurrent_writes_allowed: Literal[False] = False, provider_spend_cap_enforced: Literal[False] = False, upload_authorized: Literal[False] = False)`.
- `HandoffError(code: str)`; only its safe code may cross CLI/log boundaries. Approved transport receipt never authorizes publishing or claims video QA. Caller provenance is recorded, not independently trusted; film evidence verification stays outside this package.

Do not construct manifests with server-returned arbitrary object paths. Namespace/account/bucket and digest-derived keys must be validated at every external boundary. Persist planned limits separately from canonical manifests: changing permitted retry limits on explicit resume must not change content identity.

### Task 1: Deterministic Contracts and Offline Planning

**Files:** Create package `__init__.py`, `contracts.py`; test `tests/test_r2_handoff_contracts.py`.

**Interfaces:** Consumes none. Produces the above types plus `canonical_manifest(manifest: Manifest) -> bytes`, `parse_manifest(raw: bytes, *, account_id: str, bucket: str, namespace: str) -> Manifest`, `manifest_key(manifest: Manifest) -> str`, `plan_id(manifest: Manifest) -> str`, `plan_source(source: Path, *, account_id: str, bucket: str, namespace: str, limits: Limits, expected_sha256: str | None, provenance: dict[str,str]) -> Manifest`. Plan streams hashes with stable descriptor checks, does no network/secret access and creates no upload authorization.

- [ ] **Step 1:** Add `test_manifest_is_canonical_and_has_gap_free_offsets`: two serializations of the same manifest are byte-identical; reordered input entries, duplicate indices, gaps/overlaps, mismatched digest-derived key, wrong account/bucket/namespace and >1 MiB manifest fail. Add `test_plan_is_offline_and_enforces_v1_limits`: no network/credential runner called, default chunk bytes == 33554432, 64-chunk upload needs at least 260 data calls, verify needs 65, 2 GiB + 1 byte/65 chunks/bool budgets/empty files fail. Assert manifest contains no time-dependent receipt data.
- [ ] **Step 2:** Run `pytest -q tests/test_r2_handoff_contracts.py`; expected RED missing module/symbol, not an unrelated dependency failure.
- [ ] **Step 3:** Implement the types and functions; use deterministic JSON bytes with bounded supported fields, derive keys under `shorts-studio/<namespace>/v1/chunks/<sha>.bin` and hash-addressed manifest namespace. Job identity is the canonical manifest SHA. Do not reuse the public pilot suffix whitelist as a broad `.bin` upload permission.
- [ ] **Step 4:** Run the focused file and existing `tests/test_r2_verified_transfer.py` and `tests/test_r2_wrangler_pilot.py`; expected PASS.
- [ ] **Step 5:** Commit only these files: `feat(r2): define deterministic bounded handoff contracts`.

### Task 2: Private Staging and No-Replace Reconstruction

**Files:** Create `staging.py`; test `tests/test_r2_handoff_staging.py`.

**Interfaces:** Consumes Task 1 types. Produces `stage_source(source: Path, *, root: Path, planned: Manifest, min_free_bytes: int = 268435456) -> Staged`, `validate_staged(staged: Staged) -> None`, `validate_original(staged: Staged) -> None`, `restore_file(manifest: Manifest, *, destination: Path, fetch: Callable[[Chunk, Path], None], min_free_bytes: int = 268435456) -> None`. Fetch writes one bounded chunk; restoration streams it into the destination candidate and verifies chunk and total hashes. Scope is trusted single-user OVH, not malicious same-UID resistance.

- [ ] **Step 1:** Add `test_staging_rejects_source_replacement_and_preserves_source` (swap/symlink/mutate between planning/copy/validation => error and no success); `test_chunk_snapshot_and_full_digest_agree` (offsets cover exact bytes and original unmodified); `test_restore_existing_or_raced_destination_is_never_replaced` (a competing process creates destination immediately before installation; existing bytes survive); `test_disk_floor_blocks_before_staging_or_readback` (free space below required spool/readback + 268435456 => safe error). Assert no automatic removal of source or failed-job spool.
- [ ] **Step 2:** Run `pytest -q tests/test_r2_handoff_staging.py`; expected RED.
- [ ] **Step 3:** Pin source descriptors with no-follow/fstat; stream private chunks and full hash; verify before/after fingerprint and expected plan hash; fsync completed files and containing directories. Validate protected ownership/root parents. Avoid full-file duplicate beyond chunk spool. Restore with same-filesystem no-replace installation; fresh original full hash is a separate required upload-success check.
- [ ] **Step 4:** Run Tasks 1–2 tests; expected PASS including process-race fixture.
- [ ] **Step 5:** Commit `feat(r2): stage private chunks and restore without overwrites`.

### Task 3: Host Locks, Durable State and Budget Reservations

**Files:** Create `state.py`; test `tests/test_r2_handoff_state.py`.

**Interfaces:** Consumes Task 1 types. Produces context manager `bucket_lock(root: Path, *, account_id: str, bucket: str) -> Iterator[None]`, `profile_lock(root: Path, *, profile: str) -> Iterator[None]`, and `StateStore(path: Path)` with `create_job(staged: Staged, limits: Limits) -> str`, `create_verify_job(request: RestoreRequest, limits: Limits) -> str`, `status(job_id: str) -> dict[str, object]`, `load_job(job_id: str) -> tuple[Staged, Limits]`, `reserve(job_id: str, *, kind: Literal['data','token'], operation_id: str, utc_now: datetime, monotonic_now: float) -> None`, `transition(job_id: str, state: str, *, chunk_index: int | None = None, code: str | None = None) -> None`, `extend_limits(job_id: str, *, limits: Limits, operator_reason: str) -> None`. Restore jobs persist the immutable manifest locator/expected SHA/destination, get a distinct job kind with no PUT authority, and reuse their durable counters on repeated requests. Validate the N + 1 minimum after the bounded manifest GET reveals N; insufficient remaining budget blocks before chunk downloads. Store close is explicit/context-managed. Internal schema also stores immutable identity, per-operation attempts, deadline history, job state and chunk observations; no credentials.

- [ ] **Step 1:** Add `test_two_real_processes_share_bucket_lock_and_second_has_zero_network` (different job namespaces still contend); `test_killed_owner_releases_kernel_lock_without_deleting_lockfile`; `test_crash_after_reservation_does_not_refund_unknown_operation`; `test_corrupt_or_newer_database_blocks_without_reinitialization`; `test_backward_clock_does_not_extend_current_process_deadline` (use min of UTC remaining and captured monotonic deadline; expiry cannot become later in-process); `test_explicit_resume_limits_keep_consumed_counters` (no counter/deadline reset without supplied limits/reason). Illegal state jumps and changed immutable plans fail.
- [ ] **Step 2:** Run `pytest -q tests/test_r2_handoff_state.py`; expected RED.
- [ ] **Step 3:** Implement stable protected lock files with nonblocking flock; never unlink held lockfiles, inspect PID text or split bucket locks by namespace. Enforce bucket-before-profile lock ordering. SQLite schema v1 uses unique plan identities, FULL sync and transactions committed before network calls; no open DB transaction across network. Reserve every attempt durably, including reconciliation calls, before invoking a child. Capture conservative per-process monotonic deadline on every explicit apply/resume; restarts must also honor persisted absolute UTC deadline. Retry ceilings are per logical operation across resumes, unless a future approved contract changes them.
- [ ] **Step 4:** Run Tasks 1–3 tests; expected PASS, actual process contention/crash tests included.
- [ ] **Step 5:** Commit `feat(r2): persist handoff state and serialize bounded attempts`.

### Task 4: Private Pinned Wrangler OAuth Acquisition

**Files:** Create `oauth.py`; test `tests/test_r2_handoff_oauth.py`.

**Interfaces:** Consumes Task 3 profile lock and token reservations via caller. Produces `OAuthConfig(home: Path, config_file: Path, lock_root: Path, profile: str, wrangler: Path)`, private `OAuthGrant` (token field excluded from repr/serialization, expiry aware UTC), `obtain_grant(config: OAuthConfig, *, now: datetime, operation_seconds: int = 90, runner: Callable = subprocess.run) -> OAuthGrant`, and `data_environment(grant: OAuthGrant, *, home: Path) -> dict[str,str]`. Grant is process-local and not a public receipt field. Inject bounded child runner for tests, not a production no-op path.

- [ ] **Step 1:** Add `test_token_command_captures_oauth_and_never_echoes_it` (sentinel absent from argv/errors/logs/DB/repr); `test_ambient_credentials_do_not_override_profile` (API token/key/email env removed and returned non-OAuth type rejected); `test_config_replacement_and_permissions_block` (symlink/UID/mode/parent substitution); `test_token_with_less_than_120_seconds_enters_wait_auth_window` and exact threshold acceptance; `test_revoked_or_malformed_refresh_returns_auth_required_without_login` (no browser, no token-file edits, no data child). Simulate refresh rotating both tokens and retain unrelated config fields under the adapter's ownership rules.
- [ ] **Step 2:** Run `pytest -q tests/test_r2_handoff_oauth.py`; expected RED.
- [ ] **Step 3:** Inspect the exact pinned installed Wrangler command/config/log behavior read-only; record version/hash and compatibility conclusions in operator notes. Under profile lock invoke `auth token --json` with 30-second timeout, 1 MiB maximum stdout and stderr each, sanitized allowlisted environment, no debug/metrics leakage and exact home/profile. Accept expected OAuth result only; revalidate private config before/after and read fresh expiry. Let pinned Wrangler own rotation, do not write a competing refresh client or force expiry. If its write/log behavior cannot meet confidentiality, block real activation and report the exact capability gap. Unsupported command => AUTH_REQUIRED/manual-only; short remaining lifetime => WAIT_AUTH_WINDOW, caller persists/releases locks for explicit later resume.
- [ ] **Step 4:** Run Tasks 1–4 tests; expected PASS without real credentials or requests. Do not run the token command against a live credential as an unapproved test.
- [ ] **Step 5:** Commit `feat(r2): acquire OAuth privately through pinned Wrangler`.

### Task 5: Bounded Wrangler GET/PUT Adapter

**Files:** Create `wrangler.py`; test `tests/test_r2_handoff_wrangler.py`.

**Interfaces:** Consumes Task 4 grant/environment and Task 1 types. Produces `RemoteMissing(HandoffError)` and `WranglerBackend(wrangler: Path, *, acquire: Callable[[], OAuthGrant], before_call: Callable[[str], None], runner: Callable)` with `get(key: str, destination: Path, *, expected_size: int) -> None`, `put(key: str, source: Path, *, expected_sha256: str, expected_size: int) -> None`. Each call invokes `before_call` to durably reserve its data/token attempts then obtains fresh credentials; coordinator supplies the operation identity in closures. Preserve the returned structured distinction between missing/retryable/auth/integrity/unknown failures.

- [ ] **Step 1:** Add `test_unknown_or_truncated_errors_never_mean_missing` (including text containing both a missing-key phrase and denied/auth errors); `test_missing_bucket_is_not_missing_object`; `test_giant_existing_remote_object_hits_output_limit` (real harmless local child attempts oversized write, source retained); `test_put_uses_verified_snapshot_not_replaced_original_path`; `test_timeout_does_not_claim_put_failed_without_reconciliation`; test stdout/stderr/output-file ceilings and no secret-bearing child output escaping.
- [ ] **Step 2:** Run `pytest -q tests/test_r2_handoff_wrangler.py`; expected RED.
- [ ] **Step 3:** Pin expected CLI exit/error formats with non-secret fixtures from that exact release; only positively classified missing-key results raise RemoteMissing. No supported trustworthy classifier => block unknown, never guess. Use no-shell argv, 90-second timeout, bounded output buffers (1 MiB each), child file limit expected_size + 1 through Linux resource limits; verify resulting size/hash outside CLI metadata. Private chunk files only for PUT; check their exact planned identity immediately before command. No raw stdout/stderr persistence or exception chaining in CLI-facing errors.
- [ ] **Step 4:** Run Tasks 1–5 tests plus original R2 tests; expected PASS, including actual resource-limited subprocess test. Never assert fake CLI tests prove live R2 behavior.
- [ ] **Step 5:** Commit `feat(r2): bound Wrangler operations and classify failures safely`.

### Task 6: Resumable Coordinator and Independent Verification

**Files:** Create `coordinator.py`; test `tests/test_r2_handoff_coordinator.py`.

**Interfaces:** Consumes Tasks 1–5. Produces `Coordinator(store: StateStore, backend_factory: Callable[[str], WranglerBackend], *, lock_root: Path, utc_clock: Callable[[],datetime], monotonic_clock: Callable[[],float])` with `apply(job_id: str) -> Receipt`, `resume(job_id: str, *, limits: Limits | None = None, operator_reason: str | None = None) -> Receipt`, `verify(*, account_id: str, bucket: str, namespace: str, manifest_key: str, expected_manifest_sha256: str, destination: Path, limits: Limits) -> Receipt`. Public entry points acquire bucket lock before staging seal/refresh/network. `create_job`/sealing orchestration uses the same lock in the CLI and never contacts network before lock ownership. Verification has a separate durable read-only job/budget ledger; its receipt cannot authorize PUT or promote an upload job.

- [ ] **Step 1:** Add `test_new_job_uploads_manifest_last_and_reconstructs_complete_sha` (all chunks freshly read back; REMOTE_VERIFIED only after independent reconstruction and original recheck; MEDIA_QA_PENDING always); `test_resume_rechecks_every_remote_chunk_even_if_local_state_says_done`; `test_existing_wrong_chunk_blocks_without_overwrite`; `test_uncertain_put_reconciles_before_retry`; `test_source_changes_on_existing_object_path_never_return_success`; `test_verify_without_original_is_get_only_download_verified` (N + 1 minimum GETs, wrong manifest/account/path/hash rejected, destination protected); `test_limit_or_auth_side_state_releases_locks_and_keeps_checkpoint`.
- [ ] **Step 2:** Run `pytest -q tests/test_r2_handoff_coordinator.py`; expected RED.
- [ ] **Step 3:** Implement the spec state transitions, immutable plan lookup and per-call reservations. For each chunk: GET -> validate existing, or proven-missing -> PUT -> GET and validate. Checkpoint only verified observations. Manifest follows the same uncertain-write rules, then fresh manifest GET and full ordered reconstruction. On resume validate spool/original then re-fetch every previously verified chunk. Classify retryable transport/429/5xx only, bounded backoff 1 then 2 seconds, honor remaining UTC/monotonic deadline/counters and two-retry cap. Timeout/auth/kill during PUT always reconciles with GET before another PUT; failure to positively prove absence stops writes. No source cleanup, automatic login, indefinite lock wait or automatic job startup.
- [ ] **Step 4:** Add and run `test_kill_and_resume_at_each_persistence_boundary`, parametrized at before PUT, after PUT, after readback, before DB commit, after manifest upload and during reconstruction. Use subprocess kill with durable local fake remote storage; after restart assert no blind overwrite, no refunded counters, preserved source/spool, and either validated success or the exact safe side state. Run all handoff tests; expected PASS.
- [ ] **Step 5:** Commit `feat(r2): resume verified chunks and reconstruct remote content`.

### Task 7: Explicit CLI, Operator Guide and Whole-Branch Validation

**Files:** Create `cli.py`, `__main__.py`, `docs/r2-handoff-operator.md`; test `tests/test_r2_handoff_cli.py`.

**Interfaces:** Consumes previous tasks. Produces `cli.main(argv: list[str] | None = None) -> int`, invoked by `python -m shorts_studio.r2_handoff`. Exit codes: 0 success/dry-run, 2 invalid/integrity/auth/bounds block, 3 BUSY, 4 safe transient/checkpointed interruption. Status is read-only local state and never uses credentials/network.

- [ ] **Step 1:** Add `test_cli_defaults_to_no_network_no_secret_access`; `test_apply_and_resume_require_explicit_flag_and_recorded_job` (job ID alone insufficient); `test_verify_requires_read_remote_and_has_no_put_path`; `test_status_does_not_resume_work`; `test_android_blocks_media_commands` (plan/save-plan/apply/resume/verify blocked before media/secret handling; local metadata-only status remains permitted); `test_every_error_is_sanitized_and_all_permission_flags_are_false`; `test_resume_extension_requires_reason_and_preserves_identity_and_consumption`. Missing explicit byte/data/token/deadline/account/bucket/namespace inputs reject before network. Golden help assertions verify plan/apply/status/resume/verify options and independent expected-manifest-SHA requirement.
- [ ] **Step 2:** Run `pytest -q tests/test_r2_handoff_cli.py`; expected RED.
- [ ] **Step 3:** Wire the CLI; new local `plan` writes no queue/authorization until explicit `--save-plan`, still no network/secret access. Document source path, spool/state roots, explicit limits and expected-digest options. Apply/resume require `--apply`; independent verify requires `--read-remote` and a nonexistent destination; status takes only job/state inputs. Reject Android before any operational filesystem/network/credential action. Document host-local writer assumption, manual login only while coordinator stopped, source/spool retention, explicit retry-limit extensions, AUTH_REQUIRED/WAIT_AUTH_WINDOW handling, and copyable DRY_RUN commands only. Do not install background services or hook the renderer.
- [ ] **Step 4:** Run `pytest -q tests/test_r2_handoff_*.py tests/test_r2_verified_transfer.py tests/test_r2_wrangler_pilot.py tests/test_r2_secret_bootstrap.py tests/test_r2_storage_estimate.py`, `ruff check shorts_studio/r2_handoff tests/test_r2_handoff_*.py`, then `pytest -q` in the correct project test environment. Require all focused tests PASS and full baseline passes/skips without reduced quality thresholds; record exact commands/counts and environment limitations. Run `git diff --check` and audit changed paths. Missing optional vision dependencies do not count as live video-QA acceptance; existing full render-smoke CI must execute independently.
- [ ] **Step 5:** Commit `feat(r2): expose opt-in handoff CLI and operating contract`, push only the reviewed feature branch and monitor every initiated CI check to terminal. Read actual failure logs and fix the minimum issue; no empty green claims or repeated redundant runs. Compare main and PR head after checks, inspect real smoke QA logs. Preserve final source SHA/run IDs in project memory.

## Later Live Acceptance — Not Part of This Execution Authorization

After offline tests/review, present a concrete bounded OVH probe request: exact installed tool/source SHAs; named non-secret input; exact total bytes/operations/deadline; expected preserved source; fixed account/bucket/namespace; no new resources or deletion. With separate live approval, prove natural-expiry official token renewal plus read-only R2 access without secret output, interrupt/resume a small multi-chunk file, and perform independent GET-only restore with matching complete SHA. If expiry/permissions/logging behavior fails, leave manual pilot intact and the new coordinator disabled. Do not label mocked refresh, tiny probes, stale invoices or transfer PASS as full-film readiness. Controller integration and real media QA/900-frame production require their own approval and exact provenance.

## Self-Review and Execution Handoff

Spec coverage: deterministic chunk/manifest/resource rules -> Tasks 1–2; host serialization/durable budgets -> Task 3; private credential renewal -> Task 4; bounded data/error classification -> Task 5; recovery/source/remote verification -> Task 6; operator gates, Android block, CI and rollback -> Task 7. Live authentication/provider behavior is an explicit later gate, not assumed implementation success. All five Review Focus cases have named owning tests. No existing production code needs refactoring; new package uses existing packaging discovery.

Implementation has not begun. Recommended execution method is **Native**: the seven tasks share tightly specified interfaces and storage/auth state, so one implementer can retain context; run a fresh whole-branch reviewer after implementation and before any activation. The owner must review this plan and select/confirm the execution method before implementation under the Superpowers handoff rule. Review must include the approved spec. Preserve the owner-selected method through later context handoffs.
