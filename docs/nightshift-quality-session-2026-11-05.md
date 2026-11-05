# Shorts Studio fresh quality session — 2026-11-05

Status: initialized; implementation not started.
Baseline: main fcd20fd78851b18c550b1e433bee46ee34313c1d (verify again before code changes).
Related unmerged work: PR #95 visual causal shot; #96 department graph; #97 real assembly/QA receipts. Do not cherry-pick or duplicate without inspecting head and CI.

## Punch list
- [ ] Inspect PR #95–#97 heads, dependencies, latest checks, and any existing Nightshift ownership/STOP state. Do not run a second worker against an active session.
- [ ] Review real 90-frame driver proof against visible driver steering/gaze and shot causality; write timestamped HOLD/PASS evidence, not assumed acceptance.
- [ ] Fix the smallest confirmed visual or narration mismatch on an isolated branch, test-first.
- [ ] Re-render only changed frames via standard GitHub Actions runners; verify hashes, semantic alignment, audio, captions and editorial gates independently.
- [ ] Verify exact-head CI to terminal outcomes, record receipts and regression comparison. No merge without approval.

## Invariants
No VPS render/encode; no automatic YouTube upload; no payment; no main merge; preserve main.py/create_scene interfaces; no fabricated PASS. If regression appears, restore previous working state before proceeding.

## Continuation
Next action: check PR #97 latest head and CI, then confirm no overlapping Nightshift worker before any implementation. This document is a planning handoff, not evidence of completed implementation or a live background process.
