# Rumble-strip episode — action-first editorial revision (2026-11-07)

Status: DESIGN ONLY / HOLD. No render or upload authorized by this document.

## Reference lesson
The user-supplied suitcase-evolution short communicates a new *action* at each cut. Transfer the action-to-consequence storytelling, not its characters, subject, artwork, or footage.

## Causal spine (30 seconds / 900 unique authored frames)
| Frames | Beat | Visible physical action | Required evidence |
|---|---|---|---|
| 1–150 | hook_warning | Car drifts toward shoulder; near-side tyre approaches the first recessed groove | tyre and actual shoulder milling share the shot; no opening black frame |
| 151–300 | road_cut | Camera exposes real milled asphalt cross-section while tyre advances | geometry below road grade is visible; not painted stripes |
| 301–450 | tire_contact | Tyre rolls into and out of successive grooves | contact point and wheel movement both visible, not a static wheel close-up |
| 451–600 | rumble_mechanism | Wheel oscillation propagates through suspension into car body | wheel-to-body cause/effect visible in one continuous shot; no generic camera shake |
| 601–750 | shoulder_location | Wider road context reveals grooved band on shoulder only | lane remains smooth; car placement understandable |
| 751–900 | driver_response | Driver notices vibration, visibly reacts, and steers back toward lane | *actual driver action* visible; do not claim achieved by camera movement alone |

## Critical implementation gap
The current renderer animates a car and its wheels; a visible human driver reaction is NOT proven. Do not approve the final beat until a credible in-car driver, steering response and return trajectory are rendered. A text claim or an exterior-only car shot does not satisfy this gate.

## Editing requirements
- Every cut changes the viewer's understanding; don't repeat similar wheel close-ups.
- Establish space before close-ups and re-establish road context before the response.
- Keep English narration synchronized with *visible* actions; no unsupported explanations.
- Show vibration through wheel, suspension, and body transforms, not repeated crop/zoom.
- Preserve the existing 1080x1920, 30 fps, 900-frame target and all production quality thresholds.
- No generated holds, duplicate frames, synthetic upscale, or skipped visual QA.
- Do not run a full 900-frame render until sparse real-scene previews of frames 1, 90, 180, 330, 480, 570, 660, 780, 840, 900 are manually checked.
- Fail closed on any missing driver, missing actual groove contact, clipping, caption safe-area violation, or narration/scene mismatch.

## Acceptance protocol
1. Verify source-scene SHA and all six beats on existing manifest.
2. Produce sparse real-scene preview with the hash-pinned CC0 sedan (not generic cubes).
3. Review the actual rendered frames and action transitions.
4. Only after previews pass, dispatch the 30 production shards and verify 900 unique frame hashes.
5. Encode MP4; check 30 fps, 1080x1920, audio/captions, final semantic and visual QA.
6. Human approval required before upload. No automatic merge, upload, paid runner or VPS render.
