# Always-on 3D Asset Factory — design (2026-10-20, updated 2026-10-21)

Status: **DESIGN ONLY — implementation is not authorized by this document.**  
Repository: `mingi201209-star/shorts-studio`. Base `main` at `fcd20fd78851b18c550b1e433bee46ee34313c1d`.  
Purpose: continuously prepare reusable **native 3D models and meaningful shot assets** for the approved seven-episode English *Hidden Engineering of American Roads* Shorts series, rather than re-modeling a car from scratch per video.

## 1. Owner's intended outcome and immovable constraints

- A low-cost always-on cloud controller must survive a closed ChatGPT chat, an offline phone, service restart, and temporary model quota exhaustion.
- Whenever eligible work and budget remain, it should prepare useful 3D models, rigs, meaningful interactions and safe render shards for upcoming episodes, so production starts with a library of reusable assets.
- Model creation, **rendering**, and **video production** are distinct stages. Do not pretend a renderer generates new designs without source modeling instructions, procedural code, or available AI.
- Preserve native production requirements: 1080x1920, 30 fps, Cycles32, individual original frames; no interpolated/duplicated frames, fake visual changes, crop/zoom shortcuts, compromised audio or caption gates.
- English narration; no automatic YouTube uploads, PR merges, new spending, subscription/credit purchases, or silent approval-policy bypass.
- Fail closed against mismatched source hashes, license ambiguity, incomplete frame sets, unverified clips, and stale renders from incompatible source SHAs.
- Preserve existing `main`, PRs, worktrees and prior video assets; branch and test in isolation. Restore the last verified state on regressions.

## 2. Verified existing baseline / non-goals

- Main is clean at `fcd20fd` and remains unchanged; PR #51 introduced `shorts_studio/factory/contracts.py` and `planner.py` on a separate unmerged branch. This planner already fingerprints output profile, rig, visual parameters, and asset provenance and requires complete matching cache sidecars. **Reuse, do not duplicate it.**
- PR #52 fixes the seven approved topics. PR #56 is an unmerged **draft** for rumble strips; its older 30-second product was rejected as visually repetitive and must not be repackaged as new output.
- The controller VPS-1 is **already purchased and running** at the owner's initiative (2026-10-21). Its 2-vCore/4-GiB/40-GiB configuration is for orchestration and bounded Codex tasks, **not** a high-throughput native Cycles32 rendering host.
- No paid GPU running 24/7. GitHub Actions remains for bounded project CI/proof where compliant with its terms and quotas, **not** an assumed unlimited render farm.
- No new general-purpose project, public download site, data collection, unsupported third-party authentication, or change to the Shorts publishing policy.

## 3. Components and responsibility boundaries

**3.1 Cloud controller (`asset_factory/controller`, future)**

A daemon managed by systemd executes a persisted, bounded job state machine; SQLite WAL is suitable for a single-server pilot. Jobs carry `job_id`, `asset_id`, `asset_version`, `source_sha`, `input_digest`, dependency IDs, stage, current worker lease, progress receipt, attempt count, cost ceiling and timestamps. Atomic claim with fencing token and expiry guarantees only one active owner per job. On restart reconcile external job receipts before rescheduling.

The controller is continuously available, but expensive work only runs when the job is useful, capacity exists, and budget/policy permits. Avoid fake activity and infinite speculative rendering. A valid queue may be temporarily empty.

**3.2 Prioritized asset backlog**

1. **Next-video blockers:** approved episode #2 rumble-strip tyre-to-groove contact, camera framing, genuine wheel motion and human-response action.
2. **Shared road-safety assets:** the source-hash-pinned licensed 72-mesh sedan; wheels/tyres, road materials, crash-compatible road props and base lighting/rigs.
3. **Approved future-series elements:** breakaway posts, barrels, truck escape ramp aggregate, reflective road paint beads, expansion joints, guardrail deformation.
4. **Meaningful variations:** physically legible contact changes, close-up shots, mechanism reveal transitions, verified 3D animation, not turntable-only/stock-car-loop filler.

