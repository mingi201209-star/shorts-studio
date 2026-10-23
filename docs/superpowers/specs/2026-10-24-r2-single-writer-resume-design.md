# R2 OAuth single-writer resumable transfer design

Date: 2026-10-24 KST
Status: proposed design, awaiting owner approval; no implementation or activation authorized by this document.
Repository: mingi201209-star/shorts-studio; existing Draft PR #65.

## Intent and boundaries

Move verified Shorts media between the existing OVH VPS and existing `shorts-studio-media` R2 bucket without requiring unavailable S3 keys. A single OVH process owns remote writes and credential renewal; interrupted transfers resume from verified content. Success means complete remote bytes can be reconstructed and checked, not merely that PUT returned success.

The owner selected this approach and requested this design. All numeric defaults below are designer proposals. Design approval leads to an implementation plan, not automatic deployment, paid GPU rental, new resources, full 900-frame production, PR merge or YouTube publication. Source files are never automatically deleted. Android is a command/control transport only; media, credentials, staging and receipts remain on OVH. Existing rendering, TTS, caption and visual QA floors remain intact.

## Grounded baseline

- Main: `fcd20fd78851b18c550b1e433bee46ee34313c1d`; reviewed PR65 head: `e0075ea6ae87b1008c792d1991ac2a54e51dbc03`. Repository tree at this head contains no AGENTS.md or CLAUDE.md.
- Latest head has two successful test checks and successful smoke run `40024644471`, attempt 2, job `120662138433`; 486 passed / 1 skipped in the smoke environment. Initial attempt was cancelled after extremely slow Ubuntu mirror downloads; no QA bypass. Ordinary tests: 445 passed / 42 skipped.
- `r2_wrangler_pilot.py` performs a bounded GET-before-PUT and complete GET-after-PUT with SHA-256; it rejects near-expiry OAuth and does not renew it. Its 3-minute minimum lifetime is shorter than three possible 90-second subprocesses. It has no process lock, durable queue, chunking or resume. Its existing-object return also does not recheck the original source.
- `r2_verified_transfer.py` offers atomic S3 conditional creation, but the required S3 credentials are unavailable. Keep this separate backend dormant and unchanged.
- Prior real OAuth acceptance covered tiny JSON objects, not movie-sized transfers. Existing GET/PUT/readback proof does not establish unattended operation, billing caps or concurrent safety.
- The official Wrangler `auth token --json` command documents OAuth refresh when expired, with environment credentials taking precedence. Current installed version is recorded as 4.152.0; the command and its headless behavior on that exact installation remain to be validated.

## Approaches

1. **Selected: one OVH writer, existing OAuth, chunk objects and immutable manifests.** Reuses the observed working path, avoids S3 onboarding and serializes refresh/writes. Its lock protects cooperating processes on this host only; it cannot provide provider-side conditional writes or block dashboard/other-host changes.
2. Bucket-scoped S3 credentials with the existing conditional backend: stronger remote create-only semantics and a future path to multiple writers, but credentials cannot currently be created by the owner. Deferred, not silently required.
3. Multiple OAuth writers with a distributed lock/broker: more components and failure modes while retaining nonconditional Wrangler PUT. Rejected for this stage.

An external writer must not mutate this managed namespace while a job runs. If that operational assumption cannot be established, block apply. Never claim a host lock makes R2 globally immutable. Every consumer rechecks actual content hashes regardless of receipts.

## Components and ownership

- A new opt-in transfer coordinator calls a private Wrangler adapter. The existing pilot remains available as an explicitly manual pilot; it is not quietly upgraded to a production daemon.
- A private OAuth adapter invokes the pinned installed Wrangler and captures secret-bearing output in memory. No custom OAuth endpoint/client ID or hand-written token rotation logic in v1.
- SQLite records jobs, chunk observations, bounded operation reservations and sanitized failure codes. No tokens or secret CLI output in the database.
- A manifest assembler validates exact byte ordering, reconstructs data on OVH and computes the full-file SHA-256 before reporting success.
- No systemd service, scheduler, renderer hook, public port, queue endpoint or other-host client is installed in this stage. The CLI processes one explicit job and exits; durable jobs can be resumed explicitly after restart.

## CLI contract and limits

