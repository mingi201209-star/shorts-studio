# Hydroplaning 3D production task

Continue work on branch `content/hydroplaning-3d`.

## Goal
Build an upload-ready YouTube Shorts production about hydroplaning using the existing common 3D infrastructure, with a continuous fixed-camera physical animation that is clearer and more watchable than the current baseline.

## Required physical sequence
1. Tire rotates over wet road.
2. Tire grooves visibly evacuate water out of the contact region.
3. A water wedge grows at the leading edge as speed/load conditions worsen.
4. The real tire-road contact patch visibly shrinks.
5. The tire visibly rises onto the water layer and loses road contact.

## Non-negotiable constraints
- Do not append hydroplaning logic into golf-ball topic code.
- Reuse common 3D primitives/infrastructure only; keep hydroplaning topic code independent.
- Keep one fixed camera/viewpoint through the physical sequence. Do not create cadence with camera orbit, crop or zoom churn.
- Meaningful visual state changes must come from physics/state changes.
- Do not weaken any existing quality gate.
- Do not upload to YouTube.
- Before changing code, re-check current main, open PRs, branch state and CI.
- If a change regresses quality versus the last known-good branch state, revert it immediately and continue from the known-good state with another approach.

## Completion
Do not stop at design. Implement code, focused tests, full regression, dedicated render workflow if needed, actual MP4 render, QA, representative-frame human review, and a PR-ready result. Keep checking CI until it finishes.