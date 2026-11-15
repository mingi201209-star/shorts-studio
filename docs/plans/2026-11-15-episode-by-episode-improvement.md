# Curious Mechanics — episode-over-episode improvement policy

Decision (2026-11-15): Every new episode should be demonstrably better crafted than its predecessor, while preserving strengths and avoiding regressions. Audience metrics are observations, not guaranteed monotonically increasing targets.

## Production gates
1. Before work, check latest main, open PRs, and CI; keep the working baseline immutable.
2. Planning records one or more weaknesses in the prior episode and a specific improvement hypothesis for the next episode.
3. Render/edit show a side-by-side A/B or equivalent evidence of the improvement (first 3s, mechanism visibility, shot progression, subtitles, sound, accuracy).
4. Evaluate actual contiguous playback, narration-screen correspondence, safe-area, and physics; do not weaken QA thresholds.
5. If a real quality or functional regression is detected, revert the offending change to the prior known-good state and continue safely.
6. Following publication, compare viewed-vs-swiped, average view duration, and subscribers per 1,000 views at comparable 24h/48h windows. Separate sampling noise, distribution, and topic effects from craft quality.
7. Store an episode scorecard: previous weakness, implemented change, verification evidence, remaining issues, and post-publication outcome.
8. Do not upload automatically; publishing requires explicit user approval. No main merge, PR creation, paid rendering, or VPS rendering without authorization. Continue CI verification through the supported workflow; do not claim unattended live monitoring unless actually scheduled.

## Immediate episodes
- EP.03 speed bumps: opt-in X-ray/cutaway of suspension and wheel response, more legible first 3s, higher safe captions, two thumbnail concepts.
- EP.04 next: reuse proven internal-reveal storytelling and address EP.03's measured weakest point rather than blindly adding visual effects.

## Core principle
Improve at least one verified production-quality dimension per episode, preserve what works, and use real audience feedback to guide the next iteration. Never fabricate PASS or subscriber growth claims.
