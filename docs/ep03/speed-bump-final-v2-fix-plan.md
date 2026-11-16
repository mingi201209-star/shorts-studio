# EP.03 speed bump - final v2 fix plan (no render started)

Source: owner review of 1000020414.mp4 (that file could not be opened here; shot numbers below are mapped to the v5 timeline, 30 fps).
Scope is frozen: only the items below, no new effects. Nothing is rendered until every check in "Gate before full render" passes on a low-cost continuous preview.

## v5 timeline (frames -> seconds)
1-75 low3q approach (0-2.5) | 76-176 rear3q (2.5-5.9) | 177-202 wheel | 203-262 spring (6.8-8.8) | 263-322 front3q | 323-407 profile (10.8-13.6) | 408-486 tyre (13.6-16.2) | 487-576 spring (16.2-19.2) | 577-664 front3q | 665-732 side | 733-782 high3q | 783-860 tyre | 861-930 low3q

## Ten problems merged into six changes
| # | Merged change | Covers (owner list) | What changes | Check |
|---|---|---|---|---|
| A | Impact in the first second | old "weak first 3 s" + new 0-4 s | Shorten the lead-in of segment A so both front wheels meet the bump at ~0.7 s; first shot is the stack at the moment of impact, body pitch/heave visible; approach shot removed (<=0.5 s). Re-time SYNC_EVENTS, keep 31.0 s by lengthening the slow-motion pass. | first_three_seconds gate + new: wheel-bump contact frame <= 1.0 s (from sim) |
| B | X-ray readability against sky | old "dramatic X-ray" + new 5-9 s | Camera pitched down so the ghost body sits against asphalt, not sky; darker body tint, bright rim (fresnel edge) on the body shell, stronger spring/damper/wheel colour. No new effect type. | new gate: edge contrast of body outline vs background in X-ray shots >= threshold, measured on rendered frames |
| C | Each comparison shot shows new information | new 10-18 s repeat + old "repeated scenes" | Replace the three wheel-centred shots (profile, tyre, spring) by: (1) both hub paths in the same axes (LONG vs SHORT, same colour code), (2) rear-side view of body heave/pitch, (3) spring at live length. No two consecutive shots share camera kind. | new check: no two consecutive shots with same camera kind; frame-difference between shot first/last frames above threshold |
| D | Spring compression readable | new 13-18 s | In-world 3D marks (not 2D overlay): thin ghost spring at rest length next to the live one, a rest-height line for the body, a 3D tick at peak compression held for 0.3 s. | new check: spring length measured from rendered orange pixels correlates with simulated deflection (r >= 0.9) on the continuous preview; max-compression frame inside the pass |
| E | LONG / SHORT everywhere | new 19-25 s | Fixed panel order (LONG top/left, SHORT bottom/right) in every shot; 3D label text on the ground beside each bump, plus the caption words; single-vehicle shots show both or are cut. | new check: label pixels present in every shot (preview frame sampling) |
| F | Final proof by replay | new 25-31 s | Last shots replay both bumps side by side under identical conditions with body-height trails and peak markers, held while the conclusion is spoken. | picture_events_match_cues extended to the last cue |

## Three checks that frames cannot settle
1. Tyre vs road: simulation-level check (hub height >= rigid tyre envelope for every frame, no float > 1 mm) plus pixel check on preview frames around contact. Full-resolution frames of contact reviewed before delivery.
2. Real suspension motion: spring deflection must start/peak/recover within 2 frames of hub motion in the sim; same signal correlated against rendered spring length (item D).
3. Voice/caption sync: cue timings and gaps are verifiable by gate; pronunciation/naturalness of the TTS and sync heard by a person stay UNVERIFIED until the owner listens.

Description file stays the home of the assumptions (20 km/h, 7.5 cm, simplified suspension); the video shows the same single speed, so no contradiction.

## Gate before full render
Low-resolution continuous preview (existing preflight, 1/3 res) must pass: all existing QA gates (unchanged), plus the new checks above, plus smoothness (no frozen frames, median frame diff >= 0.5), plus a contact sheet reviewed for every change A-F. A failing part is fixed first. After the full render only failing shards are re-rendered. A regression is reverted to the v5 state (head 7fb7781 / film sha 2ba58ef4…).

## Limits
Cannot be settled by frames or by me: how the TTS sounds, first-view impression, phone readability.
