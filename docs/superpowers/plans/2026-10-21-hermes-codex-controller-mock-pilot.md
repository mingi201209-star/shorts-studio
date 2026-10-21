# Hermes–Codex–VPS Controller Mock Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Safely connect a fake Hermes supervisor's untrusted JSON proposals to the existing VPS Controller's mock-only queue, approval gate, durable audit, local SHA256 receipt verification and failure/restart reporting, without running Hermes or Codex.

**Architecture:** A strictly validating, offline, operator-mediated bridge translates an immutable proposed intent into exactly one Controller JobSpec. A separate private audit ledger preserves approval and correlation while the original Controller remains the **only authority on execution and receipts**. FakeHermes and fake Codex results exercise the contracts; actual Hermes/Codex integration, OS account creation and service deployment are later separately authorized stages.

**Tech Stack:** Python >=3.11, stdlib json/hashlib/sqlite3/dataclasses/pathlib, Linux local filesystem, existing pytest>=8 and ruff>=0.6. No new product dependencies.

**Spec:** ../specs/2026-10-21-hermes-codex-controller-mock-pilot-design.md (approved 2026-10-21, branch design/hermes-codex-controller-pilot-20261021, spec commit 8517c0f784f968534b2436f9301c611f7f21c9b0).

## Global Constraints