Rank via `blocked_episode_value / estimated_compute_cost`, subject to human-approved lane. An asset is not "complete" merely because a 3D file exists: it needs downstream mechanism proof and viewing-interest inspection.

**3.3 Model builder**

Choose deterministically from a hash-pinned CC0 or compatible licensed source, tested Blender Python procedural geometry, or an authorized AI-generated Blender modeling script. Preserve source URL, license, source file hash, unit scale, bounds, object hierarchy, rig contract and Blender version in an immutable manifest. Never make up a CC0 attribution or run unreviewed downloaded Blender scripts.

**3.4 Render worker**

Pulls an exact asset and scene version, immutable camera/lighting/motion configuration and source SHA; performs fast **preview only** for geometry/visibility diagnostics, then full native Cycles32 shards when approved and a suitable compute resource is available. Each output records width/height/fps, frame range, original unique frames, checksums, renderer build, canonical source digests and logs.

Cache key = SHA256(canonical asset hashes + Blender/renderer build + rig/source SHA + shot motion + camera + lighting + resolution/fps/samples + output profile). A change to any visually significant input invalidates the affected shard; speech-only changes do not invalidate visual cache.

**3.5 Asset and shot library**

Immutable, versioned manifests and content-addressed blobs for approved `.blend`/rig/scene data, native PNG shards, proof JSON and derived MP4, plus sample contact sheets. A published library entry is read-only; superseded versions retain their manifest, never silently replace old files. All downstream jobs resolve the exact content digest, not a filename or branch name.

Pilot storage must be explicitly provisioned and measured. Do not fill the VPS boot disk with unlimited PNGs. Keep the verified manifests durable; treat short-lived CI artifacts as transit, not long-term backup. Enforce disk headroom, retention policy and cleanup only for *unreferenced, verified redundant* objects, never original project source.

**3.6 Nightshift / model providers**

Claude, Codex and optional third provider may work on scoped modeling/planning steps using existing permission-review systems. Quota timeout => checkpoint, handoff to *authorized* available provider, or queue the next deterministic non-AI proof/render/test. No model quota bypass, no provider API use without approved funding. Denied actions remain denied for other providers.

## 4. Example flow

`episode-2 needs better close-up` → `asset library contains verified sedan + tyre` → `generate or refine groove geometry and shot rig` → `unit-scale/rig/license/source validation` → `sparse camera proof` → `human-interest review` → `native frame-shard render` → `full QA, immutable proof and exact digest registration` → `reuse in a future episode when the visual dependency matches`.

**Stages:** `queued`, `modeling`, `model_qa`, `preview_render`, `preview_review`, `native_render`, `native_qa`, `library_ready`, `blocked`, `retryable_failure`, `rejected`. Stage transitions are idempotent and have evidence receipts.

## 5. Failures, cost and capacity limits

- Always-on means **continuous scheduling/recovery**, not infinite free AI thinking, guaranteed 100% rendering utilization, or a full-time dedicated GPU.
- A worker heartbeat without actual per-job progress is considered stalled. Recover by lease and exact external run inspection before *any* retry. Recover interrupted original render ranges; never launch duplicate renders after uncertain results.
- Start with one native render concurrency slot for the asset factory and isolate it from approved episode delivery or CI. Increasing concurrency requires measured speed/quality and explicit resource approval.
- The owner has purchased **one** OVHcloud VPS-1 at a displayed USD 5.35/month; this existing charge is the baseline. There is no new authorization for paid Anthropic/OpenAI APIs, B2 storage, render hosts, a second VPS, or contract upgrades. Record actual invoice terms and guard future renewal risk separately.
- High render backlogs require a separate price/performance evaluation of CPU, GPU rental and storage. Do not treat public GitHub-hosted runners as an unlimited 24-hour commercial renderer.
- Pause work on an approval denial, unknown billable resource, unsafe storage pressure, missing provenance, production gate failure, or source drift. Continue safe independent tasks where possible.

## 6. Delivery and acceptance checkpoints

**Milestone A — persistence:** Test deduplication, leasing/fencing, crash/restart recovery, model cooldown and blocked job handling with fake workers. Persist progress across process and server restarts. Verify that no orphaned job repeats a paid or incompatible render.

