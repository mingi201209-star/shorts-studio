# KRW 50,000 Remote Render Budget Gate — Implementation Plan

> **For agentic workers:** Review this plan and its linked spec before implementing live GPU or storage integration. Never treat `ESTIMATE_ONLY` as external spend approval.

**Goal:** Preserve exact Shorts rendering/QA while preventing *unreviewed* cost proposals from automatically becoming billable work; keep Android free of video artifacts.

**Architecture:** A completely inert Python evaluator handles short-lived, manually supplied GPU quotes. A later, separately approved controller/worker integration would use provider account information, R2 and external cleanup; that live path is explicitly excluded from this change.

**Tech Stack:** Python 3.11+, decimal arithmetic, datetime, pytest, GitHub CI; existing OVH VPS and planned R2/GPU are not touched.

**Spec:** `docs/superpowers/specs/2026-10-23-50000krw-remote-render-design.md`

## Global Constraints
- All recurring server charges total at most KRW 50,000 planned: VPS 8,000; R2 3,000; GPU 30,000; reserve 9,000.
- The evaluator cannot be presented as a provider-enforced hard cap.
- No credentials, card use, auto-topup, new cloud instance, disk, GitHub rendering or transfer.
- Do not change existing `main`, CI quality floors, render source, cache contract, YouTube-upload policy or Android storage.
- Existing PR60 controller E1/E2/E3 approval stages remain separate.

## Review Focus
1. Provider quotes omit attached disks or bandwidth: reject, never assume zero.
2. A quote is stale, future-dated or missing its timezone: reject.
3. FX/fee fields have NaN, negative, bool, infinite or unknown entries: reject.
4. GPU allowance is depleted or VPS/R2 allocation unexpectedly increased: block even if GPU hourly rate looks cheap.
5. A valid estimate is mistakenly treated as a lease permit: explicit false authorization and warning in result.

### Task 1: Pure spending estimator

**Files:** `shorts_studio/render_budget_gate.py`; `tests/test_render_budget_gate.py`

- [x] Add tests for valid/manual complete quote, malformed fields, timestamp, spent-to-date, external fees, lease-duration cap and no authority to provision.
- [x] Implement `estimate_gpu_lease(quote: dict, *, now: datetime|None = None) -> dict` with Decimal; no provider clients and no stdout secrets.
- [x] Add `python -m shorts_studio.render_budget_gate --quote <local-json>` dry-run CLI; exit 0 for an in-budget estimate, exit 2 for block, regardless of actual authorization.
- [ ] Verify full pytest, Ruff and independent head-pinned CI after the branch is pushed. Do not claim verified without terminal CI evidence.

### Task 2: Controller/operator rollout plan (NOT AUTHORIZED for execution)

- [ ] Review PR57–60 controller branch dependencies; avoid cherry-picking mock worker code as real dispatch.
- [ ] Compare identical CPU/GPU Blender Cycles32 samples under separately authorized short lease and real quotes; record cold-start, IO, image quality and true cost.
- [ ] Propose separate approved R2 enrollment and immutable objects/manifest lifecycle; verify read-back before deleting temporary disk.
- [ ] Implement a provider-side maximum expense mechanism where available, plus remote controller kill/destroy watchdog and actual monthly statement reconciliation. If a true hard cap is impossible, report residual liability and block automatic unmonitored dispatch.
- [ ] Create isolated follow-up PR only with a fresh owner approval for paid integrations and remote resource changes.

## Release status
Quote evaluator is **only a planning safety tool**. No GPU benchmark, R2 bucket, paid lease, VPS deployment, upload, final film or editorial approval is part of this plan.
