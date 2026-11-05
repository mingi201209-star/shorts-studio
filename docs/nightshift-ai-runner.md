# Guarded AI repair runner — intentionally not autonomous

The workflow `Nightshift guarded AI repair (opt-in)` provides a separate,
read-only Codex diagnosis path. It is **disabled by default** unless repository
variable `NIGHTSHIFT_AI_ENABLED=true` is explicitly configured. It also
requires the repository secret `OPENAI_API_KEY`, which may incur API charges.
Neither the variable nor secret is created by this PR.

This is deliberately separate from the CI completion workflow. A GitHub
`workflow_run` on a public pull request has elevated permissions; never
execute its submitted code or pass secrets into it. This read-only runner
checks out the default branch only and treats issue contents as untrusted.

## Remaining steps for real autonomous repair

- Obtain approval for AI provider, credential handling and an explicit spend cap.
- Implement an isolated branch writer with a hard attempt limit, no main merge,
  PR-only output, rollback to last-good and exact-head CI terminal verification.
- Restrict execution to trusted issues and prevent AI-generated PRs from
  recursively triggering themselves.
- Verify one real failure-to-PR cycle and stop conditions before enabling.
- Confirm any integration capable of waking a ChatGPT task; none is wired here.

No automatic paid AI call or ChatGPT wake-up is active.
