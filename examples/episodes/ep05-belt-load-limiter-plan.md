# EP.05 plan: the seatbelt that gives way on purpose (DRAFT v1, nothing built yet)

Channel "Curious Mechanics": weekly English 9:16 Short, about 30 s, 100% 3D, no on-screen text except the narration captions. The owner posts the video; nothing here uploads anything.
Link to EP.04: the crumple zone made the stop longer. The belt's load limiter does the same for the chest.

## What the film claims (and what it does not)
Claims, kept qualitative and true for modern belts:
1. In a crash many modern belts first pull tight (a pretensioner takes the slack out).
2. As the belt force climbs, a twisting metal bar in the reel (a torsion bar) starts to give, and the reel lets out a little webbing (the load limiter).
3. That gives the chest a longer, gentler stop. A belt with no give stops the chest almost at once with a much higher peak force.
4. Same idea as a crumple zone: a longer stop means a smaller peak force.

Not claimed: no real car's numbers, no injury statistics, no claim that every belt has a pretensioner or limiter. The description says: simplified physics model for explanation, not a real crash test.

## Narration draft v1 (about 74 words, about 30 s; NOT final, no audio is made until the owner approves the words)
1. Your seatbelt is built to give way on purpose.
2. In a crash it first snaps tight,
3. pulling you back into the seat.
4. Then a twisting metal bar in the reel starts to give,
5. letting out a little belt.
6. Your chest gets a longer, gentler stop.
7. A belt with no give stops it almost at once, with a much harder push.
8. Same idea as a crumple zone: a longer stop means a smaller peak force.

## Scene list (frozen before coding; new wishes go to EP.06)
| id | narration | what is on screen | action that must be visible |
|---|---|---|---|
| s01 | 1 | The sedan rolls in on a long run-up toward the wall; cut to the cabin view: belted driver, belt across the chest | car moving, belt visible, 2+ changes in the first 5 s |
| s02 | 2-3 | Impact (reuse the EP.04 crumple car pulse). The belt snaps tight and pulls the driver back into the seat | pretensioner pull-back, driver moves back about 3 cm |
| s03 | 4-5 | See-through cutaway at the seat-side reel: the torsion bar twists and webbing pays out | bar visibly twisting, webbing length growing |
| s04 | 6 | Cabin view, slow motion: the driver moves forward gently, chest colour stays green to yellow | forward travel, colour = chest load (no text) |
| s05 | 7 | Second run, same crash, belt with no give: the driver is stopped almost at once, chest turns red | shorter stop, harder push, red |
| s06 | 8 | Back to the crumpled front and the belt together: both give | crumple front plus belt, callback to EP.04 |

Colour code reused from EP.04: shirt blue, then yellow, then red with the chest load. The rigid-belt run uses the same look as the rigid car in EP.04.

## Definition of done
- Every scene above is on screen at the time of its narration (checked on real frames, with timecodes in the report).
- Gates reused from EP.04: same conditions, energy and claims, no scene text, smoothness (no frozen frames), sync to speech, captions visible, black opening, scene spec and alignment, frozen audio identity.
- New gate `belt_limiter_physics`: with the limiter the peak chest load is lower than without; webbing pays out only above the force threshold; the stroke never shrinks.
- Honest NOT_VERIFIED list stays: voice pronunciation, readability with the sound off, human first view.

## Build plan and what is reused
- Reused: the EP.04 cabin interior set, driver, belt, crash pulse, camera path system, scene-spec and alignment gates, frozen-audio flow, pre-roll run-up, see-through look (neutral, no blue).
- New: a force limiter in `dummy_motion` (belt force capped, webbing pays out), a reel cutaway asset (housing, spool, torsion bar, webbing), scene spec for s01-s06.
- Render: 720x1280 at 12 samples, composed at 1080x1920 (measured: about 30 s per frame including see-through).

## Steps and approvals
1. Owner approves this plan and the narration words (change them now, not later).
2. Storyboard stills: 5-6 range-rendered key frames for the owner to check.
3. Audio capture of the approved words (frozen audio).
4. One full preview with every gate, then the final render.
5. Publish kit: title, description, tags, text-free thumbnails.

## Open questions for the owner
- Narration words OK, or change any line?
- s05: sequential cut (like EP.04) or a split screen of the two belts? Default: sequential cut.
- Show the pretensioner at all (s02), or only the load limiter to keep the film simple? Default: show both, as drafted.
