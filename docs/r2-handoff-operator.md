# R2 single-writer handoff: operator contract

Status: opt-in offline-tested implementation. Not deployed, not a daemon, not a production film, and not proof that OAuth renews unattended on OVH. Existing manual Wrangler pilot and S3 uploader are unchanged. No service or renderer starts this CLI automatically.

## Safe local planning

Run from the reviewed checkout on OVH, using the project's Python environment. This example only reads/hashes an approved local file; replace account, path and UTC deadline. It makes no network requests and reads no OAuth credentials. Do not put tokens in arguments or source files.

```bash
python -m shorts_studio.r2_handoff plan \
  --file /absolute/path/to/approved.json \
  --account YOUR_32_HEX_ACCOUNT_ID --bucket shorts-studio-media --namespace episode2 \
  --max-bytes 1048576 --max-data-ops 320 --max-token-fetches 320 \
  --deadline 2026-10-24T12:00:00+00:00
```

`--save-plan` additionally copies protected chunk snapshots into the OVH spool and records a STAGED job; it still makes no network request. Identical saved input reuses its recorded identity. Use only approved non-secret source formats. Native frame/video quality is not reduced to fit the transfer bounds.

`status --job <id>` reads the local ledger without credentials, network or resuming work. State defaults to `~/.local/state/shorts-studio/r2-handoff`; an explicit state-root does not change the fixed account/bucket lock location `~/.config/shorts-studio/r2-locks`. All cooperating jobs on this host must use this same owner HOME/lock directory. No global R2 lock is claimed; no other host/dashboard writer may modify this managed namespace during a job.

## Commands that require deliberate activation

`apply` and `resume` require an existing recorded job, `--apply` and an absolute `--wrangler` path. They do not start just because a job exists. `verify` requires account/bucket/namespace, manifest key plus expected manifest SHA, destination and explicit limits; without `--read-remote` it is a local preview. With that flag it is GET-only, needs no original file/spool, and returns DOWNLOAD_VERIFIED only after complete reconstruction; it never promotes an upload job or a film into production readiness. Existing destinations, including raced-in files or symlinks, are never replaced.

GET-only verification returns its durable job ID in success and blocked receipts. Resume that same ID with `resume --job <id> --apply`; it stays GET-only and retains consumed counters.

An explicit resume extension supplies all four new byte/data/token/deadline bounds plus `--reason`; immutable identity, consumed counters and per-operation retry history remain. No counter is refunded for a command whose execution is uncertain. A changed original source requires a new plan; remote wrong bytes block rather than overwrite as repair.

Initial limits: 32 MiB chunks, up to 64 chunks and 2 GiB per job, 128 MiB hard object ceiling and 1 MiB manifest ceiling. Explicit maximum data/token operations each <=1,024; 320 is the proposed initial data budget. Upload minimum is 4N+4 data/token calls; GET-only verification minimum is N+1. Retry attempts are included in budgets, never additional free calls. Logical read attempts are separated by preflight/readback/reconstruction stage, and stage retry limits persist through restart. Local limits do not include other actors' requests and are not a provider billing cap.

## Credential and missing-key feasibility gate

No live credential command was executed for this implementation. A previously working short-lived OAuth token and the official docs are not proof that the installed distribution refreshes safely or writes no secret logs. Public source lookup of the recorded release was unavailable and the prior SSH agent was no longer accessible; installation audit remains pending. Do not create an approval receipt merely to suppress AUTH_REQUIRED.

Before any separately authorized live use, inspect the exact existing Wrangler 4.152.0 distribution read-only on OVH, record its executable entrypoint SHA-256, verify its dependency/version identity, credential replacement ownership/modes and all disk/telemetry logging paths. Confirm that `auth token --json` uses the expected profile and that any secret-bearing data is not logged. Then record the actual findings in an owner-only JSON audit file under the same private HOME (default `~/.config/shorts-studio/wrangler-audit.json`). Required evidence fields are `version`, `entrypoint_sha256`, `credentials_write_private` and `secrets_logging_safe`; both booleans must be true based on observed source/installation evidence. They do not mean natural-expiry renewal has passed. There is intentionally no command that auto-generates or approves this record.

