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
