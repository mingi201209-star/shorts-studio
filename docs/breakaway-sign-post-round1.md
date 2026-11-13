# Breakaway sign post episode (topic 4 of the road-safety lane)

Branch `road-paint-retroreflective-20261106`. No PR, nothing merged to `main`, nothing uploaded (`upload_authorized: false`).

## Result

| item | value |
|---|---|
| video | `breakaway-sign-post.mp4`, 1080x1920, h264 + aac, 32.000 s |
| sha256 | `f6312d35b9d3c853cf485781d0d43ec4e0928366c732ed373a5729684e8d85c9` (matches `SIGN_FILM_PASS`) |
| preflight (low-res, full length) | run 43382142649 PASS (five earlier preflights failed and were fixed, see below) |
| render + assembly | production run 43383407475 (32 shards x 30 frames, 32 samples, free standard runner), first attempt, all gates PASS |

Frames at 17 timestamps from the real 1080x1920 video: `docs/evidence/breakaway-sign-frames.jpg`.

## What the film shows and what backs each claim

Two identical 1,500 kg cars at 90 km/h hit two identical-looking sign posts at the same instant: a fixed post (blue car) and a slip-base post (red car).

1. "Only one of them stops": fixed-post lane stops in 0.79 m (assumed deceleration distance 0.8 m, 40 g average); the breakaway car keeps 98% of its speed (speed change 0.49 m/s).
2. "Base slips apart": the upper plate slides off the lower plate and three bolts are thrown clear (extreme slow motion, 0.008x).
3. "Plates held by bolts in open notches that resist the wind but not a car": exploded view (diagram device). Design-gust base shear on the sign 933 N against an assumed 8,000 N slip force against a 48,600 N mean impact force.
4. "Spins up and over the roof, lands behind the car": plastic impulse at bumper height on a rigid post (momentum and angular momentum conserved, residual 0), free flight, smallest clearance over the hood and roof 0.23 m, lands 3.8 m past the post while the car's tail is already 9.2 m past it. Translucent post copies every 0.06 s mark the arc (diagram device).
5. "Fixed post took all of the car's speed in under a meter, breakaway almost none": both read-outs from the simulation.
6. Closing: roadside signs; the last two seconds return to the opening camera with both cars arriving again, ending one frame before frame 1 (first-vs-last frame mean difference 0.65 on a 0-255 scale), so the Short loops.

## Gates on the real video

Original QA PASS (visual_activity longest hold 3.5 s, black_opening, captions_visible, plus silence/loudness inside the film QA; integrated -16.4 LUFS, true peak -1.6 dBFS with the effects), motion_plausibility PASS, narration_screen_match PASS (6 of 6), first_three_seconds PASS (post released at 0.33 s, fixed car stopped at 0.87 s), caption_safety PASS.

## Improvements carried over from the sand-barrel review (this episode's design choices)

- Opening is the comparison itself: two cars side by side, not a single car.
- Edit order from the retention graph supplied for an earlier Short: action continues after the hook, the diagram comes third, the ending loops. **Unverified whether that pattern transfers**; it can only be checked with this video's own retention graph after upload.
- Test conditions on screen (`SIMULATION | 1,500 kg CARS | 90 km/h HEAD-ON`), live speed read-outs for both lanes.
- Quiet synthetic impact and clank effects mixed under the narration, placed at telemetry event onsets (6 marks); the voice-only file is kept beside the mix. The effects are synthesized noise and a sine tone, not recordings.
- Captions cut at phrases, each cue within one 24-character line.

## Limits (not hidden)

- Not a validated crash simulation. Rigid cars, no deformation drawn, post and panel masses, slip force, base impulse and the fixed-post crush distance are assumptions; `physically_calibrated` stays False.
- The breakaway speed-change limits used in the gate (5 m/s limit, 3 m/s preferred) are recalled from roadside-hardware test criteria and were **not** re-read from a source in this session.
- No comparison with a full-scale test trace.
- Speed read-outs and the stroboscopic marks are diagram devices; the read-outs count as "visible" whenever shown (true by construction).
- The effects have no recorded basis; they are a plausibility aid.

## Process record