- **Implementation not yet authorized.** This plan itself is documentation only. Do not write product code before the owner reviews this plan and selects an execution method.
- Execution branch, when approved, must be a new isolated worktree branched from **the exact then-current PR #57 HEAD**, initially c145e07cbbbb3676a879844d97bd8fcd8fadeb04. Recheck PR topology, SHA and exact-head CI before starting. PR #57 and its base design branch remain untouched. Bring the approved spec/plan into the worktree read-only via git show or an explicit docs-only commit, without cherry-picking unrelated features.
- Keep **main**, PR #51–56, Factory code, video QA gates and existing user worktrees intact. No auto merge, GitHub push to main, or YouTube upload.
- Only **mock_proof** jobs. Existing Controller claim_next/run_once/MockWorker behavior, database schema v1, source SHA, input digest, lease/fencing, receipt verification and offline restore safety MUST NOT be weakened. No extra worker kind admitted by the runner.
- Request: **UTF-8 JSON <=4096 bytes**, exact "hermes-controller-pilot/v1" schema, lowercase 40-hex source_sha, "mock_proof" kind, requested_by="hermes-proposal", payload={}, allowed fields only, no duplicate keys, NaN/Infinity, control characters, path, shell command, URL or secret.
- Intent identifier: lowercase [a-z0-9-]{8,64}; Kanban origin_task_id: lowercase [a-z0-9-]{1,64}, correlation only. Use regex fullmatch, ASCII only, reject Unicode lookalikes.
- Canonical bytes: json.dumps(validated complete intent object, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8'); input_digest=SHA256(canonical bytes); job_id="hp-"+input_digest[:40]. A digest supplied by a model is forbidden.
- JobSpec: asset_id="hermes-pilot", asset_version="v1", stage="mock-proof", worker_kind="mock", payload_json="{}", budget_usd="0", max_attempts=1.
- Consent: only a trusted local operator capability and operator-owned private ledger may record approval for an **exact intent_id+input_digest**. FakeHermes has no approval capability or access to ledger storage. Hermes task "done" or arbitrary text never authorizes work.
- P0 session cap **3** mock jobs, queue cap **20** pending proposals, mock dispatch concurrency **1**, **0** actual Codex processes. Disk free <15% blocks new ingress without relaxing Controller's internal 10% floor. MemAvailable <1GiB warns and <512MiB blocks.
- Logs and returned reports expose only bounded safe enums/counts/digest excerpts, not prompts, OAuth, file paths, untrusted job payloads or secrets. All terminal pilot report flags render_qa_pass, video_qa_pass and publish_ready are false.
- No Hermes installation, OAuth, real Codex execution, automatic dispatch daemon, systemd activation, additional paid API, extra server, B2, source-deleting cleanup, direct SQLite mutation by Hermes, publicly exposed HTTP/webhook, GitHub PR merge or upload.
- Use existing venv / Python 3.12 only for future mock tests; Hermes's separate managed runtime is not installed or used.
- Local operation proof is not 24-hour resilience proof; real OS UID permission enforcement/ownership is a **P1 acceptance gate**, not something simulated P0 tests can certify.

## Review Focus

The following real-world input/failure cases need explicit tests even though the vision spec does not spell out every byte-level edge:

1. **Malformed raw transport:** UTF-8 BOM, truncated/malformed multibyte, 4097-byte JSON, duplicate fields, trailing JSON, Unicode confusables and control characters are rejected without partial ledger entries (Task 1).
2. **Approval forgery/race:** "approved" in the Hermes proposal, wrong-digest approval and two concurrent same-id submissions cannot enqueue twice or advance the wrong intent (Tasks 2–3).
3. **Crash across two databases:** Controller enqueue may commit before bridge audit update; replay must query the matching Controller record and recover, never duplicate or overwrite a foreign job (Task 3).
4. **Evidence loss/tampering:** missing/changed blob, stale source SHA, invented receipt and Hermes "done" must not become proof_verified_mock or video QA PASS (Task 4).
5. **Resource/sandbox boundary:** unavailable memory/disk metrics, symlink state paths, ignored-file edits, and a 4th job in one session must fail closed with no live Codex or paid provider invoked (Tasks 2, 5–7).

---

## File Map and Interfaces

Create in the **new execution worktree only**:

| File | One responsibility |
| --- | --- |
| shorts_studio/asset_factory/integrations/__init__.py | Namespace only |
| shorts_studio/asset_factory/integrations/hermes_pilot/__init__.py | Namespace, no import-time side effects |
| shorts_studio/asset_factory/integrations/hermes_pilot/contracts.py | ProposedIntent validation, canonical digest, JobSpec mapping |
| shorts_studio/asset_factory/integrations/hermes_pilot/audit.py | Private SQLite correlation/approval ledger and lock/transaction |
| shorts_studio/asset_factory/integrations/hermes_pilot/bridge.py | Verified request ingestion, queue handoff, cross-DB crash recovery |
| shorts_studio/asset_factory/integrations/hermes_pilot/report.py | Read-only, evidence-based status projection |
| shorts_studio/asset_factory/integrations/hermes_pilot/policy.py | Pure bounded admission and resource decisions |
| tests/test_hermes_pilot_contracts.py | Untrusted input and digest invariants |
| tests/test_hermes_pilot_audit.py | Operator approval, durable ledger and concurrency |
| tests/test_hermes_pilot_bridge.py | Existing Controller enqueue/reconcile and crash windows |
| tests/test_hermes_pilot_report.py | SHA256 byte verification and false QA flags |
| tests/test_hermes_pilot_policy.py | Memory, disk, queue/session capacity |
| tests/test_hermes_pilot_e2e.py | Three complete FakeHermes/FakeOwnerApproval jobs, failure injections |
| docs/operations/hermes-controller-pilot.md | Future P0 local fixture commands and separate P1/P2 approval gates |

Existing components **consume but do not modify**: controller/contracts.py::JobSpec/ArtifactReceipt, controller/queue.py::enqueue, controller/runner.py::run_once, controller/workers.py::MockWorker/CodexProbeResult, controller/artifacts.py::LocalArtifactStore.verify, controller/database.py::open_controller_db and coordinated read-only paths.

These names and signatures are the cross-task interface contract; a change requires a recorded design ruling before downstream tasks proceed.

## Task 1: Strict Hermes Intent Contract

**Files**
- Create: shorts_studio/asset_factory/integrations/__init__.py
- Create: shorts_studio/asset_factory/integrations/hermes_pilot/__init__.py
- Create: shorts_studio/asset_factory/integrations/hermes_pilot/contracts.py
- Test: tests/test_hermes_pilot_contracts.py

**Interfaces**
- Produces: frozen ParsedIntent(intent_id: str, origin_task_id: str, source_sha: str, input_digest: str, job_id: str, canonical_bytes: bytes).
- Produces: parse_intent(raw: bytes, *, expected_head: str) -> ParsedIntent. Raises ValueError for all invalid proposals.
- Produces: to_mock_job(parsed: ParsedIntent) -> JobSpec (uses the existing validated JobSpec class).

- [ ] **Step 1: Write the failing test** with a valid exact-schema ASCII JSON fixture and expected_head="a"*40. Assert stable canonical SHA256, id "hp-" + digest[:40], and exact JobSpec values (including max_attempts=1, budget_usd="0"); assert dataclass frozen.
- [ ] **Step 2: Run** \`python -m pytest -q tests/test_hermes_pilot_contracts.py::test_valid_intent_canonical_identity\`. Expect RED (module/function missing); record the failure.
- [ ] **Step 3: Implement** parse_intent/to_mock_job. Enforce bytes max 4096 before decode; strict UTF-8 without BOM; json.loads with object_pairs_hook rejecting duplicate names and parse_constant rejecting NaN/Infinity; reject nonobject, unknown/missing fields, trailing JSON, controls and disallowed characters; regex ASCII fullmatch on identifiers and lowercase hex; no caller-supplied digest or other execution authority.
- [ ] **Step 4: Add invalid-input tests** named test_rejects_utf8_bom_truncated_multibyte_and_4097_bytes, test_rejects_duplicate_unknown_control_and_unicode_identifiers, test_rejects_non_mock_command_and_fake_approval, and test_exact_sha_required. Include both upper/lower SHA, harmless order change, same intent_id with different origin ID (digest changes). No user-supplied paths/commands are ever parsed as executable.
- [ ] **Step 5: Run** \`python -m pytest -q tests/test_hermes_pilot_contracts.py\` then \`ruff check shorts_studio/asset_factory/integrations tests/test_hermes_pilot_contracts.py\`. Expect GREEN. Commit only Task 1 files: \`git add shorts_studio/asset_factory/integrations tests/test_hermes_pilot_contracts.py && git commit -m "feat(hermes-pilot): validate immutable mock intent"\`.

## Task 2: Durable Private Approval and Correlation Ledger

**Files**
- Create: shorts_studio/asset_factory/integrations/hermes_pilot/audit.py
- Test: tests/test_hermes_pilot_audit.py

**Interfaces**
- Produces: open_ledger(path: Path) -> sqlite3.Connection; use a private pre-existing operator-owned directory (0700), reject symlink DB/parent, create db 0600 with O_NOFOLLOW|O_CREAT|O_EXCL when absent, PRAGMA journal_mode=WAL, foreign_keys=ON, synchronous=FULL, busy_timeout=5000, user_version=1. Refuse unfamiliar/unversioned populated schema, preserve WAL on reopen.
- Produces: Ledger(conn) with propose(parsed: ParsedIntent) -> str, approve_operator(intent_id: str, input_digest: str, *, authority: OperatorAuthority) -> str, lookup(intent_id: str) -> LedgerEntry, mark_submitted(intent_id: str, job_id: str) -> None.
- Produces: OperatorAuthority, a typed capability injected solely by trusted operator-side code/tests; never exposed through proposal JSON or a Hermes-callable command. Real UID-based security is deferred to approved P1 installation.

- [ ] **Step 1: Write failing tests**: test_private_ledger_requires_secure_directory, test_propose_idempotent_and_conflict_preserves_first_digest, test_owner_approval_exact_digest_only, test_persist_after_close_reopen and test_non_owner_or_hermes_cannot_approve. Assert approval event includes approved digest but no untrusted payload, and mismatched digest leaves proposal unapproved.
- [ ] **Step 2: Run** \`python -m pytest -q tests/test_hermes_pilot_audit.py\`. Expect RED and record reason before creating product implementation.
- [ ] **Step 3: Implement** ledger schema: proposals(intent_id PK, origin_task_id, digest, source_sha, job_id, state), approvals(intent_id PK, digest, approved_at, consumed), and minimal event journal. Keep source hash and job_id, never secrets/prompt. BEGIN IMMEDIATE for create/check/update; transaction ordering always ledger lock before Controller enqueue (never reverse in product code). Any exception rolls back. Do not use caller's arbitrary path as SQL or shell input.
- [ ] **Step 4: Add adversarial tests** for same ID raced by two SQLite connections/processes; directory/file symlink, overly open mode (0700/0600 invariants), invalid schema, crash/close between propose and approve, caller-forged origin_task_id="approved". A test-only FakeOwnerApproval may mint OperatorAuthority; FakeHermes may not. Make approval records durable before enqueue.
- [ ] **Step 5: Run** \`python -m pytest -q tests/test_hermes_pilot_audit.py\` and Task 1 suite; \`ruff check shorts_studio/asset_factory/integrations tests/test_hermes_pilot_audit.py\`. Expect GREEN and commit with \`git add shorts_studio/asset_factory/integrations/hermes_pilot/audit.py tests/test_hermes_pilot_audit.py && git commit -m "feat(hermes-pilot): persist owner approvals and correlations"\`.

## Task 3: Controlled Submission and Cross-DB Recovery

**Files**
- Create: shorts_studio/asset_factory/integrations/hermes_pilot/bridge.py
- Test: tests/test_hermes_pilot_bridge.py

**Interfaces**
- Consumes: parse_intent, to_mock_job, Ledger, existing queue.enqueue(conn, JobSpec) -> bool.
- Produces: submit_intent(ledger: Ledger, controller_conn: sqlite3.Connection, parsed: ParsedIntent) -> str. Return safe enum "submitted"|"already_submitted"|"review_required"; raise a typed safe BridgeRejected(reason_code: str) for conflict/unapproved/foreign controller identity.
- Produces: reconcile_submission(ledger: Ledger, controller_conn: sqlite3.Connection, intent_id: str) -> str. Reconstruct from Controller only when exact job_id, source_sha, input_digest and spec match; never assume an unknown job belongs to us.

- [ ] **Step 1: Write failing tests**: test_unapproved_intent_cannot_enqueue, test_approved_exact_digest_submits_one_mock, test_duplicate_proposal_creates_one_controller_job, test_controller_identity_conflict_refuses_and_preserves_first. Inspect jobs and attempts directly in test assertions only; production writes only through queue.enqueue.
- [ ] **Step 2: Run** \`python -m pytest -q tests/test_hermes_pilot_bridge.py\`. Expect RED; record.
- [ ] **Step 3: Implement** submit_intent with trust checks and ledger BEGIN IMMEDIATE fencing. Confirm stored approval matches canonical digest, approval was durably recorded, expected source HEAD is unchanged, then call original queue.enqueue with exactly the Task 1 JobSpec. Mark submitted only after Controller commit. Never alter Controller schema or runner.
- [ ] **Step 4: Add crash-window tests** named test_crash_before_controller_enqueue_does_not_claim_success and test_crash_after_enqueue_before_ledger_commit_reconciles_without_second_attempt. Inject a failure **after Controller enqueue commits, before ledger state commit**. On replay, inspect Controller by job_id and compare every immutable JobSpec column; exactly matching record => already_submitted, mismatch => review_required. If Controller has no matching record after ambiguous error, keep proposed/approved and require operator resubmission; never schedule a second external provider.
- [ ] **Step 5: Add concurrency and auth test**: two submitters race the same approved intent; result is one job. Hermes-provided "approved" or a fabricated OwnerAuthority JSON key never reaches approved status. A changed source SHA after approval is review_required.
- [ ] **Step 6: Run** \`python -m pytest -q tests/test_hermes_pilot_bridge.py tests/test_hermes_pilot_audit.py\`, then \`ruff check shorts_studio/asset_factory/integrations tests/test_hermes_pilot_bridge.py\`. Expect GREEN and commit: \`git add shorts_studio/asset_factory/integrations/hermes_pilot/bridge.py tests/test_hermes_pilot_bridge.py && git commit -m "feat(hermes-pilot): submit idempotent approved mock jobs"\`.

## Task 4: Read-Only Verified Proof Projection

**Files**
- Create: shorts_studio/asset_factory/integrations/hermes_pilot/report.py
- Test: tests/test_hermes_pilot_report.py

**Interfaces**
- Consumes: Ledger.lookup, read-only SELECT from Controller (jobs, receipts), JobSpec, ArtifactReceipt, LocalArtifactStore.verify(JobSpec, ArtifactReceipt)->bool.
- Produces: frozen PilotReport(intent_id: str, status: str, proof_sha256: str | None, render_qa_pass: bool=False, video_qa_pass: bool=False, publish_ready: bool=False).
- Produces: inspect_result(ledger: Ledger, controller_conn: sqlite3.Connection, store: LocalArtifactStore, intent_id: str) -> PilotReport. Safe status enum: "awaiting_approval", "queued", "running", "blocked", "proof_not_verified", "proof_verified_mock", "review_required".
- Produces: report_public(report: PilotReport) -> dict[str, str | bool | None] with no raw exception text, paths, tokens, prompt or untrusted status string.

- [ ] **Step 1: Write failing tests**: test_mock_completed_with_verified_bytes_returns_proof_verified_mock, test_done_message_without_receipt_is_not_verified, test_missing_or_changed_blob_rejects_success, test_foreign_receipt_source_digest_is_review_required, test_report_never_reports_render_or_video_qa. Use a real temp Controller DB/LocalArtifactStore, MockWorker and runner.run_once; do not fake the verified bytes for the happy path.
- [ ] **Step 2: Run** \`python -m pytest -q tests/test_hermes_pilot_report.py\`. Expect RED.
- [ ] **Step 3: Implement** independent read projection: load audited intent mapping; query exactly matching immutable Controller job; require state="completed_mock" AND one matching receipt AND store.verify(job, receipt) before status="proof_verified_mock". Receipt record/ID alone is insufficient. Unrecognized Controller state => review_required. Use bounded safe result strings.
- [ ] **Step 4: Add regression tests**: another job's receipt, symlinked artifact, file deleted after earlier success, wrong source SHA, Hermes "done" with no receipt, fake CodexProbeResult(status="success") without a mock receipt. All render_qa_pass/video_qa_pass/publish_ready stay false.
- [ ] **Step 5: Run** \`python -m pytest -q tests/test_hermes_pilot_report.py tests/test_asset_controller_artifacts.py\`; \`ruff check shorts_studio/asset_factory/integrations tests/test_hermes_pilot_report.py\`. Expect GREEN; commit \`git add shorts_studio/asset_factory/integrations/hermes_pilot/report.py tests/test_hermes_pilot_report.py && git commit -m "feat(hermes-pilot): report only independently verified mock receipts"\`.

## Task 5: Finite Admission and Resource Policy

**Files**
- Create: shorts_studio/asset_factory/integrations/hermes_pilot/policy.py
- Modify: shorts_studio/asset_factory/integrations/hermes_pilot/bridge.py (invoke policy at admission; no change to Controller runner)
- Test: tests/test_hermes_pilot_policy.py

**Interfaces**
- Produces: frozen ResourceView(mem_available_bytes: int, disk_free_ratio: float, pending_proposals: int, accepted_this_session: int, active_mock_workers: int, codex_processes: int).
- Produces: assess_ingress(view: ResourceView) -> str returning "allow"|"warn_memory"|"blocked_memory"|"blocked_disk"|"blocked_capacity"|"blocked_worker".
- Consumes: bridge.submit_intent(..., resources: ResourceView) must use a **trusted** local resource reading/injected fixture, not anything supplied by Hermes. If the old Task 3 signature needs updating, change both signature and all tests in this task; document the change in task ledger.

- [ ] **Step 1: Write failing tests** test_resource_thresholds_and_unknown_metrics_fail_closed: 1 GiB warning threshold; <512MiB deny; disk <0.15 deny; pending >=20 deny; accepted_this_session>=3 deny; >1 active mock worker or codex_processes>0 deny. Reject negative/NaN/infinite/wrong type counters or ratios; unknown metrics blocks.
- [ ] **Step 2: Run** \`python -m pytest -q tests/test_hermes_pilot_policy.py\`. Expect RED.
- [ ] **Step 3: Implement** pure assess_ingress with exact thresholds and no subprocess or external API. One trusted snapshot per submission, then recheck pending/session counters under ledger transaction to avoid concurrency overfill. "warn_memory" may admit mock jobs if at or above 512MiB; warnings never relax disk or queue caps.
- [ ] **Step 4: Add bridge-facing regression**: test_no_enqueue_when_disk_low_or_fourth_request; assert Controller job count unchanged, no attempts, approved state preserved for future operator review. Confirm Controller's own .10 free disk gate remains unchanged; bridge's .15 is stricter.
- [ ] **Step 5: Run** \`python -m pytest -q tests/test_hermes_pilot_policy.py tests/test_hermes_pilot_bridge.py\` and Ruff on integration paths. Expect GREEN; commit \`git add shorts_studio/asset_factory/integrations/hermes_pilot/policy.py shorts_studio/asset_factory/integrations/hermes_pilot/bridge.py tests/test_hermes_pilot_policy.py tests/test_hermes_pilot_bridge.py && git commit -m "feat(hermes-pilot): gate finite mock sessions on host resources"\`.

## Task 6: Offline 3-Job Rehearsal and Failure Injection

**Files**
- Test: tests/test_hermes_pilot_e2e.py
- Modify: only integration files from previous tasks if red tests reveal a real bug. No Hermes/Codex installation, CLI integration or OS identity changes.

**Interfaces**
- Consumes: FakeHermes JSON fixture -> parse_intent -> Ledger.propose -> FakeOwnerApproval via trusted test method -> submit_intent -> existing runner.run_once(worker=MockWorker, approved_budget_usd="0") -> inspect_result.
- FakeCodex is a **pure value fixture**, never a subprocess; do not set CodexWorker enabled=True.

- [ ] **Step 1: Write failing test** test_three_distinct_owner_approved_mock_jobs_produce_verified_receipts: three uniquely keyed ProposedIntent payloads, three exact-digest approvals, 3 enqueue, 3 sequential run_once calls, 3 verified proof_sha256; no fourth, 0 real Codex calls, 0 video QA flags. Use separate isolated temp DB and artifact storage, no preexisting queued jobs.
- [ ] **Step 2: Run** \`python -m pytest -q tests/test_hermes_pilot_e2e.py::test_three_distinct_owner_approved_mock_jobs_produce_verified_receipts\`. Expect RED before integration fixture/fixes; record.
- [ ] **Step 3: Complete** minimal FakeHermes/FakeOwnerApproval fixtures and only necessary real integration fixes; no new scheduler. Simulate restart by closing and reopening both ledger and Controller DB; reconstruct results from receipts, not in-memory objects.
- [ ] **Step 4: Add failure tests** test_restart_between_enqueue_and_ledger_ack_is_idempotent, test_mock_worker_lease_expiry_stays_blocked, test_unauthorized_approval_never_executes, test_corrupt_or_missing_artifact_cannot_report_success, test_out_of_scope_codex_fake_success_not_production_qa and test_rejects_sneaky_untrusted_command_payload. Assert no duplicate attempts and no additional external side effects.
- [ ] **Step 5: Run** \`python -m pytest -q tests/test_hermes_pilot_*.py tests/test_asset_controller_*.py\`. Expect GREEN and commit \`git add tests/test_hermes_pilot_e2e.py shorts_studio/asset_factory/integrations/hermes_pilot && git commit -m "test(hermes-pilot): prove offline E2E and crash recovery"\`.

## Task 7: Operator Runbook, Security Boundaries and Full Review

**Files**
- Create: docs/operations/hermes-controller-pilot.md
- Modify: tests/test_hermes_pilot_e2e.py (only for final negative boundary tests)
- No systemd unit, installer, real Hermes config, production CLI or checkout of other feature branches.

**Interfaces**
- Documents P0 pure offline test commands, fake fixtures, exact-head Controller source pin and proof inspection.
- Documents **future** P1 separate UID/managed Python 3.14/Hermes profile, auth.adopt_external_logins=false, no Cron/gateway/auto-dispatch, no public ports, and OS-level ownership tests; not executed in P0.
- Documents **future** P2 one explicitly approved existing Codex CLI scratch run, max 1 process / 5 min, no API fallback, separate auth profile, approved source SHA/files/tests and diff. No CodexWorker.run call from new bridge.
- Documents P1/P2 rollback preserving Controller DB, local artifacts, approved Git branches and credentials.

- [ ] **Step 1: Write failing boundary tests** test_fake_hermes_cannot_directly_approve_or_modify_controller_sqlite (P0 is isolated process/test double and a non-writable directory, not an uninstalled Hermes UID), test_runbook_has_separate_p1_p2_authorization and test_bridge_does_not_dispatch_codex_or_paid_provider. Document that **real Unix UID/ACL proof cannot pass until authorized P1 installation** and must remain explicitly UNVERIFIED after P0.
- [ ] **Step 2: Run** \`python -m pytest -q tests/test_hermes_pilot_e2e.py\`. Expect RED for newly specified missing behavior/doc, record.
- [ ] **Step 3: Write** docs/operations/hermes-controller-pilot.md: clear read-only verification commands; P0 sample FakeHermes; approval provenance; 3-job max; exact head/digest evidence, resource/cost thresholds; ways to inspect/restart without double submitting; rollback and why mock PASS != video QA PASS. Keep any sample shell under an operator's deliberate execution, never imported/run by product code.
- [ ] **Step 4: Run** \`python -m pytest -q tests/test_hermes_pilot_*.py tests/test_asset_controller_*.py\`; expect GREEN. Run \`ruff check shorts_studio/asset_factory/integrations tests/test_hermes_pilot_*.py\` and \`git diff --check\`. Expect zero failures.
- [ ] **Step 5: Run full regression** \`python -m pytest -q\` and scoped \`ruff check shorts_studio/asset_factory tests/test_hermes_pilot_*.py tests/test_asset_controller_*.py\`. Record exact pass/skip counts; do **not** reuse the previous PR #57 counts. Compare reviewed branch to pinned PR #57 and ensure no modifications in Controller/Studio QA/systemd.
- [ ] **Step 6: Commit** \`git add docs/operations/hermes-controller-pilot.md tests/test_hermes_pilot_e2e.py && git commit -m "docs(hermes-pilot): document safe offline integration and approval gates"\`. Run \`git status --short\` to confirm clean new worktree.
- [ ] **Step 7: Request a fresh whole-branch review** of trust boundaries, approval authority, raw JSON, crash windows, SHA/receipt checks, no paid/production commands, exact-head CI compatibility. Fix Important/Critical issues using another RED→GREEN cycle, re-run full suite and Ruff, commit fixes; preserve review evidence. Native mode: one independent reviewer at end; Subagent-driven: task-by-task fresh reviewers plus final whole-branch review.
- [ ] **Step 8: Stop at handoff.** If owner approved GitHub push/Draft PR, push **only the isolated implementation branch** and wait for exact-head test/render-smoke. Never auto-merge, auto-deploy, auto-install Hermes, connect model OAuth or enable real Codex. P0 status may be "local tests passed" only after reading actual output; P1/P2 and 24-hour soak remain unverified.

## Final Requirements Coverage / No-Escalation Ledger

| Spec requirement | Owning task | Proof |
| --- | --- | --- |
| Exact UTF-8 schema, canonical SHA, no arbitrary commands | 1 | invalid + valid contract tests |
| Separate immutable operator approval and intent collision | 2 | ACL/path/owner + duplicate/race tests |
| At-most-once queue insertion, crash across ledger/Controller | 3 | before/after-commit crash replay tests |
| Verified local content receipt, no false video QA | 4 | byte corruption and fake-done tests |
| 4KiB, 3/20/1, 1GiB/512MiB/15%, budget 0 | 1, 5 | policy unit + bridge rejection tests |
| 3 mock end-to-end, restart, fake Codex blocked | 6 | e2e tests |
| No Hermes/Codex install, no P1/P2 launch | 7 | runbook + source audit + permission negative tests |
| Real OS UID proof and Hermes OAuth / 1 real Codex probe | **Deferred until separately approved P1/P2** | explicit stop condition; no false P0 success |
| Full 24h unattended reliability; B2; native rendered video quality | **Out of this plan** | future Asset Factory Milestones B–D |
| Existing QA gates, exact-head CI, branch isolation | 7 | regression, Ruff, review, separate approval before push |

### Execution Preflight for Approved Implementer

1. Read **both spec and this plan**, inspect PR #57, current main SHA and all active branches; stop if head changed or PR was merged without reconciliation.
2. Create a fresh named worktree from reviewed PR #57 head, not from main or the docs-only design branch. Keep PR #57 and its worktree untouched.
3. Obtain spec/plan file content from the design branch with read-only git show, or copy just these two docs into the new worktree if necessary. Do not merge the docs branch into code branch wholesale.
4. Run baseline \`python -m pytest -q\`, Ruff where applicable; only after baseline check start Task 1 RED→GREEN. Record tasks and design deviations in the Superpowers ledger.
5. Work one task at a time with review gates and small local commits, no background promise, no 24-hour daemon. The existing VPS can execute tests when connected, but installing/activating a service is not covered by code-implementation approval.

### Self-review Checklist

- [x] Each approved spec subsection maps to a task or an explicit **future authorization**, with no P1/P2 claim in the P0 acceptance.
- [x] Integration imports use actual PR #57 controller names: JobSpec, queue.enqueue, MockWorker/run_once and LocalArtifactStore.verify. Controller DB v1 unmodified.
- [x] Each task has interface definitions, RED, minimal implementation, GREEN, commit, and where relevant adversarial inputs.
- [x] No plan step instructs the operator to install Hermes/Codex, trigger a paid API, merge a PR or publish a video.
- [x] Crash after Controller commit but before Ledger commit is explicitly tested; ambiguous external work remains blocked.
- [x] Source branch and document branch separation is explicit: implementing against docs-only branch would lack the Controller.
