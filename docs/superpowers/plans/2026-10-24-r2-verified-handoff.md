# R2 verified artifact handoff — remote worker implementation (2026-10-24)

**Status: source code and tests only; R2 live connection NOT verified.** The owner has said R2 was activated in Cloudflare. Account ID, bucket existence, scoped API token and OVH deployment have not yet been authenticated from this agent. This PR is stacked on the **inert** PR #61 and does not change production controllers or YouTube.

## Exact scope

- Code: `shorts_studio/r2_verified_transfer.py`
- Contract tests: `tests/test_r2_verified_transfer.py` (injected in-memory S3 fake, no network or charges)
- Optional dependency: `pip install -e '.[r2]'` on an **authorized remote machine**
- Not included: GPU rentals, cloud resource creation, automatic deletion, paid dispatch, automated full-film production, upload publication, source/visual QA relaxation

## Security and data-integrity contract

1. **Dry-run by default.** File must be a regular non-symlink, expected media extension, positive nonzero size and at most the operator's explicit `--max-bytes`, which is itself capped at 128 MiB. Uses constant-memory SHA-256 and returns only content metadata. Zero R2 calls.
2. **No overwrite.** Remote key is derived entirely from SHA-256 and a narrowly validated namespace, under `shorts-studio/<prefix>/<hash>.<suffix>`. Existing object must fully re-download and match SHA-256. If absent, use atomic `IfNoneMatch="*"` on `PutObject` with R2 Standard class. On a concurrent 412, verify the winner's bytes. No bucket auto-create.
3. **Real data read-back.** A `HeadObject`, ETag or stored checksum *alone* never passes; verify every remote byte by streamed `GetObject`, compare exact byte count and SHA-256. Wrong/missing/denied object leaves source file untouched and raises an error.
4. **No automatic local cleanup ever.** `authorized_to_cleanup_local` stays `false` even when remote verified. Cleanup policy belongs to a later explicit stage and must preserve master assets, snapshots and full manifest provenance. No Android video transfer.
5. Only `--apply` enables network write. `R2_ACCOUNT_ID` is a 32-hex account ID, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and `R2_BUCKET` are environment variables loaded **only on the remote host**. Nothing is written to GitHub secret files, terminal log output, Android caches, or PR comments.
6. **No provider cap claim.** Per-file 128 MiB and explicit `--apply` limit each individual call, not monthly billing. R2 requests/storage are usage-billed even under a planning envelope. No automated recurring upload until actual usage metering + budget cap reviewed.
7. This is a bounded **single-object** initial handoff. For larger FFV1 lossless shards use separate tested multipart/resume design, with per-part integrity and cost accounting, before production.

Cloudflare documentation: [official boto3 S3-compatible endpoint](https://developers.cloudflare.com/r2/examples/aws/boto3/), [atomic conditional writes](https://developers.cloudflare.com/r2/api/s3/extensions/), [official billing](https://developers.cloudflare.com/r2/pricing/).

## Activation checklist — after OVH authenticated SSH is unlocked

1. Confirm that `shorts-studio-media` is an existing **R2 Standard** bucket in the owner's Cloudflare dashboard (do **not** create another billable resource simply because the default proposed name was absent).
2. In **R2 → Manage API Tokens**, create a **bucket-scoped Object Read & Write** token. Paste access key + secret **directly into an OVH server-only private environment file**, never chat, GitHub, CI, shared files, or Android render folders. These are R2 S3 keys, not the general Cloudflare API token.
3. On OVH, install Python package from the **exact reviewed source SHA** in a protected checkout / Python virtual environment. First run `python -m shorts_studio.r2_verified_transfer --file /path/to/verified-small-test.json --prefix episode2/sha256 --bucket "$R2_BUCKET" --max-bytes 1048576` **without** `--apply` (zero network).
4. Check real R2 usage, billing and bucket permissions; for **one explicitly approved bounded test**, run the same command with `--apply`, confirm `VERIFIED`, query object content with R2/S3 read-only scope and independently verify SHA. No production files/deletion yet.
5. Only after independent read-back and cost proof, separately integrate controller render receipts, exact renderer/source SHA and manifest, data retention, review artifacts, provider-side limits and 900-frame handoff.

## SSH access blocker (2026-10-24)

The existing OVH VPS `ubuntu@15.235.243.144` host key matches the pinned known_hosts entry and the server **accepts** the user's registered ED25519 public key. The phone's private key file is encrypted (`aes256-ctr`/`bcrypt`); an unattended `BatchMode=yes` login cannot sign without an interactive passphrase unlock. **Do not request or record the passphrase in chat.** Unlock the existing key locally inside the owner's Termux SSH agent, then use SSH agent forwarding/socket access only after inspecting the running agent. No server connection or R2 live upload can be claimed yet.

## Verification checklist

- [x] Red-first GitHub CI genuinely failed on missing `shorts_studio.r2_verified_transfer`.
- [x] Green CI after adding module: test workflow success, 426 pass, 42 skip at `f37d883`; exact-head follow-up checks still required for this docs/dependency commit.
- [ ] Final exact-head CI + Ruff + separate smoke terminal verification.
- [ ] OVH SSH interactive local key unlock.
- [ ] Actual R2 bucket/name/access/token connected (never paste keys into chat).
- [ ] SHA-verified real ~1KiB pilot transfer with actual costs.
- [ ] Full 900 frames; final film; editorial approval (not part of this PR).