`plan`, `apply`, `status`, `resume`, and `verify` are distinct coordinator operations. Planning is default/no-network and does not read OAuth secrets. Applying or resuming requires the recorded job identity and an explicit apply flag; no pending job starts just because the program boots. No automatic new production job.

`verify` is an independent read-only restore, not an upload or a requirement to keep the original source available. Inputs are the expected canonical manifest SHA/key, fixed account/bucket/namespace, explicit maximum bytes/GETs/token calls/deadline, and a nonexistent destination within a validated private OVH directory. Default shows a local plan; only `--read-remote` permits bounded GETs and credential acquisition. It never PUTs or creates an upload job and cannot be promoted into write authority. It obtains the same bucket/profile locks, fetches and validates the manifest by the caller-supplied SHA, streams all ordered chunks with bounded readbacks, and verifies total size/SHA. Minimum read budget is N + 1 GETs for N chunks, plus explicit retry headroom. The final destination is installed atomically without replacing an existing path (for example a same-filesystem no-replace rename/link); a conflicting destination blocks. Success is `DOWNLOAD_VERIFIED`, independent of source/spool availability. It does not update the original upload job to REMOTE_VERIFIED without that job's additional original-source checks, and does not attest to film QA. This is the path used for independent-download acceptance.

The caller supplies exact bucket, source path, source SHA expectation if known, namespace, maximum total bytes and maximum remote operations. Refuse missing/invalid limits; do not infer network permission from an estimator. Default proposal: 32 MiB chunks; hard v1 object ceiling 128 MiB, file/job ceiling 2 GiB, maximum 64 chunks per job, manifest ceiling 1 MiB. Larger inputs block; the limits do not represent measured production sizing. No lower render quality to meet them.

Any job also carries an absolute UTC deadline, default proposal 30 minutes; proposed default budget is 320 CLI data operations, with a hard v1 ceiling of 1,024, and two transient retries per operation included in that total. Planning computes the minimum new-upload plus manifest plus independent reconstruction path (4N + 4 data calls for N new chunks) and rejects an insufficient caller-supplied budget; the remainder is retry/reconciliation headroom, not guaranteed completion. Token-fetch subprocesses have a separate hard maximum of 1,024 per job and must have sufficient planned allowance for the reserved data calls. All bounds are checked before reserving an attempt. Reaching a bound leaves a resumable BLOCKED record; automatic retries do not reset counters or deadline. An explicit resume may extend deadline/limits only with recorded new operator-supplied bounds, never by default.

`authorized_to_cleanup_local=false`, `production_concurrent_writes_allowed=false`, `provider_spend_cap_enforced=false`, `upload_authorized=false` remain explicit. Local counters bound calls made by this coordinator; they are neither actual Cloudflare invoices nor a provider spending cap. Existing monthly KRW 50,000 total / KRW 3,000 R2 allocation is planning context only. Actual usage/cost review remains necessary before any separately approved live test or production activation.

## Local files, snapshot and manifest

Use an owner-only OVH state/spool root, separate from renderer outputs and credentials. Reject symlinked roots, symlink sources, unsafe ownership/perms and unsupported input types. Open the source with no-follow semantics, pin its descriptor and record device/inode/size/mtime/ctime. Stream into private chunk files while computing both per-chunk and full-file SHA-256; compare source metadata before/after. Close, flush and fsync completed chunks before sealing the plan. Verify snapshot bytes against their recorded digests before any PUT. This protects against accidental concurrent mutation under a trusted single-user host; it is not protection from a malicious same-UID process.

Do not duplicate the entire file in addition to the chunk spool. Reserve disk for source-preserving spool plus bounded readback space and a proposed 256 MiB free-space floor, based on available disk at staging and before each write/readback. Readbacks are sequential. The adapter must enforce an expected-size-plus-one output-file bound in the child process, e.g. Linux RLIMIT_FSIZE, so a wrong giant existing object cannot exhaust disk. Overrun blocks and preserves source. Persisted spool remains until an explicitly authorized cleanup, including on failure; unknown orphan directories are reported, not deleted.

