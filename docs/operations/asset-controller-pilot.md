# Local mock controller pilot

This is Milestone A local persistence evidence only. **Do not install or enable**
the service during this plan. Installation, activation and a finite 24-hour burn-in
require separate owner approval. No service has been deployed by these instructions.
Use the existing VPS only (2 vCore / 4 GiB / 40 GiB, Ubuntu 24.04); do not purchase
another server, storage account, GPU or paid model API. There is no external job,
Codex dispatch, renderer, B2 transfer or upload in this CLI.

## Manual rehearsal

Use an approved isolated worktree and virtual environment, a private local directory
and a single operator. Keep production and Factory branches unchanged. Record the
worktree SHA with `git rev-parse HEAD`. Full exact-SHA product CI is required before
claiming compatibility; local tests alone do not establish remote CI or VPS results.
Run from the repository root; replace the example source SHA with the audited SHA.
These commands use only mock proof bytes, never frames or production QA PASS.

```sh
umask 077
mkdir -p /tmp/asset-controller-pilot
python -m shorts_studio.asset_factory.controller --help
python -m shorts_studio.asset_factory.controller init --db /tmp/asset-controller-pilot/controller.db
python -m shorts_studio.asset_factory.controller enqueue-mock --db /tmp/asset-controller-pilot/controller.db --id pilot-1 --source-sha aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --input-digest bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
python -m shorts_studio.asset_factory.controller step --db /tmp/asset-controller-pilot/controller.db --storage /tmp/asset-controller-pilot/objects --mock-only
python -m shorts_studio.asset_factory.controller status --db /tmp/asset-controller-pilot/controller.db --json
python -m shorts_studio.asset_factory.controller serve --db /tmp/asset-controller-pilot/controller.db --storage /tmp/asset-controller-pilot/objects --mock-only --poll-seconds 60 --max-ticks 2
```

`init` alone may create a database. Other commands require an existing valid v1
database, except `recover`, which may create an offline destination. Invalid schema,
invalid digest, identity conflict or inaccessible paths return a nonzero exit code
without a traceback or echoed exception text. Repeating an identical enqueue is a
no-op; changed identity is refused. `step` performs at most one mock claim. `serve`
uses the same admission gates each tick; omit `--max-ticks` only for an approved
supervised run. SIGTERM/SIGINT finishes the current bounded mock tick, interrupts
polling, and closes SQLite. Run only one manager per state directory.

Status reports queued, blocked, completed_mock and receipt counts, last event number
and time, and schema version. Free-form event details, IDs and payloads are omitted.
A mock receipt proves local hash/ownership only. Preserve the production contract:
1080×1920, 30 fps, Cycles32, unique native frames, English narration and all video,
audio and caption quality gates. No interpolation or filler substitutes.

## Checkpoint and offline recovery

1. Stop the manual loop with SIGTERM or Ctrl-C; ensure every process using the
   destination database is stopped. If a separately approved service exists, use
   `sudo systemctl stop shorts-asset-controller.service` and verify it is inactive.
2. Create a uniquely named snapshot using SQLite backup (safe with committed WAL
   data); never copy a live database file with `cp`.

   ```sh
   python -m shorts_studio.asset_factory.controller snapshot --db /tmp/asset-controller-pilot/controller.db --dest /tmp/asset-controller-pilot/checkpoint-1.db
   sha256sum /tmp/asset-controller-pilot/checkpoint-1.db
   cat /tmp/asset-controller-pilot/checkpoint-1.db.sha256
   ```

3. Record the printed SHA256 independently. Retain the last verified snapshot and
   local object directory: the database snapshot does not include artifact bytes.
   The sidecar alone is not an independent trusted checksum. Off-host encrypted
   backups remain an unmet requirement until separately approved and tested.
