# R2 remote OAuth pilot: live validation, 2026-10-24

**Status: Verified live on owner's existing OVH VPS. Not production, not unattended.** User said R2 S3 API credentials could not be created; the owner approved the Wrangler device-login in their own browser. No R2 secrets entered in chat. No new host, GPU lease, paid controller, GitHub merge or YouTube upload.

## Live verified components

- VPS SSH: `ubuntu@15.235.243.144`; passphrase-protected Termux SSH identity was unlocked locally and used via an existing private ssh-agent; no password or private key exposed.
- Existing `shorts-studio-media` bucket was listed using `wrangler 4.152.0` via an OAuth token obtained after `wrangler login --device --browser=false`. Token file `~/.config/.wrangler/config/default.toml` stays on OVH (`0600` mode). Cloudflare GET `/client/v4/user` returned HTTP 200; no OAuth value logged.
- **Wrangler headless quirk:** `wrangler whoami` returned "not authenticated" and `r2 bucket list` rejected noninteractive use *even with a valid OAuth cache*. The workaround reads the **unexpired** access token locally and supplies it to **that one Wrangler child process** as `CLOUDFLARE_API_TOKEN`. Do not confuse this short-lived OAuth access token with an R2 S3 key; it does NOT authorize the boto3 S3 backend.
- First real one-off test: remote `PutObject` using Wrangler uploaded **138 bytes**, `GetObject` downloaded the actual bytes, matching SHA-256 `e06a7fa12f8d93e435ed096ead7c575662587b999bb8db79dc3ca715c47e5752`. Immutable test key `shorts-studio/connectivity/sha256/<hash>.json` remains in bucket for audit.
- New `shorts_studio/r2_wrangler_pilot.py` has an explicit `--apply` gate; no network on default dry-run; currently capped to at most **128 MiB per object** by shared `plan_upload`; performs real remote GET before PUT, full post-PUT GET and byte-length/SHA-256 matching; idempotent existing content recognized as `VERIFIED_EXISTING`, wrong existing bytes and unknown API error block; never deletes the source; rejects Android video handling; refuses token file with unsafe permissions and expiring access tokens. **No truly atomic PUT-if-absent support with Wrangler:** never schedule concurrent/production uploads through this module. Existing `r2_verified_transfer.py` provides a separate, atomic S3 implementation, but S3 keys were not provided.
- This CLI was checked out by exact SHA `32978eecfc0c07b7cd899aa0968fe969e1f28e89` on OVH in isolated detached worktree `~/shorts-controller-worktrees/r2-handoff-20261024`, leaving clean production `~/shorts-studio` main `fcd20fd78851b18c550b1e433bee46ee34313c1d` untouched.
- **Verified second real remote test via new CLI:** `DRY_RUN` then `VERIFIED` then `VERIFIED_EXISTING` for the same 113-byte JSON object at `shorts-studio/episode2/sha256/9622a6f865f4b99b1e6ccddd02580cabb284efcbdc765f6d0cee263cd36f3a15.json`. Remote full checksum equal in both successful paths. Source was preserved and disposable OVH temporary copies cleaned. No data was rendered/transferred onto Android.
- TDD: initial new tests failed on missing module (run `40024050652`); new-module test run `40024208541` succeeded: **445 passed, 42 skipped**. Exact-head CI and render smoke must be rechecked after this documentation commit.

## Running one owner's separately approved pilot

From the **existing OVH server** and pinned checkout, with an **unexpired** device-login token in the local protected credential file, replace `/absolute/path/to/approved/test.json` with a reviewed non-secret pilot. The default command makes **no network request**:

```bash
cd "$HOME/shorts-controller-worktrees/r2-handoff-20261024"
PYTHONPATH="$PWD" python3 -m shorts_studio.r2_wrangler_pilot \
  --file /absolute/path/to/approved/test.json \
  --prefix episode2/sha256 \
  --bucket shorts-studio-media \
  --max-bytes 1048576 \
  --wrangler "$HOME/shorts-controller-worktrees/r2-wrangler-tool/node_modules/.bin/wrangler"
```

Only the separately intended **one-object remote operation** uses the same command with `--apply`. If the token is expired, the command blocks; refresh the login interactively on the VPS through the owner's phone. Never paste tokens into chat, source control, logs or GitHub secrets.

## Scope boundaries / next gates

1. Actual charges are not retrieved from Cloudflare. 2 tiny R2 objects remain; no meaningful R2 bill can be extrapolated from them. Continue checking actual provider usage and the KRW 50,000/month total plan, with R2 planning share KRW 3,000. Neither budget estimator enforces provider spending caps.
2. Wrangler OAuth uses broader default scopes and short-lived bearer tokens. For unattended headless production jobs, obtain a narrowly scoped S3 credential *if permitted* or design + audit another secure refresh/access mechanism before any automation. Never claim automatic or unlimited R2 uptime from this test.
3. Do not weaken 1080x1920 Cycles32 900-original-frame/English TTS/caption/visual QA requirements or treat a 113-byte handshake file as a movie.
4. Before full 30-second film: design safe concurrent immutable upload backend, multipart/resume or per-shard checksums, manifest receipt verification, budget/quotas, lossless-retention policy and final human review. Keep the existing OVH worktree separate; no PR auto-merge.
