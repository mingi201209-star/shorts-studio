# Curious Mechanics — X-ray / Cutaway episode plan (2026-11-15)

Status: APPROVED CREATIVE DIRECTION; implementation and upload NOT approved.

## Decisions
- EP.03 speed bumps: apply X-ray / transparent body / suspension cutaway to show wheel, spring, damper, chassis response when crossing short versus long ramps.
- EP.04 (next episode after speed bumps): also apply the same explanatory X-ray/cutaway storytelling pattern, choosing the precise mechanism only after topic and physical accuracy review.
- Preserve narration-to-visual correspondence: when a mechanism is mentioned, expose and animate that exact mechanism. No arbitrary transparency, repeated crop/zoom, or empty motion.
- Use exterior danger/curiosity hook (0-3 s), transition into internal mechanism, side-by-side identical vehicle/speed/suspension comparison, then return to exterior conclusion.
- First 3 seconds must be understandable with sound off. Distinguish bump shapes clearly and show actual suspension response; not merely a camera move.
- Rendered captions must sit higher and clear YouTube Shorts UI safe area, reflecting real viewer feedback.
- Produce two thumbnail concepts plus a selectable in-video Shorts cover frame. Do not imply Shorts supports unrestricted image-thumbnail uploads.
- Treat physics values as assumptions unless independently validated; avoid fabricated shock-force/comfort/safe-speed claims.

## Engineering acceptance gates
1. Before implementation check latest main SHA, open PRs and CI; keep existing interfaces and features.
2. Prototype X-ray effect as an opt-in module; default existing renderer behavior remains unchanged.
3. Low-resolution motion preview and actual contiguous playback reviewed by a human, not only stills.
4. Verify vehicle silhouette, mechanism visibility, wheel-ground contact, physical plausibility, subtitles, audio/narration sync, and first-3-second semantic change.
5. Compare against prior known-good version; if measurable visual/functional regression occurs, revert the offending change and continue.
6. Run existing tests and CI without weakening thresholds; no PASS without evidence.
7. Free GitHub Actions rendering only; VPS management/storage, not rendering. No paid resources without permission.
8. No automatic YouTube upload, main merge, PR creation, or full render implied by this planning document. Explicit approval required for publishing.

## Ownership
Planning: storyboard and claims; Rendering: reusable transparent-body/cutaway assets; Editing: reveal timing/captions; Evaluation: visual comprehension and physics QA; Management: branch/CI/cost tracking.

## Success measurement
Compare EP.03 and EP.04 against road-sign and truck videos on viewed-vs-swiped, average view duration, and subscribers per 1,000 views. A visual effect alone does not prove subscriber growth.
