# Controller → Native Shorts Evidence Integration — Design

**Date:** 2026-10-22  
**Status:** DESIGN FOR OWNER REVIEW — no execution authority  
**Base:** Draft PR #59 `d988d4df8f578654320e417ddd31b8376bd2d0ec`, stacked on PR #58 → PR #57. **Never merge or deploy by implication.**

## 1. Goal and measurable exit criteria

Turn the previously proved *Hermes proposal → Codex scratch → Controller mock receipt* into a trustworthy path that can recognize and audit **a real Shorts Studio video**, without equating mock success or model output with an upload-ready MP4. The first deliverable is one newly rendered 30-second English *Shoulder Rumble Strips* episode (#2), source-proven and separately reviewed; the operational ambition is seven independently verified Shorts candidates a week, not seven fake PASS statuses.

A technical candidate meets all of: exact pinned input/source/renderer SHA; genuine source 3D frames 1–900 at 30fps (1080×1920, Cycles32) with no held/cross-version native shards; actual H.264 MP4/verified AAC speech; measured captions and final semantic/visual/audio QA; immutable digest evidence. Editorial acceptance, attractive pacing, natural voice and manual YouTube upload remain **separate** human decisions. Production throughput is measured as an end-to-end total including brand-new native render; a pre-rendered cache-only 128-second assembly is **not** proof of a five-minute new-film render.

## 2. Current truth and boundaries

- `shorts_studio/asset_factory/controller/runner.py` admits **only** `MockWorker`. `JobSpec` presently accepts `mock` or `codex`; `CodexWorker` is independently scoped and disabled for queue execution. `completed_mock` is not render QA.
- `shorts_studio/asset_factory/integrations/hermes_pilot/` validates untrusted proposals against separate operator-owned approvals. Its SQLite identity, dedup, leases/fencing and immutable local SHA256 receipts are the authority for **mock** work; Hermes model text is not approval.
- Episode #2 Draft PR #56 is **not merged**. Its six-shot Cycles32 proof at `b8bed7c` was successful; the older 900-frame video was rejected editorially. Safety commit `91d0932` removes automatic push triggering from the obsolete old-frame recovery workflow and gates its manual invocation against the original SHA. **Never mix the old video’s shards with the new renderer.**
- Android has ~2.2% free space, below the existing 10% Controller disk admission threshold. Do not disable that threshold or perform a 900-frame phone render.
- Existing OVH VPS and GitHub Actions are resources, not new spending authority. Do not start an expensive full 900-frame run until quota/budget and the exact SHA/asset plan are checked. No new paid API, storage, credentials transfer, public endpoint, automatic merge, release, deploy or YouTube upload.

## 3. Approaches considered

**A. Make `run_once` execute arbitrary renderer jobs:** rejected. This would bypass its explicit mock-only admission model and reclassify jobs as successful before video proof.

**B. Let Hermes dispatch GitHub jobs or write Controller SQLite directly:** rejected. It collapses untrusted intent into execution authority, enables duplicates and risks accidentally consuming billable Actions minutes.

**C. Recommended: staged, read-only evidence intake first, then independently authorized production dispatch.** Keep MockWorker/old tests unchanged. Read actual Shorts Studio artifact bundles through a narrow, separately tested verifier, create an audit-only `NativeEvidenceVerdict` only when all physical/video reports agree, and link this to Controller correlation identities without upgrading the mock receipt. Only after distinct approval implement a new sealed rendering worker/queue state with explicit operator job approval, fencing, budget and retries.

## 4. Phase E1 — verified evidence boundary (first code milestone after approval)

Read-only function `inspect_native_evidence(bundle_root: Path, expected: NativeEvidenceExpectation) -> NativeEvidenceVerdict`, housed in `shorts_studio/asset_factory/integrations/native_evidence.py`. Caller supplies exact expected source commit, manifest+scene hash, renderer code hash, frame count, FPS, dimensions, narrator language, approved output paths and SHA256 digests. Paths must be confined to an immutable receipt directory; refuse symlinks, traversal, special files and hash or stat races; require bounded sizes and counts. Reject missing, stale, externally linked or unverifiable reports.

Check physical media independently using the existing `ffprobe`/FFmpeg helpers or verified vendor primitives, not only arbitrary JSON `PASS` strings. Independently establish 30.0 seconds / 900 decoded video frames / 1080×1920 / 30fps / H.264 / actual AAC speech; inspect final MP4 timestamps and audio presence. Validate the build's source-frame provenance indices 1..900 and each shard's strict single renderer/source identity. Consume existing executed `episode2_film.py` native shard validation, semantic visual QA, real captions/word-timing, final_video_qa/retention and final-render-integrity **without weakening their criteria**. Every required report must exist and independently report an evaluated PASS. `NOT_EVALUATED`, cached legacy shards or checksum mismatches fail closed. Use the existing project verification logic instead of creating a duplicate looser QA implementation.

Result fields: `status` enum (VERIFIED_TECHNICAL / BLOCKED / NOT_EVALUATED), sanitized reason, expected source identifiers, media/content digests, report digests, measured durations/counts, verification time and `editorial_status=HOLD`. It must **never** contain `publish_ready=True`. Reject anyone supplying unsupported or model-generated success fields as authority. The verifier performs no rendering, upload, publishing, queue dispatch, credential lookup or status mutation.

Existing older rejected clips are useful **negative fixtures** for source mismatch, never a positive current-film certification. An independent valid fixture must be created without asserting its visual appeal.

## 5. Phase E2 — Controller audit linkage (separate approval after E1)

Record the completed `NativeEvidenceVerdict` content hash in an append-only, owner-controlled evidence ledger keyed by exact `job_id/input_digest/source_sha` **and distinct from `completed_mock`**. A reporting view may show `render_evidence_verified=True` only with fresh full bytes/hash read-back; `video_qa_pass=True` only if the exact final video evidence passes; `publish_ready` remains false until explicit editorial signoff and is never a controller instruction to publish. Do not infer `completed_render` from a mock receipt, Codex test result, Hermes Kanban “done”, GH Actions green mark, or a fabricated sidecar.

Replay same ID + identical bytes returns the same verdict without new tasks. Same ID/different digest, unknown renderer/source SHA, missing artifact, expired GitHub artifact or aborted transfer blocks. Crashes between storing evidence and recording ledger recover conservatively by reconciling immutable bytes, never by launching a second render.

## 6. Phase E3 — actual rendering dispatch (new owner approval)

Only after E1/E2 review and separate explicit permission: define a render-specific, allowlisted controller job kind/stage and operator-issued approval matching the exact intent hash and cap. Add a separate `run_native_once` implementation with fixed allowed GitHub workflow / pinned commit / manifest and no arbitrary shell, rather than extending `run_once` with a permissive worker. Enforce existing resource limits, unambiguous remote run identity, one bounded active job, lease fencing and artifact recovery. Missing budget evidence, trigger ambiguity, incomplete source frame library, stale provenance, API error or unknown run state **blocks**, not retries or spending. Budget-aware job submission is an owner action; no webhooks, 24-hour Hermes daemon or unattended recurrent billable workflow without separate authorization. Only real measured runs can support throughput claims.

## 7. Test and operational acceptance

- E1 TDD RED → GREEN: allow a valid independently generated fixture, reject fabricated `PASS`, symlinks/path escape/TOCTOU, mismatched SHAs, duplicate/missing/held frames, mismatched renderer shards, incorrect resolutions/FPS/codecs/duration, no speech/AAC, unmeasured captions, `NOT_EVALUATED`, and corruption after receipt creation.
- E2: same ID+digest idempotent; same ID different digest fail; crash-before/after ledger write; lease expiry; ledger/bytes disagreement fail; Hermes completion/MockWorker/Codex output never promote video status.
- E3 (only when separately authorized): operator digest gates, zero budget unapproved dispatch blocked, unknown GH status blocks, run ID captured once, recovery does not double-dispatch, 3D+caption+audio QA executed against actual completed MP4. Existing unit/full pytest, Ruff, and exact-head GitHub test/render-smoke CI must remain green with no gate weakening.
- Measure actual cost/time of brand-new native frame rendering separately from pre-existing cached assembly. Check the original 900-frame 30-second film manually: first 5 seconds, meaningful visual changes, physics/visual comprehensibility, natural voice, subtitles, boredom/retention risk. Human approves the candidate **before** manual upload.
- Regressions restore the last verified-good source/workflow/settings in their scoped branch, preserve receipts/checkpoints and rerun exact-head CI. Never erase someone else's worktree changes.

## 8. Review and approval gates

This document is a Superpowers **architectural spec**, not an implementation approval. The requested overall outcome does not waive distinct approval for real external dispatch, new cloud spend, automated deployments, merging or publication. After user review of this written spec, create a TDD implementation plan with small isolated commits: E1 standalone verifier → E2 receipt linkage → separately authorize E3 safe execution → real episode proof and editorial review. Each phase must end with concrete SHA, tests, CI and artifact evidence; no “completed” claim based on model narration alone.