4. Rehearse restore into a new offline path using the independently recorded digest:

   ```sh
   python -m shorts_studio.asset_factory.controller recover --source /tmp/asset-controller-pilot/checkpoint-1.db --expected-sha256 REPLACE_WITH_VERIFIED_64_HEX_DIGEST --db /tmp/asset-controller-pilot/restored.db
   python -m shorts_studio.asset_factory.controller status --db /tmp/asset-controller-pilot/restored.db --json
   ```

5. Compare counts and receipts against the recorded checkpoint and verify retained
   artifact hashes/ownership using the existing local store interface before relying
   on them. Never count a missing blob as durable success. To roll back, stop all
   readers/writers and restore the verified snapshot to the original `--db` path.
   Check checksum, schema and status before resuming mock work.

Recovery verifies checksum and schema before replacement and refuses live/locked
or uncheckpointed destinations. On rejection, preserve the original database and
inspect the cause offline. Do not delete WAL/SHM files to force recovery. Prevent
concurrent opens throughout restore. Managed controller connections hold a
shared advisory maintenance lock and restore holds its exclusive counterpart.
Linux psmisc fuser is required for the additional same-owner open-handle
check; if unavailable, restore refuses to proceed. An administrator must
still stop every unmanaged or privileged database client before offline
recovery. Retain earlier known-good snapshots and source masters.

## Incident handling and approval boundaries

At less than 10% free space, dispatch defers without consuming an attempt. Stop the
loop, inspect disk usage, retain verified data and add no paid capacity automatically.
For corrupt artifacts, SHA drift or failed writes, preserve evidence and the last
good copy; quarantine affected jobs and investigate before resuming. Do not reset
blocked jobs with SQL to force retries. Unknown expired external status must stay
blocked; the CLI does not reconcile or redispatch ambiguous leases. Evidence-based
reconciliation uses the existing recovery API with independently established worker
status. Quota/auth failures never authorize API fallback or duplicate work.

Keep SSH public-key-only, UFW and AppArmor/Bubblewrap enforced. Store no private
keys, login caches, passwords, tokens, OTPs, public host addresses or account IDs in
repo files, payloads or logs. Status deliberately omits arbitrary text; review all
other diagnostic evidence before sharing it. Rotate compromised credentials through
the separately approved operator process. No sandbox bypass, automatic merge,
workflow dispatch, production Codex worker, YouTube upload or external spend is
permitted. Factory integration and renderer/storage rollout require separate plans.

## Inert service template: future approved installation only

`deploy/systemd/shorts-asset-controller.service` has no install target and requires
an explicit approval marker at `/etc/shorts-asset-controller/approved-mock-service`.
It runs only mock-only serve, with no network, conservative CPU/memory/process limits,
private state and restart on failure. The marker is an additional guard, not approval.
Do not create it as part of this implementation.

After separate owner approval, an operator must review the exact source SHA and unit,
create a dedicated `shorts-asset-controller` system account with shell
`/usr/sbin/nologin` and no login home or persistent Codex auth, deploy the reviewed
worktree/environment under `/opt/shorts-studio`, and create private service-owned
state under `/var/lib/shorts-asset-controller`. Initialize its database as that user.
Review journal retention and available disk space. Install the reviewed template
under `/etc/systemd/system/shorts-asset-controller.service`, then run
`sudo systemctl daemon-reload`. Only under that separate approval, create the marker
and start explicitly with `sudo systemctl start shorts-asset-controller.service`.
The template intentionally provides no enable target; boot activation requires a
separate reviewed unit change. Inspect `systemctl status` and bounded journal output,
verify mock receipts, then stop at the approved soak deadline.

Disable/rollback an approved installation with `sudo systemctl disable --now
shorts-asset-controller.service`, remove the approval marker, verify no manager
process remains, preserve state and snapshots, and remove the installed unit if
rolling back deployment. Run `sudo systemctl daemon-reload` after removal. Restore
the prior reviewed code/environment and verified offline database as needed. Do not
delete the state directory or last verified artifacts during rollback.
