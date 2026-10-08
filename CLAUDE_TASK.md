# Local Claude Code task — PR #41 quality reset

Read and obey `CLAUDE.md` first.

## Repository state
- Repo: mingi201209-star/shorts-studio
- Work branch: exp/quality-reset-v1
- PR: #41
- Do not merge.
- Do not upload to YouTube.

## Goal
Take full ownership of the quality-reset workstream and continue until the Short is materially more upload-worthy by human judgment, not merely automated QA.

## Current known failure
The latest quality-reset workflow completes the full regression (499 passed, 1 skipped), downloads both licensed real-footage assets successfully, then fails in:
`scripts/build_hydroplaning_states.py`
with:
`RuntimeError: Prompt V2 produced no hydroplaning hook`

Do not weaken the hook judge or any existing QA gate to make it pass.

## Mandatory product bar
- First 0–2.5s must not be dominated by low-budget custom CG.
- Opening should use strong real/high-end-looking wet-road/tire visuals.
- If current 3D still looks cheap in the real render, materially improve it or demote/remove it.
- No fake cadence from crop/zoom-only changes.
- Narration should sound like one human narrator.
- Edge TTS is a dev/fallback baseline, not the final quality target.
- Do not use decorative breath noise to hide robotic delivery.
- Keep captions, safe area, timing, semantic alignment, and render integrity at least as strict as current gates.

## Source reuse policy
Before writing new implementation code:
1. Prefer official vendor implementations/examples.
2. Then maintained human-authored OSS with tests/CI.
3. Then widely used reference implementations/libraries.
4. Only write custom code where no suitable maintained implementation exists.

Verify license compatibility before copying/adapting. Prefer permissive licenses. Preserve notices where required. Do not use unlicensed, leaked, proprietary, or unclear-license code.

Especially prefer proven code for:
- TTS/provider adapters
- FFmpeg/media handling
- subtitle/word timing
- download/retry
- CI helpers
- video primitives

## Execution
Do not stop at planning.
1. Inspect branch, relevant code, existing tests, and git history.
2. Reproduce/diagnose the Prompt V2 hook failure.
3. Fix it without weakening standards.
4. Improve the real-footage-first visual path and narration quality.
5. If practical, add a clean high-quality TTS provider abstraction and an external pre-rendered narration override path; never commit secrets.
6. Add tests for new behavior.
7. Run targeted tests.
8. Run full regression.
9. Run the real quality-reset build/render locally where practical.
10. Inspect actual frames and audio, not only metrics.
11. Revert any change that regresses product quality/reliability and try another approach.
12. Commit coherent changes to exp/quality-reset-v1.
13. Push the branch.
14. Inspect GitHub CI after pushing and fix failures if possible.

Only report ready if the actual output no longer has an obvious first-second swipe trigger. Otherwise keep improving or report the concrete external blocker.