New-object creation additionally needs `missing_key_message_verified=true` only after establishing the exact pinned-release missing-object error fixture. The current adapter accepts only return code 1, empty stdout and exact trimmed stderr `The specified key does not exist.`; anything else, including mixed auth/missing messages and missing bucket, blocks PUT. If the real CLI format differs, collect a sanitized fixture, add a RED/GREEN regression and review the classifier; never enable a substring fallback. Default is unknown/blocking.

The private OAuth TOML must live at `~/.config/.wrangler/config/<profile>.toml`, with owner-only regular file and owner-only profile parents. Symlinks, unexpected HOME/profile/config, ambient API key/token overrides and grant type mismatch block. Only the official CLI may rotate tokens. Capture is private and bounded; no secret is passed through argv or emitted in receipts. Data commands explicitly pin CLOUDFLARE_ACCOUNT_ID in their child environment.

AUTH_REQUIRED means stop for operator inspection/re-authentication, not repeated login. WAIT_AUTH_WINDOW means the official command returned a token with less than 120 seconds left; the job checkpoints and releases locks. Resume explicitly later so an actually expired token may refresh; do not edit expiration timestamps. Perform any manual Wrangler login/logout only with the coordinator stopped, respecting the same profile lock ownership rule. No browser opens automatically. Android is rejected for all media commands.

## Failure, recovery and retention

The deadline clock starts before source validation. OAuth acquisition is bounded by the remaining time, and the deadline is checked again before starting data commands. Every remote GET/PUT checks the local disk floor before credential acquisition or reserving remote work. Source planning rejects FIFOs without waiting and stops if the sealed source grows.

Each request runs under a private supervisor holding inherited account/profile lock descriptors. Coordinator death closes a lifeline; the supervisor terminates the request process group before releasing ownership. If a kernel-blocked child cannot terminate, ownership stays held rather than permitting an overlapping writer. This is Linux host-local cooperation, not protection against another host or malicious same-UID code.

Every PUT timeout/unknown outcome is reconciled by GET before another PUT. HEAD, ETag, local success flags and manifest existence are insufficient. Every resume checks source and staged hashes and re-fetches previously verified chunks. A manifest is uploaded last, and independently downloaded/reconstructed before REMOTE_VERIFIED. Disk shortages, deadlines, corrupted/newer SQLite schemas, permission errors or wrong remote bytes leave source and durable evidence intact. Temporary per-request readbacks can be discarded; original sources, staged chunks and saved reconstruction spools have no automatic cleanup command. Report orphan spools for separate owner review.

Rollback disables only this opt-in CLI/new integration and returns to the unchanged manual pilot; preserve failed receipts/source and do not reset main. A byte-verified video still has MEDIA_QA_PENDING and `upload_authorized=false`: exact renderer/source provenance, native frame coverage and evaluated original QA must be independently attached before film readiness. No automatic YouTube upload or source cleanup.

## Separate live acceptance proposal

After installation audit and separate authorization, propose a fixed non-secret 3 KiB JSON payload, 1 KiB chunks, <=64 data calls and <=64 token-fetch calls, existing bucket, a unique reviewed namespace and a recorded UTC deadline. No new resources, production frames or deletion. Test one interrupted transfer/resume and an independent GET-only reconstruction; compare full SHA independently. Schedule a separate bounded read-only probe after natural token expiry to prove actual renewal; do not claim the fake refresh tests did that. Check actual Cloudflare usage independently; KRW 50,000/month total and KRW 3,000 R2 are planning allocations, not enforced caps. Full controller activation, live media production and paid GPU work remain outside this implementation.
