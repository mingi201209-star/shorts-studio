# EP.05 seatbelt: revision from real retention data (2026-11-19)

Replaces the scene order and narration of `examples/episodes/ep05-belt-load-limiter-plan.md` (draft v1,
branch `fix/ep04-narration-visual-contract-20261117`). Claims, physics gates and reused assets are unchanged.
Nothing is rendered or uploaded until the owner approves the words below.

## Evidence (YouTube Studio, supplied by the owner)

| Short | viewed vs swiped | avg view duration (32 s film) |
|---|---|---|
| Why Are Road Signs Designed to Break? | **69.9% / 30.1%** | 0:26 |
| Why Are Cars Designed to CRUMPLE in a Crash? | 48.0% / 52.0% (first hours only) | 0:19 |
| Channel, last 28 days | 59.3% / 40.7% | – |

Feed is 94.2% of views, so the first second decides distribution.

What the road-sign film did that the crumple film did not:
1. The first frame is the comparison itself: two identical cars side by side, both hit at 0.33 s.
2. Action at real speed continues after the hook; the diagram comes third.
3. The ending returns to the opening camera so the Short loops.

The crumple film opened on one car, spent 2-16 s on a single slow-motion crash, and introduced the
comparison car only at 20.5 s. n = 2 videos, so this is a strong hypothesis, not a proven rule.

## Change for EP.05

Split screen from frame 1 (answers the plan's open question: split screen, not sequential cut).
Left: belt with load limiter. Right: belt with no give. Same car, same crash, same driver.

| id | time | narration | picture |
|---|---|---|---|
| s01 | 0-2.5 s | Same crash. Two seatbelts. Only one is built to give way. | Split screen, both cars already moving, impact on both sides by 0.4 s |
| s02 | 2.5-5.5 s | Both snap tight first, pulling you into the seat. | Both straps glow, both drivers pulled back (real speed, then slow motion) |
| s03 | 5.5-8.5 s | Then this one lets out a little belt. | Left side: webbing pays out, driver keeps moving forward gently |
| s04 | 8.5-14 s | Inside the reel, a metal bar twists on purpose. | Camera flies into the left reel: ratchet locked, torsion bar twisting, spool turning |
| s05 | 14-18 s | So the chest gets a longer, gentler stop. | Back to split screen: left chest green, longer travel |
| s06 | 18-23 s | With no give, the chest stops almost at once, with a harder push. | Right side highlighted: short stop, chest yellow-orange |
| s07 | 23-29 s | Same trick as a crumple zone: a longer stop means a smaller force. | Both front ends crumpled plus both belts, callback to EP.04 |
| s08 | 29-31 s | (no words) | Return to the s01 camera, both cars arriving again: loop |

The pretensioner macro shot from v1 (s02b) is cut: it delays the comparison and the load limiter is the
point of the episode. It can return as its own episode.

## Title / thumbnail
- Title: **Why Is Your Seatbelt Designed to Give Way?** (same "designed to" framing as the best Short)
- Thumbnail: split-screen frame at the moment of maximum difference (green vs orange chest).

## After publishing
Record viewed-vs-swiped and avg view duration at 48 h next to the table above. If viewed is >= 65%,
make split-screen-from-frame-1 the default opening for every episode.

## Result (2026-11-19)
- Built as an edit of the existing frames (run 44463242672, no re-render): frames 0-60 are the top/bottom split, then the calm cabin leads into the snap.
- Final preview run 44473029950: all gates PASS, including the new `split_opening` gate (both halves within 2 ms of the same crash time) and the two fixed gates (`no_scene_text`, `captions_visible` at 24 fps). 586 frames, 24 fps, 24.4 s.
- Still NOT verified: voice pronunciation, sound-off readability, a human first view. The owner uploads.

## First data after upload (owner's Studio, 61 minutes after posting)
| | viewed vs swiped | avg view duration (24.4 s film) |
|---|---|---|
| EP.05 seatbelt, split close-ups from frame 1 | **23.4% / 76.6%** | **0:32** (more than one full play: viewers who stay, rewatch) |

Small first-hour sample; re-check at 24-48 h. Reading: the content holds people, the first frame does not. The hypothesis
"split screen from frame 1" was incomplete: the Road Signs opening worked because a crash between two visible cars is readable
in the first second, not because the screen is split. Two cabin close-ups without the car or the crash are not readable in the feed.
Applied to EP.06: wide shot of both cars and the box, opening 0.6 s into the stop so the locked car hits the box at 0.95 s.
