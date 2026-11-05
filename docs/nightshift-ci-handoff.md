# Event-driven CI handoff (safe first stage)

## What this implements

The `Nightshift CI completion handoff` workflow listens for completion of the existing
`test` workflow through GitHub's `workflow_run` event. It does not poll hourly.
A successful test run writes a log receipt. An unsuccessful run creates one
deduplicated GitHub issue containing its run URL, commit SHA, event and conclusion.
No untrusted pull-request code is checked out or executed in this privileged workflow.

## What this does NOT implement

GitHub cannot directly resume this ordinary ChatGPT conversation using this workflow.
This bridge does **not** launch Codex, call a paid model API, edit source code,
merge a PR, render video, or publish YouTube videos. A supported event receiver
and explicitly authorized AI execution environment would be needed for autonomous
repair between scheduled ChatGPT runs.

## Rollout / validation

1. Review the workflow on a draft PR. It will only become active after an
   authorized merge to the repository default branch.
2. Confirm `test` workflow completion creates a handoff workflow run.
3. Confirm success produces only a log and failure produces one issue.
4. Re-run the same workflow event to verify duplicate prevention.
5. Only after a separate approval and credentials/budget review, connect an
   AI executor; maintain bounded retries and exact-head CI validation.

The existing hourly Nightshift automation remains the code-changing agent
until a verified event receiver/AI executor replaces it. No extra spend is authorized.