Each object key is content-addressed under the selected versioned namespace, e.g. `shorts-studio/<namespace>/v1/chunks/<sha>.bin`. `.bin` is an internal chunk format, not permission to broaden the existing public pilot's accepted suffixes. Reuse hashing/validation concepts through the new adapter without changing S3 or pilot contracts accidentally.

The canonical manifest contains schema version, fixed account identity, bucket, namespace, original safe basename/suffix, total size and SHA, exact chunk size/count, ordered entries with index/offset/size/SHA/key, and pinned caller-supplied source/renderer/QA provenance when available. Creation time belongs to a receipt, not the canonical content identity. JSON uses deterministic serialization with bounded fields. Reject duplicate/missing indices, gaps, overlaps, nonpositive lengths, wrong namespace/hash keys, cross-account references, oversized totals and malformed digests. Empty source is rejected, consistent with the pilot.

The manifest itself uses a SHA-derived key and is uploaded last, after all chunks pass fresh remote readback. There is no mutable `latest` pointer. Download it again, verify its hash and reconstruct all chunks in order into a private temporary destination, hashing the entire stream. Only then atomically rename/fsync the verified destination and persist REMOTE_VERIFIED. A manifest being present alone is never acceptance. Final size and SHA must match the sealed source snapshot; a fresh original source fingerprint and full hash must also agree before the original job can report success. Mutation yields SOURCE_CHANGED and preserves both original and remote evidence.

For video use, provenance verification additionally requires the exact approved renderer/source SHAs, native frame coverage and evaluated original QA; storage success alone must never mark a film production-ready. Missing provenance leaves MEDIA_QA_PENDING, even when byte transport is verified.

## Serialization and credentials

One stable Linux flock per canonical account/bucket namespace covers staging seal, reconciliation, GET/PUT/readback and manifest completion for the entire job. Different job namespaces do not bypass this bucket lock. A second process fails fast BUSY and performs no credential fetch or network request. Use a protected fixed lock location, validate file owner/type, never delete/recreate a held lock, never decide liveness from PID text. Kernel release after process death allows restart without breaking a live worker's lock.

A separate fixed OAuth-profile flock covers every invocation that might read/refresh credentials. Acquire bucket lock before credential lock everywhere; the OAuth adapter never obtains the bucket lock. Lock paths are independent of job IDs and config replacement. Any manual Wrangler login/logout/renewal must occur with the coordinator stopped, using the same documented ownership rule. Other hosts are outside this guarantee.

Strip inherited Cloudflare token/key/email overrides and unsafe debug/logging options from the token-fetch child; select the exact expected HOME/config/profile. Run pinned `wrangler auth token --json`, capturing stdout/stderr privately, with a 30-second timeout and a bounded output buffer. Accept only the expected OAuth JSON result, never an ambient API token or key. Do not echo child output, exception payloads, env or argv containing secrets; redact error categories. Inspect pinned Wrangler logging/metrics behavior before real use: secret-bearing output and credential files must not be copied into debug logs, CI or receipts. Do not put the token into command arguments. Only the single data child receives it through its private environment.

Before and after acquisition validate config ownership, regular-file/no-follow identity and owner-only permissions; reject permissive/symlinked files or parents. Preserve unrelated Wrangler config fields; let Wrangler own rotation/storage, rather than implementing an unsafe competing TOML writer. If Wrangler's pinned write behavior cannot preserve private credentials safely, block activation and specify the fix in the implementation plan.

Fetch credentials before each bounded data operation, not once for the whole batch. Require freshly read expiry to cover that operation's 90-second timeout plus 30-second margin. The official command promises refresh on expiry, not necessarily early refresh: if it returns an unexpired but too-short token, enter WAIT_AUTH_WINDOW without a PUT, release the locks after persisting state, and require a later explicit resume once refresh can occur. Do not alter expiry to force rotation or wait indefinitely inside a lock. Failed/invalid refresh, unrecognized JSON, unsupported command, missing refresh token or revoked grant gives AUTH_REQUIRED. No browser opens or interactive login starts automatically.

Feasibility gate before calling this unattended-capable: on an explicitly approved OVH test, the pinned command must obtain a usable token without leaking it and successfully renew after natural expiry, then pass a real read-only authenticated R2 check. Failure leaves the system manual-only; do not silently add a custom OAuth client or request credentials in chat. This design does not authorize that live test.

