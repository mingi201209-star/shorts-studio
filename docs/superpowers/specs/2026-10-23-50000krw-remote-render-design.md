# KRW 50,000/Month Remote Render + Storage — Superpowers Design

**Date:** 2026-10-23  
**Status:** Conservative design and inert budget-preflight pilot; NO account purchase, credential setup, new VPS, production deployment, render dispatch, or permission to spend.  
**Existing reference:** `docs/superpowers/specs/2026-10-20-gpu-render-10x-proof.md` and `docs/superpowers/specs/2026-10-20-always-on-asset-factory-design.md`. This spec adds a *cost boundary* to existing designs rather than replacing their QA or controller.

## 1. Intent, constraints, non-goals

Owner delegates provider/payment-model choice. Choose one existing OVH VPS controller + Cloudflare R2 Standard storage + *ephemeral usage-based GPU* for approved pilots, not a monthly fixed GPU host. Use the **KRW 50,000 all-inclusive monthly planning ceiling** (OVH, object storage, rented GPU, attached disks, transfer, other fees and reserve). Owner plans to discontinue Claude; do not assume cancellation is completed. **Do not initiate any new billable account/lease before explicit spend approval.** Never render video or save image/caption outputs to Android phone without separately requested delivery. No automatic merge, publication, weaker QA, counterfeit source frames, or unreviewed E3 worker deployment.

## 2. Compared approaches

- **Chosen:** existing VPS remains the control plane; R2 Standard as immutable artifact library; quote-validated, time-limited GPU rental *only for jobs with separate spending permission*. Strong throughput potential without monthly idle GPU rent. Risk: marketplace billing is not intrinsically capped.
- **Alternative:** GitHub public runners only + R2 Standard. No new GPU expenditure but prior episode2 CPU frame `100.723s` at 1080×1920 Cycles32 makes brand-new 900 frames approximately 25 hours serial; public Actions is not an unlimited dedicated render farm. Useful for bounded tests.
- **Rejected for now:** dedicated 24/7 GPU monthly server; insufficient room after OVH within KRW 50,000 budget.

## 3. Provisional envelope (estimates, not receipts)

| Item | Monthly planning allocation |
|---|---:|
| Existing OVH controller VPS | KRW 8,000 |
| Cloudflare R2 Standard, including usage allowance | KRW 3,000 |
| GPU rental **including instance storage & bandwidth** | KRW 30,000 |
| Contingency/fees/FX/VAT variance | KRW 9,000 |
| **Total** | **KRW 50,000** |

When the actual OVH or R2 projected bill exceeds its envelope, fail closed pending owner review. A 25% quote uncertainty factor is applied to all estimated GPU provider charges; this is **not** a guaranteed maximum charge. Any unknown GPU, attached-volume, data-transfer, FX, fixed or other fee blocks the preflight. No automatic credit-card top-ups. Owner must independently verify billing controls, actual invoices and whether the provider may charge a saved card to settle negative balances.

**Provider caveat:** Vast.ai's official billing guidance says that stopped instances still incur storage charges and negative balances may be settled by automatic card charges. Do not advertise prepaid credit or an application watchdog as an absolute monthly hard cap. The only acceptable exit for a paid ephemeral instance is *verified instance deletion* and zero remaining billable associated volumes, after copying and hash-verifying remotely stored artifacts. If actual provider-side hard limits cannot be configured, the operator must explicitly accept residual billing risk before any paid launch. Do not store a provider card, login token or signed object URL in GitHub.

R2 Standard pricing: free 10 GB-month and operation quotas; paid storage $0.015/GB-month (subject to live terms). Class A/B requests, billing rounding and any extra billable operations count toward envelope. Use R2 Standard, not Infrequent Access, for active native frames. Avoid storing 900 raw 1080×1920 frames longer than needed; ensure verified lossless shard and exact content SHA before deleting any transient copy. Keep source masters, QA and provenance. Object keys are immutable hashes scoped to source SHA/renderer SHA/manifest SHA and job ID.

## 4. Immutable render handoff

1. Existing controller records approved intent SHA, source/renderer/Blender version (5.0.1 for current pilot), manifest, frame range, CPU/GPU device, exact scene profile and estimated billable wall time; state stays BLOCKED without a recent complete quote and independent owner approval for *actual spending*.
2. Inert `shorts_studio.render_budget_gate` reads an **operator-supplied quote**; it validates required prices, current FX, prior spending, 15-minute freshness, two-hour single-job cap and KRW envelope. It returns **ESTIMATE_ONLY**, never a permission token or provider rate limit. This script has no cloud, secrets, IO writes or dispatch behavior.
3. If provider/expense approval later exists, external operator leases one GPU for a bounded benchmark, reads actual active storage and bandwidth rates and checks Blender 5.0.1 Cycles GPU device activation (existing production renderer may force CPU). Only exact pinned source may be used. Fail if CUDA/OptiX is absent; never silently fall back to CPU and call it a speedup.
4. GPU worker writes independently rendered unique Cycles32 frames to provider ephemeral disk, verifies real frame hashes/provenance, uploads to R2 directly **without passing through Android/VPS boot disk**, and reads back remote digest. R2 gets original `.blend` masters and durable evidence separately.
5. Controller tracks provider instance ID and deadlines, resumes only after reading actual remote status; never create duplicate leased GPU after an uncertain API call. Upload completion and true remote read-back precede **DELETE** of provider instance and attached billable resources. Independent controller-side cleanup watchdog and incident alert are required before any real dispatch.
6. Assemble final H.264/AAC MP4 with measured English voice and thin lower captions; retain exact original 900 native frames, no temporal interpolation or mixed-source shard caching, and unchanged strict semantic/frame/audio QA. Editorial status stays HOLD until manual acceptance, with no YouTube automation.

## 5. Tests, gating and acceptance

Pilot code deliberately implements **only** quote validation and budget math; no paid integrations. Must reject missing rates, future/stale quotes, NaN/negative prices, extended hours, exhausted GPU allowance, or VPS/R2 overrun. Positive quote still states `authorized_to_provision=false` and `provider_spend_cap_enforced=false`.

**Next hard gate:** owner separately authorizes chosen provider, attached-storage and bandwidth quote, explicit chargeable minutes/cap and complete teardown; Claude subscription status may be verified then. Read-only capacity assessment and dry-run quote validation do not imply consent to order anything.

**Production acceptance later:** actual invoice and deallocation evidence + remotely retrievable source-hash-pinned 900-frame film, unchanged video QA, user-approved editorial quality; >=7 satisfactory weekly candidates remains a goal, not a promise. If projected charge, real invoice, orphan GPU disk or transfer usage are unknown, stop all new billable render dispatch and report the discrepancy.

**References:** Cloudflare R2 pricing https://developers.cloudflare.com/r2/pricing/ ; Vast billing https://console.vast.ai/faq/ ; GitHub Actions reference https://docs.github.com/en/actions/reference/limits .
