# EP.36 plan: how do you stop a runaway train at the end of the line? (friction buffer stop)

Owner, 2026-11-27: "ㅇ" to parts 4-6 of "Built to Get Hit" (EP.35 carrier wire, EP.36 train buffer stop, EP.37 elevator safety
brake). 2026-11-28: "시작" (start), then "처음 만들 때부터 예고를 붙여" (attach the teaser from the very first build). So this film
is delivered with part six's teaser already at its end. EP.37's opening was designed, recorded and rendered first, and it is now
frozen (playbook section 10).

## Facts (sources in the publish kit's claims check)
- Friction buffer stops slide: friction shoes or grips (bronze inserts) bolted to the rail head; the energy goes into heat over
  a set braking distance (Rawie; Oleo).
- Oleo: each pair of shoes up to 50 kN; gas-hydraulic buffers take low-energy hits without sliding. A six-car, 246 t train stops
  in about 18 m (59 ft) at 25 km/h (15.5 mph).
- Hard car braking with ABS on dry roads averages 0.87-1.08 g (SAE 2023-01-0616). Bane NOR caps a buffer stop's deceleration at
  10 m/s2.
- After an impact, the stop is put back by loosening the clamping bolts, moving it and tightening them (US 5,209,165).

## Narration (Bumper, ElevenLabs eleven_multilingual_v2; 107 words, 34.6 s, 185 wpm; examples/episodes/ep36-audio)
1. How do you stop a runaway train at the end of the line?
2. Hitting a solid wall would wreck it, so this buffer stop is built to slide.
3. It's clamped to the rails by steel shoes, bolted on tight.
4. When a train hits, the stop's hydraulic buffers squash first.
5. Then the whole stop gets shoved along the rails, and the friction turns the train's speed into heat.
6. A six-car train at fifteen miles an hour stops in about sixty feet.
7. That's gentler than slamming on the brakes in your car.
8. Yes, that's me driving. Again.
9. Afterwards, crews loosen the bolts, push it back, and tighten them again.

Line 7 was first "Gentle enough that the coffee in the cab doesn't spill." The model then showed it would not hold. The stop's
kick, getting its own 4.5 t up to speed, peaks at 0.23 g, and a cup with 15 mm of headroom would spill. The line was re-recorded
as the car comparison, which holds by a wide margin, before anything was rendered.