## Durable state, retries and recovery

SQLite uses schema-versioned jobs keyed by the sealed plan identity, with a unique constraint preventing duplicated active identity, transactional state updates, FULL synchronization and local crash-consistent storage. The bucket lock covers each job run; transactions do not stay open across network calls. Record attempts/reserved operation budget durably before invoking CLI. A crash may conservatively overcount an unissued operation, never undercount a possibly issued one. Job ID or plan hash alone never grants permission to apply.

Job states: PLANNED -> STAGED -> TRANSFERRING -> MANIFEST_VERIFIED -> RECONSTRUCTING -> REMOTE_VERIFIED. Side states: BUSY, WAIT_AUTH_WINDOW, AUTH_REQUIRED, SOURCE_CHANGED, INTEGRITY_FAILED, LIMIT_REACHED and FAILED_RETRYABLE. Side states retain the last safe checkpoint. Corrupt/unknown DB schema blocks rather than recreating success records.

On resume, load the same immutable plan and bounded permissions, validate staged hashes and original identity, then reconcile every claimed completed chunk by fetching and hashing actual remote bytes. Local flags/HEAD/ETag/manifest existence cannot skip verification. Proven missing objects may be uploaded once and then fully read back. Wrong existing bytes block; never overwrite them as repair. Unknown GET errors never imply missing. A source change cannot reuse the previous job's success identity; it requires a newly planned job.

Wrangler human error text is not a stable API. The new adapter must have pinned-version tests and captured non-secret fixtures distinguishing missing key from auth, missing bucket, throttling and generic errors. Unless a missing object is positively classified, block PUT. Do not copy the pilot's substring-only classification into the coordinator. Bound both stdout and stderr retention; truncate safely without retaining secret-bearing diagnostics.

A timeout or crash after PUT leaves outcome unknown. Reconcile by GET before any retry; matching bytes finish verification, wrong bytes block, proven absence permits bounded retry. Manifest PUT follows the same rule. An auth failure during a write is also an uncertain write, not permission to blindly PUT again. Retry only classified transient transport/429/5xx conditions with bounded backoff, remaining deadline and durable budget reservation. No retry on integrity, permissions, schema or source mutation errors. Stop/resume never deletes data or creates another renderer job.

## Acceptance and rollout

Offline implementation must demonstrate: two actual processes contend on the same lock and only one reaches the fake network; lock release after killed process; deterministic manifests and exact gap-free reconstruction; source replacement/mutation rejection including existing-object path; permission and secret-output rejection; refresh failure/rotation/near-expiry behavior; resource and operation/deadline exhaustion; corrupt/missing/oversized remote reads; crashes before PUT, after PUT, after readback and before DB commit; restart without blind overwrite or loss of checkpoints. Existing R2 tests and full engine regression CI must remain green.

Separate live acceptance, if later authorized, uses a named bounded non-secret payload on OVH, limited total bytes/operations and explicit no-cleanup. It must prove natural-expiry OAuth renewal, interrupted/resumed chunks, independent download/reconstruction and matching complete SHA. Record sanitized exact tool/source SHAs, counts, state transitions and actual observations. Fake tests do not establish live renewal or real bills. Do not require rendering new frames to test storage.

No rollout to the existing controller until byte transport and auth gates pass, original video QA is independently attached, and activation is separately authorized. Keep last verified manual pilot intact; remove/disable only the new integration if regression occurs, preserve receipts and source files, then continue from the good path. No weakening checks, overwriting others' changes or resetting main.

## References and decisions left to the builder

- Official authentication command and precedence: https://developers.cloudflare.com/workers/wrangler/commands/general/#auth-token
- Official command announcement (2025-12-18): https://developers.cloudflare.com/changelog/post/2025-12-18-wrangler-auth-token/
- Existing source: `shorts_studio/r2_wrangler_pilot.py`, `r2_verified_transfer.py`, `r2_storage_estimate.py`, and their tests at the reviewed head.
- Builder chooses internal module names, SQLite table details, secure staging primitives and test fixture organization within these contracts. Inspect/pin the installed Wrangler implementation before planning its credential write/log behavior; record any unavailable required capability as a blocker, not an assumed success. Numeric limits and host-local exclusivity are proposed choices for owner review.
