# Reference clip: how much the picture keeps moving (measured)

One reference Short ("Why Deer Freeze In Headlights", a 30.9 s 3D explainer) supplied by the owner as three screen
recordings (10.47 s + 8.34 s + 12.05 s = 30.86 s, 1080x2340). The clip itself is not stored in this repository;
only numbers and our own observations are.

## Measured with `benchmarks/road_safety/motion_profile.py` (same crop, same 15 fps sample for every film)

| film | median frame-to-frame change | share almost still (<4) | share moving a lot (>25) | registered beats (2 fps, threshold 12) | longest stretch without a beat |
|---|---|---|---|---|---|
| reference clip | 14.7 | 11 % | 16 % | 57 in 31 s (0.54 s each) | 1.0 s |
| our sand barrels v4 | 2.8 | 64 % | 1 % | 27 in 32 s (1.19 s each) | 3.0 s |
| our runaway ramp, round 1 | 4.2 | 48 % | 3 % | 30 in 32 s | 3.0 s |
| our runaway ramp, round 2 | 4.5 | 45 % | 4 % | 32 in 32 s | 3.0 s |
| our runaway ramp, round 3 | 5.4 | 39 % | 4 % | 31 in 32 s | **5.0 s** (20.5-25.5 s, the top-down comparison) |

The shared visual_activity QA only requires a new beat within 5 s, so a film that holds a view for 3-5 s passes it.
The reference almost never holds: a new beat at nearly every half second.

## Observed structure (from sampled frames, 1 per second; not a frame-accurate edit list)
- 0-10.5 s: deer in the foreground, a car approaching head-on with bright headlights and a visible driver; the
  question is asked in the first ~5 s; then the answer begins and the camera pushes into the deer's eye.
- 10.5-18.8 s: eye close-up; a light beam enters the pupil; a cut to an anatomical cutaway of the eye with the
  same beam travelling through it; a contrast case (slow sunrise light) and back to the eye.
- 18.9-30.9 s: headlights hit all at once (the eye cutaway floods white), the deer freezes (question marks over it,
  the driver reaching), and the last frames return to the first (a loop).
- Large changes (frame difference > 35) cluster at about 0.3, 1.4, 11.3, 11.7, 12.4, 13.5, 14.9, 21.6, 25.1 and
  30.1 s; between them the picture still moves (typical difference 13-22).

## Caveats
- One clip. Its engagement figures (shown on screen: 340k likes, 2,940 comments) do not show that this motion
  profile caused them; topic, channel size and distribution matter.
- The numbers come from a screen recording of a streamed video: re-encoding noise adds some difference, so the
  reference's motion is an upper bound. Rows with the phone UI, side buttons and caption text were cropped out.
- The measure counts changing pixels, not whether the motion is meaningful.
- Audio was not analysed (a phone recording's level depends on the device volume).

## What this suggests (hypotheses to test, not conclusions)
1. Our "static feeling" (reported for the 10-22 s section) is measurable: 45-64 % of our frame pairs are almost still.
2. A camera that never fully rests (slow dolly or drift on every hold) plus a physical cause shown moving
   (the light beam entering the eye) is the pattern to try; the Cinematic Camera Director
   (`cinematic_camera.py`) is the tool for the first part.
3. Any new "continuous motion" gate must be added, never replace an existing one, and its target must be
   calibrated on more than one reference before it can fail a film.