**Milestone B — usable library:** Integrate with existing factory `contracts.py` / `planner.py` **once their unmerged branch topology is reconciled**, not by unreviewed partial cherry-picks. Produce exactly one pinned sedan/wheel/groove asset record, a meaningful mechanism-contact preview and an independently verified sample native shard. Confirm hash invalidation and license proof.

**Milestone C — real throughput:** Measure modeled/validated assets per day, accepted mechanism-ready shots, time spent by modeling versus rendering, cache hit rate, time from topic to finished video, storage cost and editorial rejection. Benchmark against the current baseline. Target seven *approved usable video candidates per week*, not seven empty or low-quality files. Keep promotion blocked until exact-head CI plus real audio/visual checks pass.

**Milestone D — 24-hour soak:** On provisioned server, run a 24-hour bounded resilience experiment with a finite useful backlog. Force daemon restart, simulated quota unavailability, canceled/uncertain render, stale worker lease, storage pressure and CI error. Every job must resume or remain explicitly blocked with durable evidence; no duplicate native shards or unauthorized charges.

## 7. Concrete controller-and-storage pilot (2026-10-21 design addendum)

This remains **design-only for future deployment**, but the one VPS-1 controller host has already been provisioned and paid for by the owner. The design does not authorize new cloud accounts, services, paid API traffic, B2 buckets, additional hosts, or an unattended execution loop.

### Proposed components

- **Controller (already installed):** OVHcloud VPS-1 2027, Singapore region; x86-64 Ubuntu 24.04 LTS, 2 vCore, 4 GiB RAM, 40 GiB NVMe, displayed **USD 5.35/month**. Measured about 35 GiB free after installation on 2026-10-21. Future service design: systemd-managed orchestration, SQLite WAL job state, manifests, bounded workspaces and monitoring. The local disk must not become a high-resolution frame archive. Promotional automated backup availability was displayed during checkout but must not be assumed sufficient, retained, or restore-tested.
- **Durable objects:** Backblaze B2 private bucket using an S3-compatible endpoint and separate limited-scope application keys; published starting price USD 6.95/TB-month with the first 10GB free, and published free monthly egress up to 3x average stored volume. The billable amount depends on average stored byte-hours, region, egress and eligible operations. No promise that a 100GB cap will accommodate three months of original frames.
- **Workers:** GPU/CPU render nodes are independently allocated only when expressly funded and policy-compatible; GitHub Actions continues to host bounded software development validation and quality proofs, not an assumed 24x7 commercial fleet. Workers fetch immutable input digests, render assigned native ranges, upload staged shards, and submit signed or hash-verified receipts.
- **Budget reference:** the **actual VPS order displayed USD 5.35/month**, not an advertised lower-region starting price. Future B2 storage is not yet provisioned or charged; when approved, meter exact retained bytes, operations, and egress. The owner's earlier KRW 20,000/month baseline and potential KRW 50,000/month after a *hypothetical* Claude Pro cancellation are planning scenarios, **not** blanket spend authorization. Do not cancel Claude Pro until a sustained alternative is verified and the owner chooses to do so. Require per-provider approved ceiling and independent billing alerts.

### Persistent control flow

`approved_episode -> deterministic backlog -> SQLite state claim + lease/fencing -> asset/provenance check -> worker allocation -> original-frame render -> verify native QA -> upload immutable B2 objects -> atomic completion receipt -> final audio/film QA -> release candidate`.

The VPS persists `job_id`, episode, priority, exact source/render/manifest digests, attempt number, lease owner/expiry, frame range, artifact checksums, estimated cost, approved budget and terminal outcome. Files are staged locally and **verified remotely** (size, digest, complete range and manifest provenance) before a job is marked durable; cleanup must not remove a sole good copy. On restart, reconcile remote receipts and any external worker state before rescheduling. A stale heartbeat alone never licenses duplicate paid work.

### Security and operations

