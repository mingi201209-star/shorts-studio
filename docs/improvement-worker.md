# Persistent Shorts improvement worker (foundation)

Run this under a dedicated server account using `systemd` with `Restart=always`
and a persistent SQLite path. It is currently **not deployed**. The worker
invokes an external adapter every interval, records verified versions, and
stops only when the current candidate hash is explicitly approved. A failed
adapter, missing video, failed QA/CI or detected regression blocks the campaign
until its root cause is fixed and `resume` is called. The service stays alive,
but blocked work is never reported as active improvement.

```bash
python -m shorts_studio.improvement_worker --database /var/lib/shorts-improvement/state.db run --interval 300 --timeout 3600 /opt/shorts-improvement/adapter
python -m shorts_studio.improvement_worker --database /var/lib/shorts-improvement/state.db status
python -m shorts_studio.improvement_worker --database /var/lib/shorts-improvement/state.db approve ACTUAL_VERIFIED_SHA256
```

Adapter stdin: `{ "iteration": 1, "last_good_sha": null, "previous_candidate_sha": null }`.
It must return JSON containing the lowercase SHA256 of the exact review video,
an absolute `video_path` and independently verified booleans `qa_pass=true`,
`ci_pass=true`, `regression=false`. It must itself verify source/main/PR status,
render real media, compare visual and audio quality, poll CI to terminal, and
restore the last good code when quality regresses. The worker does not grant
deployment, publication, purchasing or merge authority. An adapter that falsely
claims verification defeats this boundary; production requires an audited
adapter which checks video hash and CI receipts rather than trusting claims.

The next integration step is to connect the existing Shorts Studio production
and quality reports to that adapter, then deploy and verify `systemd` restart on
the user's existing server. Current SSH key was rejected on the known server,
so the 24-hour service and reboot recovery have not been verified.
