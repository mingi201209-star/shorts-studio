# Rumble strip film: flexible-duration implementation contract (2026-11-07)

## Baseline and isolation
- Repository default branch `main`: `fcd20fd78851b18c550b1e433bee46ee34313c1d` (verified by compare API).
- Source branch: `feat/curious-mechanics-b-causal-shot-20261101` (PR #95); 129 commits ahead of main, 0 behind at inspection.
- This independent branch is a planning/implementation staging branch. Do not merge PR #95-#99 implicitly.
- No paid GPU, VPS render/encode, automatic upload, main merge, QA threshold relaxation or deletion of 30s support.

## Evidence from code
`benchmarks/road_safety/curious_mechanics_progressive_delivery.py` hard-codes `len(unique)==900`, 900 verified source frames, video probe `nb_read_frames==900`, and duration 30 seconds. Native shard validation also assumes the old 900-frame episode. Merely editing a 48s narration/manifest is unsafe.

## Proposed film (provisional 48s, editorially adjustable)
- 0-4s: lane departure / clear hazard, without black opening.
- 4-10s: tire first contacts shoulder grooves.
- 10-18s: repeated physically coherent tire vertical displacement; contact visible.
- 18-27s: suspension and body vibration transfer, no camera-shake-only fake.
- 27-36s: driver notices, attention returns to road, hands respond.
- 36-43s: visible steering-angle change and lane recovery.
- 43-48s: concise causal recap. Every scene must align with measured narration timing.

## Implementation order
1. Freeze current source/manifest/renderer and old final MP4 SHA256 and QA receipts. Identify PR #95-#99 base/head and exact-head CI before edits or merge.
2. Introduce opt-in episode duration from canonical shot timeline; derive expected frame count as fps * duration. Retain default 30s/900 frames for legacy manifests.
3. Update shard coverage/layout and final assembly checks to use derived frame count; require contiguous frames, verified hashes, renderer generation per shard, and zero duplicates.
4. Reconcile English narration beat timestamps, ASS captions, scene semantics and diagram timing with the new timeline. Reject missing/unreviewed editorial evidence.
5. Extend procedural action shots for contact -> wheel oscillation -> chassis vibration -> driver response -> steering correction. Real object motion, not meaningless crop/zoom.
6. Scope re-render to changed shot shards only on GitHub Actions standard runners. Reuse old shards only if source, renderer, timeline and pixel identity evidence proves compatibility.
7. Validate A/B/C independently for captions, silence/loudness, black opening, visual activity, clipping, semantic alignment, exact frame count, audio duration and human first-view review.

## Test-first acceptance
- Legacy 30s episode remains 900 frames and existing interface/QA behavior remains identical.
- New 48s example produces 1440 frames at 30fps with no gaps or overlaps; changing length cannot silently reuse incompatible 900-frame assets.
- Invalid durations, non-integer frame boundaries, missing renderer generation, missing audio beat, or unreviewed editorial evidence fail closed.
- Before/after snapshots include exact commit SHA, manifest hash, source frame hashes, encoded output hash, QA receipt, and CI run URLs.
- On any regression, retain previous known-good artifacts and branch state; no main update. Repeat tests after fixes.
- Do not mark editorial PASS based only on technical QA.

## CI monitoring
Check exact-head `test` and `render-smoke` plus new targeted tests. Pending/unknown is not PASS. Existing hourly Nightshift remains separate; never claim continuous monitoring without a scheduled task or active runner.