- SSH keys only; firewall deny by default; no public unauthenticated job-dispatch endpoint. Store provider tokens and B2 keys in root/service-owned secret files outside the repository, with least privilege, private bucket/prefix limits and no delete right on production source masters. Rotate compromised keys. Logs scrub keys and URLs containing credentials.
- Keep the SQLite checkpoint database on local NVMe and write encrypted, checksum-verified off-host snapshots to a protected B2 prefix with an independent restore mechanism. Restore is tested; simply having daily VPS snapshots does not count as validated recovery.
- Monitor disk pressure, state DB integrity, stuck leases, outstanding unverified uploads, queued work, unusual worker charges and last verified complete video. Stop dispatch when storage headroom or billing evidence is inadequate. Reject SHA drift and incompatible stale frames.
- Keep a small temporary download/render staging area with a hard quota. Preserve original 3D models, exact provenance records and accepted source frames unless retention requirements and redundant verified copies justify deletion. Monthly stored bytes and estimated bills are reported.

### Pilot acceptance before any recurring commitment

1. **VPS preflight completed:** user purchased VPS-1 at displayed USD 5.35/month in Singapore and SSH access is verified. Confirm actual contract/renewal terms from billing records; **B2 account and spending ceiling require separate explicit authorization**. No new VPS order is needed for the controller pilot.
2. With test/mock workers and without paid render compute, demonstrate a single durable job from queue to complete B2 receipt; verify the exact digest on upload and on download.
3. Simulate network loss, duplicate submissions, daemon restart, expired lease, storage 95% full and quota exhaustion. Jobs either recover once or remain visibly blocked, with no duplicate dispatch, data loss, silent source downgrade or unapproved charge.
4. Reboot the controller, restore its SQLite state from B2, reconcile external artifacts and prove that a 30-second native frame manifest rejects any missing or foreign frames.
5. Only then test a production episode with the existing exact-head GitHub verification and quality gates. No automatic PR merge, YouTube publish, large render fleet, or month-two charge is authorized by a successful pilot.


## 8. Verified controller readiness and bounded deployment design (2026-10-21)

### 8.1 Verified facts versus remaining gaps

2026-10-21 operator checks establish the following **on the owner's provisioned VPS**:

| Component | Observed evidence | Meaning |
| --- | --- | --- |
| OS/compute | Ubuntu 24.04.5 LTS, x86-64, 2 vCPU, 4 GiB RAM, about 35 GiB available disk | Suitable as control plane, not proven for Blender render throughput |
| Access | `ubuntu` SSH public-key authentication from Termux; password and root SSH logins disabled; UFW active, only 22/tcp allowed | Secure remote shell was tested; keep original emergency access and key recovery plan |
| Codex | `codex-cli 0.163.0`, `codex login status` reported `Logged in using ChatGPT` | Subscription login works now, but unattended quotas/refresh are **not** guaranteed |
| Sandbox | Installed Ubuntu `apparmor-profiles` and applied distro `bwrap-userns-restrict` profile; `bwrap --unshare-user --unshare-net --ro-bind / / /bin/true` passed with global AppArmor restriction still enabled | Retain enforced sandbox; no `dangerously-bypass-approvals-and-sandbox` or global userns restriction disabling |
| Actual coding | Codex used file editing tools to write `~/codex-test/hello.txt`, then wrote `frame_jobs.py` and `test_frame_jobs.py`; four Python unittest cases and separate 900-frame continuity/parameter checks passed | Proves bounded scratch code-edit/test feasibility only |
| Existing product | `shorts-studio` is **not yet cloned to VPS**; root `main` and draft PR #56 remain unmodified | Product integration, permissions, CI and full regressions not yet tested |
| Storage / fleet | B2 not connected; no renderer worker purchased or allocated; no resident Nightshift controller service | Future milestones, not current working features |

Private host/IP, account, passwords, tokens, personal email, SSH key and one-time sign-in codes must **not** appear in public GitHub docs or git history. Phone-to-VPS SSH through a passphrase-protected, time-limited local `ssh-agent` enables operator access **during this chat**, but is not an always-on VPS control channel. Do not copy an unlocked SSH private key or ChatGPT credential from the phone to VPS.

### 8.2 Pilot scope and low-risk rollout

