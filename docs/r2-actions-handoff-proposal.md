# Proposal (read-only investigation, nothing connected): GitHub Actions -> R2 temporary storage -> verification environment

Written 2026-11-15 after reading PR #65 (`feat/r2-verified-transfer-20261024`, draft, base `design/50000krw-budget-gate-20261023`) and its operator contract
`docs/r2-handoff-operator.md`. No R2 credential was used, no request was made to Cloudflare, no workflow or code was changed for this.

## What exists today (PR #65, draft, offline-tested only)
- An opt-in CLI `python -m shorts_studio.r2_handoff` (`plan` / `apply` / `resume` / `verify` / `status`) for moving a file in bounded chunks to the bucket
  `shorts-studio-media` under a per-episode namespace, with durable budgets, a single writer per host, a manifest written last, and GET-only independent
  reconstruction with SHA-256 comparison. A byte-verified file still carries `MEDIA_QA_PENDING` and `upload_authorized=false`; R2 handoff is not a YouTube upload.
- It authenticates through the **Wrangler OAuth profile on the OVH host** (no API keys in argv or source) and is meant to run **on that host**.
- Its own activation gates are still open: the installed Wrangler distribution has not been audited (credential/log handling), the missing-key error fixture is not
  verified, and natural-expiry OAuth renewal has never been observed. "Default audit gates block real activation."
- Limits written in the contract: 32 MiB chunks, <= 64 chunks and 2 GiB per job, 128 MiB hard object ceiling. Budget planning: KRW 50,000/month in total and
  KRW 3,000 for R2 are allocations, not enforced caps; actual Cloudflare usage must be checked independently.

## Fit for the problem we hit (getting a rendered MP4 out of a GitHub Actions run)
The blocker was reading results back in this sandbox: job-log reader cap (~285 kB per job), artifact/log download hosts that change per job and are not allow-listed.
The PR #65 design does not solve that as it stands, because
1. it runs on the OVH host with OAuth, whereas the producer here is a GitHub runner (no Wrangler OAuth profile there);
2. its gates are not yet passed, and it says explicitly that it must not be activated without separate authorization.

## Proposed design (needs separate approval before any step)
1. **Producer (Actions):** a final job uploads the review MP4 (about 2-15 MB for the opening, tens of MB for a whole film) to a dedicated prefix such as
   `tmp/review/<run-id>/` using an **S3-compatible R2 token scoped to that bucket and prefix, write-only**, stored as a GitHub Actions secret by the owner.
   The job prints the object key and the file's SHA-256 (small log lines).
2. **Consumer (this verification environment):** a **read-only** token (list/get on the same prefix) stored through the session's credential form; one stable host,
   `<account-id>.r2.cloudflarestorage.com`, added to the environment allow-list (a single exact host, unlike the per-job blob hosts).
   Download, recompute SHA-256, compare with the printed value; reuse the PR #65 principle (GET reconstruction decides; HEAD/ETag do not).
3. **Retention:** an R2 lifecycle rule that expires `tmp/review/` objects after 1-3 days; nothing production-bound is stored there; no public bucket URL, no presigned
   URL printed in logs.
4. **Guards kept:** `upload_authorized=false`, no YouTube upload, free GitHub runners only, no paid GPU.

## Cost and access (to be checked against Cloudflare's current price list before approval)
- R2 has no egress fee; storage is billed per GB-month and operations per million. A few review clips a day are far below the free allowance (10 GB-month storage,
  1M class-A and 10M class-B operations per month as of my last knowledge - verify), so the expected cost is about zero; the KRW 3,000 R2 allocation is not at risk.
- Access: two tokens with the least privilege above; neither can list or touch other prefixes. Rotation by the owner in the Cloudflare dashboard.
- Risks: a token stored as an Actions secret is readable by workflows on this repository (only on branches that run it); protect with a prefix-scoped write-only token and
  a short lifetime. The PR #65 audit gates concern the OVH Wrangler path and stay separate.

## What I need from you before anything is connected
1. Approval of this direction (or a different one), and whether to use the new prefix-scoped S3 tokens or wait for the PR #65 Wrangler path.
2. The owner creates the two tokens (I cannot, and should not see the values); the consumer token is entered through the session's credential form.
3. Approval to add the single R2 host to this session's environment allow-list.
Until then the log-chunk method stays as the fallback (it works; it is just cumbersome).
