# Verified Nightshift development loop

This feature is a **checkpoint and verification layer** around the **existing**
Shorts Studio pipeline; it is not a new renderer, AI model provider, background
service, GitHub merger or YouTube uploader. The render API, visual QA, TTS and
caption implementation remain unchanged.

## Safety and baseline

1. Inspect main SHA, open PRs, existing CI and the last verified video before
   starting. Use a clean, isolated working branch. Never write directly to main.
2. Keep one checkpoint per immutable commit SHA; the runner rejects HEAD drift.
3. Preserve the known-good commit and video externally. Do **not** auto-reset
   Git, merge a PR or declare a new video good after automated tests alone.
4. Never relax `SHORTS_REQUIRE_SEMANTIC_QA=1`, or omit the existing caption,
   structural, final-video, media-integrity or human audio/visual review gates.
5. Run the CLI only in a trusted working copy. Checkpoints stay under the ignored
   `.nightshift/` directory and contain no secrets.

## Reproducible gated run

```bash
python -m shorts_studio.nightshift init --goal "verify current Shorts Studio change"
python -m shorts_studio.nightshift status
python -m shorts_studio.nightshift run-tests
python -m shorts_studio.nightshift run-render --project examples/comet.json
python -m shorts_studio.nightshift status
```

- `run-tests`: actually runs the complete `pytest -q` suite. No mocked PASS.
- `run-render`: requires successful tests on the **exact** current SHA, runs
  the existing renderer with production semantic QA required, then checks that
  **new** `dist/final.mp4` and `dist/qa_report.json` exist.
- The evidence gate validates semantic scene PASS, structural QA, every
  final-video check, subtitles, captions, H.264/AAC, 1080×1920, >=30 fps and
  plausible duration using `ffprobe`.
- Passing automated checks leads only to `awaiting_human_video_review`.
  Listen for robotic prosody, chopped pauses or pronunciation errors; check
  first-five-second visual changes, actual moving 3D evidence, camera continuity,
  caption safe area, and compare directly with the previously accepted video.
- To log a real human comparison:
  ```bash
  python -m shorts_studio.nightshift review --result fail --notes "The voice sounds robotic"
  ```
  **Never mark pass without performing the comparison.** A human review is not
  replaced by the binary QA report.

## Crash recovery and limits

The checkpoint uses atomic file replacement and an exclusive OS lock.
If the process or device is killed, the OS releases the lock; after relaunch,
the prior `RUNNING` stage is recorded as `INTERRUPTED`. At most two attempts
per stage and SHA are allowed. On repeated failure, diagnose the root cause and
make a minimal change **on a new SHA**; repeat all gates. No unattended infinite
retry, destructive cleanup or ambiguous fallback-to-PASS is permitted.

The runner itself does **not** stay alive if Android forcibly terminates it,
does **not** switch or pay for AI models, and does **not** watch GitHub indefinitely.
To use it as an always-on job, an already authorized Termux/cloud supervisor must
reinvoke the CLI after a restart. The GitHub Actions `test` and `render-smoke`
workflows independently test/render this PR; the new layer does not replace them.

## Separation of responsibilities

- **Supervisor:** checkpoint, SHA/permission boundary, bounded execution.
- **Coding agent:** investigate actual failure, reproduce, minimal patch.
- **Independent QA/CI:** complete regression and semantic render gates.
- **Human owner:** assess visual/audio quality against previously accepted
  baseline and explicitly decide whether to merge or upload.
- **Credential handling:** secrets stay in the existing credential store, never
  in the checkpoint or command log. Do not give an agent publishing privileges.

## Effectiveness

Track completed video renders, manually accepted usable videos, regressions,
repair iterations and evidence per attempt. PR count and lines changed are not
success metrics. Model selection changes require a separately verified trial
and may never silently weaken the gates.