**Option selected:** continue the existing repo's controller concept in an isolated branch, deploy *only after plan approval*, and validate with mock workers. This is preferred to either (a) moving the Android Nightshift supervisor wholesale, with environment-dependent stale checkpoints, or (b) building a larger multi-provider scheduler or commercial render farm immediately.

A. **Repository topology and read-only sync:** verify GitHub's current `main`, PR #51-56 dependency chain, source hashes and CI; clone the repo on VPS under a dedicated workspace without changing upstream branches. Record and respect user-defined instructions. Prepare a distinct development worktree/branch *only when the implementation plan is approved*. Never rely on the Android Nightshift's stale checkpoint as a queue to replay blindly.

B. **Local persistent manager:** minimal `shorts_studio/asset_factory/controller/`-compatible Python code (subject to branch inspection), SQLite WAL on local NVMe; explicit `jobs`, `attempts`, `leases`, `receipts` and `events` tables. Public job status contains no secrets. Fixed `job_id` + input SHA + source/renderer digest define uniqueness. Run one exclusive manager instance with systemd `Restart=on-failure`, service-user isolation, journal limits, database checkpoint and disk headroom checks.

C. **Permission-aware worker adapter:** start with deterministic fake/dry-run workers. After approval and successful tests, a Codex adapter may execute narrowly scoped `codex exec` in a clean worktree using `--sandbox workspace-write`, an explicit task spec, bounded timeout, finite concurrency, and a receipt verified by independent commands. Never interpret Codex exit code 0 as successful work without checking expected files, `git diff`, test output and exact head. If login/session quotas fail, checkpoint as `blocked` instead of attempting unauthorized API fallback or launching another paid agent.

D. **Approval boundary and external effects:** allowed mock jobs only until explicit next-stage approval. No unattended `workflow_dispatch`, automatic PR merges, pushes to `main`, YouTube uploads, third-party auth, external renderer procurement, or permanent user instructions to run new paid AI services. If planned real production jobs need money, user approval or source licensing that is not documented, halt that job with evidence.

E. **Storage staging:** keep controller WAL DB, event receipts and bounded cache locally with daily off-host backup requirement noted as **not yet satisfied**; design a B2 adapter with private bucket, least-privilege keys, checksum verification and safe retention, but test it with a local filesystem double until an account and charges are separately approved. No deletion of source masters or last known good frame versions.

### 8.3 Pilot acceptance and evidence

1. In a newly approved isolated branch, unit tests pass for enqueue idempotency, correct lease ownership/fencing, worker timeout, restart recovery and failed SHA-identity checks. No duplicate execution of an ambiguous external job.
2. Start/stop the mock manager using a temporary test service; restart it and verify SQLite WAL state and deterministic receipts survived without missing or repeated work.
3. A **bounded** Codex scratch task can produce an audited diff and tests under the real sandbox; quota-unavailable and authentication-expired simulations lead to a safe blocked state.
4. Simulate disk at/above policy threshold, network interruption and B2-unavailable status. Confirm that unverified artifacts remain protected and no remote spending or dispatch occurs.
5. Verify `main` and stacked PRs unchanged, no private credentials in commits/logs and existing native 1080x1920/Cycles32 video/audio/subtitle gates remain intact. Production film is not claimed unless exact-head, full real-source QA separately passes.
6. Only after the above, a finite 24-hour soak with approved useful work and tested restore procedure; this is **not** implied by the successful scratch coding proof.

### 8.4 Design review decision still required

Review this **updated specification** and approve it explicitly before writing the implementation plan under `docs/superpowers/plans/`. The plan must separate no-spend mocked persistence tasks, optional Codex integration, and later B2/renderer procurement into independently testable gates. The owner then reviews that plan and selects how it will be executed. A spec approval is not automatic permission for unattended live jobs or new cloud purchases.

## 9. Hand-off rules

This specification is a design artifact, not a running process or a request to dispatch a worker. The **host exists**, but a running 24-hour orchestration service does not. The user reviews this updated spec, then a stepwise implementation plan is written and reviewed before isolated-branch implementation. Never use this design to claim the 24-hour loop runs, B2 is live, or PR #56/episode 2 is complete.