## Shots (each line shows what it says; benchmarks/buffer_stop/stop_timeline.py)
| Row | Film s | Shot |
|---|---|---|
| A1-slides | 0.00-2.82 | Ahead-right of the stop: the six-car train shoving it along the rails, buffers squashed, sparks off the shoes; slow motion. |
| B1-wall | 2.82-5.56 | The what-if, side on from the platform: the same train into a solid concrete wall; the cab sides fold up like an accordion (the model's 0.3 m crush), the windscreen crazes, glass and concrete fly, dust. |
| B2-built-to-slide | 5.56-7.48 | From the overrun: the stop at rest with the empty rails behind it, the train still far off. |
| C-shoes (reveal) | 7.48-11.11 | X-ray with the sting: the stop's frame glows orange and the eight shoes on the rails, with their bolts, yellow-white; pushing in to a shoe's bolts. |
| D-buffers | 11.11-14.68 | X-ray: the train's buffer meets the stop's; the plunger squashes 0.48 m. |
| E1-shoved | 14.68-17.78 | Low beside the stop: shoved along the rails by the train, sparks off the shoes. |
| E2-heat | 17.78-20.52 | Thermal look, low on the rail just ahead of the last shoe: the stop blueprint blue, the shoes and the rail they have rubbed glowing from red to yellow-white as their heat builds (61 % to 94 % of each shoe's 360 kJ, from the model). |
| F-sixty-feet | 20.52-24.55 | High behind the stop: its slide laid out in yellow on the track (59 ft), the train following it in and stopping. |
| G-gentler | 24.55-27.47 | Split: Bumper in the cab, barely moved (top); a dummy thrown forward in a car braking hard (bottom). |
| H-thats-me | 27.47-29.83 | Through the windscreen: Bumper at the controls, waving once stopped. |
| I1-loosen | 29.83-32.88 | The crew in orange turning the shoes' bolts with wrenches. |
| I2-push-back | 32.88-34.86 | From the platform end: a yellow rail tractor pushing the stop back to its mark. |

## Model (benchmarks/buffer_stop/stop_motion.py)
- Two bodies: a 246 t train at 25 km/h, and a 4.5 t stop with eight pairs of shoes (four on each rail) at 40.5 kN per pair (the
  pair force is found so the train stops in 59 ft). They meet through two gas-hydraulic buffers: spring and oil, capped by the
  oil's relief pressure, with a 0.6 m stroke.
- Result: the buffers squash 0.48 m and the stop slides 17.8 m. The train stops in 59.0 ft (18.0 m) in 5.3 s, peak 0.23 g,
  average 0.14 g. The shoes take 98 % of the 5.93 MJ as heat, about 360 kJ each.
- The what-if wall: 8.2 g, 35 times the stop's peak. The comparison car: 0.8 g from 30 mph.
- Gates: the claims, the energy balance (2 %), the 50 kN pair limit, the 1 g limit, the buffers within their stroke.

## Storyboard notes
- Detail from the start (EP.35's lesson):
  - the track: a real rail section, sleepers with clips, ballast;
  - the station: platform coping, yellow line and tactile strip, a canopy with lights and benches, passengers;
  - the overhead line with droppers, the concourse, a parked train on the next track and a siding;
  - the stop: shoes with bronze inserts, through-bolts and nuts, an end lamp;
  - the train: a cab with a desk and screens, doors, pantographs, bogies.
- The bolts were first drawn through the rail's web. They now pass just above the rail head and squeeze the jaws together.
- The cab first sat inside the solid body, so Bumper was hidden. The cab end is now built open (nose, sloped windscreen, side
  panels, roof), and the cab sides are white with the yellow front mask.
- Cameras moved after the sheets:
  - the wall shot's camera first sat beside the parked train, then behind the wall; it is now side on from the platform;
  - the push-back shot's camera first sat inside the parked train's cab;
  - the heat shot's camera first sat between two shoes; after the full-size check it came down to the rail, just ahead of the
    last shoe, so the glowing shoes fill the frame;
  - the opening, the slide and the cab shots came in closer.
- The dust first read as glass bubbles; it is now a cloudy, soft-edged grey.
- Captions: "Afterwards, crews loosen" was 928 px in the heavy face, so captions.restyle now breaks any line wider than 900 px in
  two. EP.35's captions are unchanged (widest 876 px).
- The full-size check of CI v1 (run 46094432645) found three shots that did not show their line well enough:
  - B1, the wall what-if:
    - the dust was see-through spheres, and where a puff cut into the train or the wall it drew a hard circle;
    - the crash read as a flat white side touching a grey block. The wall reached over the platform edge and hid the corner
      where the cab meets it, and the model's 0.3 m crush was only a uniform squeeze of the nose.
    Now:
    - the wall is as wide as the track bed;
    - the camera stands on the platform beside the wall, so the train comes at us and hits it;
    - the cab's sides fold like an accordion by exactly the model's crush, the front strips first (up to 62 degrees, stop_motion.fold_angles);
    - the windscreen crazes and 28 glass shards fly with the concrete;
    - the dust is a volume (no surface, so no edge where it meets the train), a little self-lit so a thick puff reads light
      grey, rising off the contact. A first try at full density read as black smoke.
  - C, the shoes: the whole stop glowed the same orange. Now the shoes and their bolts glow yellow-white on the orange frame.
  - E2, the heat: it was the same orange x-ray, only a little brighter, so nothing said heat. Now it is a thermal look:
    - the rest of the stop turns blueprint blue;
    - the shoes, and the rail they have rubbed, glow from red through orange to yellow-white (an ironbow ramp,
      benchmarks/identity/xray.thermal_material);
    - the glow follows each shoe's friction heat in the model, from 61 % to 94 % of its 360 kJ through the shot.
  New gates check all three: the folds against the model's crush, the shards, the shoes in focus, the heat against the model.

## Local and CI
Local low-res (837 frames at 162x288, 3 samples, composed to 1080x1920). Every gate PASS but one:
- passed: physics, pace (20.7 cuts a minute, 185 wpm, 34.9 s), line alignment, telemetry, visible action, no scene text,
  smoothness (no frozen frame), black opening;
- passed: captions (widest line 705 px), audio -15.1 LUFS, true peak -1.9 dBFS, speech 11.8 dB over the effects;
- failed: the opening hook, because of how its box was drawn. The subject box reached behind the opening camera, so it projected
  as off screen. It now covers the train's nose and the stop's buffers and beam: in the first second the subject is 100 % in frame
  and 61 % of the width (re-rendered and checked). The crew shots' telemetry check was too strict for positions recorded to four
  decimals; its tolerance is now 1 mm.
After the 1 fps sheet, the split's two cameras moved in: the car's dummy is seen thrown forward, Bumper in the cab barely moves.

CI v1, run 46094432645 (sha 52eed2e, renderer 25f62fdf, 70 frame jobs at the full 1080x1920 / 16 samples + final, 74 min):
every gate PASS. Checked at full size it was not delivered: the wall what-if, the shoes and the heat shot did not show their
lines well enough (storyboard notes above).

CI v2, run 46122473476 (sha 16bf9ca, renderer b2b684de, 70 frame jobs + final, 72 min): every frame rendered.
- The final failed on one gate, telemetry, and the cause was a bug in the gate, not the film. The new heat check had been placed
  inside the gate's chain of variant checks, so every train frame fell through to "unknown variant".
- The fix moves the check after the chain. tests/test_ep36_stop.py::test_telemetry_gate_takes_every_variant now feeds the gate
  model-true records of every frame and variant; it fails on the old code with CI's exact message and passes on the fix.
- The fixed gate was run on CI v2's own frame records for every frame the v2 changes touched: PASS on 228 frames, one renderer.
  Those frames are the opening, the whole wall shot and the whole heat shot (frames 0-143 and 420-503):
  - the folds reach 62 degrees at the 0.3 m crush;
  - 28 shards;
  - the heat runs from 61 % to 94 %.
  The other shots' records were not fetched again; their checks are the same as in CI v1, which passed them.
- Every other gate PASS in CI:
  - physics, pace (20.7 cuts a minute, 185 wpm, 34.9 s), line alignment;
  - opening hook (the subject 100 % in frame, 61 % of the width);
  - visible action, with the new checks: the folds, the shards, the shoes in focus, the heat rising;
  - no scene text, smoothness (no frozen frame), black opening;
  - captions (widest line 705 px);
  - audio -15.1 LUFS, true peak -1.9 dBFS, speech 11.8 dB over the effects.
- Film stop-film-1080x1920.mp4 sha256 8016624e17c465c998e52cc172a048a3363ebf1515b6d0ee861b54dc59b9c14a (837 frames, 34.875 s).
  Its effects bed is the same as v1's (sha256 24c99b71).
- Checked at full size:
  - the wall what-if: the train coming at the platform, the windscreen crazing, the cab's sides folding, glass, concrete and dust;
  - the shoes yellow on the orange frame, pushing in to the bolts on "bolted on tight";
  - the shoes glowing in the thermal look on "speed into heat";
  - the rest as in v1.

## The part-six teaser, in the first build (owner, 2026-11-28: "처음 만들 때부터 예고를 붙여")
- EP.37's first line was recorded first and frozen (examples/episodes/ep37-audio/line1): "What stops an elevator full of people
  from falling if every one of its cables snaps?". It is 4.4 s long, so EP.37's opening shot is held to 3.6 s and a close shot
  follows inside the same line.
- EP.37's opening was then built and rendered at 1080x1920 (run 46092206288, renderer 1b43eb9f, frames 0-107):
  - the hoistway cut away on one side, the car behind glass with Bumper and two passengers;
  - the safety gear's wedges biting the guide rails in a shower of sparks, the broken rope ends whipping above;
  - then a close look at a wedge on the rail.
  Its effects come from benchmarks/elevator_safety/car_sfx.py (the opening only). That opening is now frozen for EP.37.
- The line: "Subscribe for part six: what stops a falling elevator?" in Bumper's voice, the shortest of four takes (3.32 s), frozen
  in examples/episodes/ep36-audio/tail. The tail is EP.37's frames 0-90 (3.79 s).
- Built with benchmarks/series_tail.py from CI v2's final and EP.37's opening (frames 0-90 of run 46092206288, renderer 1b43eb9f,
  and its effects). Every gate PASS:
  - 928 frames, 38.667 s; the film part re-encoded once (PSNR 52.55 dB);
  - the tail hash-checked as EP.37's frames;
  - the captions say the line;
  - mix -15.1 LUFS, true peak -1.9 dBFS, the line 14.9 dB over the effects;
  - no frozen frame.
- Film stop-film-1080x1920.mp4 with the tail, sha256 e320d79213dd90443e01fffda62f56f4e0bb5d789d41b0bf8dfcfa26379742cf, copied to
  ep05-review/EP36-friction-buffer-stop.mp4 (upload this one).
- EP.35 v3 ends with this film's opening (frames 0-101 of CI v2), rebuilt after the wall shot's new camera
  (docs/episodes/ep35-wire-plan.md, v3).

