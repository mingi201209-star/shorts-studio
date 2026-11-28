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
| B1-wall | 2.82-5.56 | The what-if, side on from the platform: the same train into a solid concrete wall, the front crushed, debris and dust. |
| B2-built-to-slide | 5.56-7.48 | From the overrun: the stop at rest with the empty rails behind it, the train still far off. |
| C-shoes (reveal) | 7.48-11.11 | X-ray with the sting: the stop's frame and the eight shoes on the rails glow orange, pushing in to a shoe's bolts. |
| D-buffers | 11.11-14.68 | X-ray: the train's buffer meets the stop's; the plunger squashes 0.48 m. |
| E1-shoved | 14.68-17.78 | Low beside the stop: shoved along the rails by the train, sparks off the shoes. |
| E2-heat | 17.78-20.52 | X-ray, low behind the last shoe: the shoes sliding on the rail, glowing hotter. |
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
  - the heat shot's camera first sat between two shoes;
  - the opening, the slide and the cab shots came in closer.
- The dust first read as glass bubbles; it is now a cloudy, soft-edged grey.
- Captions: "Afterwards, crews loosen" was 928 px in the heavy face, so captions.restyle now breaks any line wider than 900 px in
  two. EP.35's captions are unchanged (widest 876 px).

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