Five preflights before the PASS: (1) audio server returned no audio for one sentence (re-run); (2) total silence 5.94 s from comma pauses (narration reworded); (3) two sentences spoke 17-21% over the neighbouring shot (boundaries moved to the measured sentence windows); (4) a 5.5 s static hold in the side view (a third camera setup added, checked locally with the QA's own rule); (5) PASS. A worker restart cut one command mid-way; the push had completed and the watcher scripts were rebuilt. Production gates are closed again.

## Next

- Human review; upload decision (not done).
- If this episode's retention graph is shared after upload, compare it with the earlier Short's.

---

# Round 2 (after the owner's comparison of the two Shorts)

Owner review (supplied in chat; the owner's scores are subjective and not a retention prediction): sand-barrel 84/100, breakaway sign 78/100. The sand-barrel Short is reported by the owner to have **62.8% stayed to watch, 1,332 views, 18 likes** (numbers not visible to this session, recorded as supplied). Points raised for the sign Short: the start screen carried too much (two cars, two signs, speed read-outs together); the comparison needed explaining after the collision; the fixed-post result and the speed read-outs needed a stated basis. Recommendation followed: strengthen the first 3 seconds rather than remake everything; keep the caption safe area unchanged.

| item | v1 | v2 (this cut) |
|---|---|---|
| sha256 | `f6312d35b9d3c853cf485781d0d43ec4e0928366c732ed373a5729684e8d85c9` | `d9ed541f037963bc7af7d52bd52b680fa331ae494ca699408fb713cb4f8ec387` (matches `SIGN_FILM_PASS`) |
| preflight | run 43382142649 | run 43427562214 PASS |
| render | run 43383407475 | production run 43429090955 (first attempt, all gates PASS) |

Frames of v2 at 20 timestamps: `docs/evidence/breakaway-sign-v2-frames.jpg`.

## What changed

- **First 3 seconds:** hook narrated as the question "Why are some road signs designed to break the moment a car hits them?"; for the first 1.5 s only the two cars and two signs are on screen (no read-outs); the collision and the two outcomes happen inside that time (post released at 0.33 s, fixed car stopped at 0.87 s); the read-outs appear at 1.5 s.
- **Order:** the plain-language comparison is now shot 2 (right after the hook), the base-release shot 3, post-over-roof shot 4, the exploded diagram moved to shot 5, then the looping ending.
- **Read-out basis:** every frame that shows the read-out records the integers drawn next to the simulated speeds of that frame, and a new gate (`readout_matches_simulation`) requires exact agreement on all 561 frames that show it, requires the fixed lane to reach 0 and the breakaway lane to end at the simulated speed it keeps. This also found one precision artefact in the audit's own input (speeds rounded to 3 decimals sat on a .5 boundary at frame 165); the telemetry now keeps full precision. A tampered number is rejected (unit test). The pixels themselves are not read back: the drawn text is built from the same values.
- **Fixed-post stop distance:** the shot that compares the lanes states on screen that 0.8 m is an assumed deceleration distance.
- **Closing shot:** cuts to a full-frame view of the yellow sign face (the earlier closing views were too similar for the visual-activity rule).

## Gates on the real v2 video

Original QA PASS (visual_activity longest hold 3.5 s, black_opening, captions_visible, silence and loudness inside the film QA; integrated -16.5 LUFS, true peak -1.7 dBFS with the effects), motion_plausibility PASS, narration_screen_match PASS (6 of 6), first_three_seconds PASS, caption_safety PASS, readout_matches_simulation PASS. First vs last frame mean difference 0.59 (loop).

## Still open

- The assumed fixed-post crush distance (0.8 m), post and panel masses, slip force and base impulse are unchanged assumptions; no comparison with a test trace.
- Whether "comparison first, question narrated" retains better than v1 is unverified; it needs this video's own retention graph.
- The two lanes still replay the same collision in shot 2 (an instant replay from other cameras, same slow motion).

## Topic-selection note for planning

From the owner's comparison: a topic whose result is **visible destruction the viewer understands at once** (sand barrels bursting) held attention better than a topic whose interest depends on **understanding two structures** (fixed vs breakaway), and the latter needs a stronger and simpler first 3 seconds. Proposed criteria for choosing the next topics: (1) what is the single visible event in the first second; (2) can a viewer name the difference without narration; (3) does the explanation shot come after, not before, the event; (4) is there a number or length the screen can show honestly. This is an observation from one pair of videos, not a rule.

## Process record (round 2)

Six preflights: three audio server no-response events (re-run), long gaps then total silence (two narration lengthenings), sentence/shot spill and a read-out minimum (boundaries moved to the measured windows), and a 6.0 s hold in the closing shot (sign close-up). A GitHub API 502 made the watcher decode an old job's log once; the stale result was recognised (wrong hash, missing new gate) and discarded before anything was reported, and the real job log was fetched afresh. Production gates are closed again.
