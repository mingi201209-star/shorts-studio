# EP.03 speed bumps: planning check (nothing rendered, nothing uploaded)

## Real-world shapes (secondary sources; check ITE primary documents before any "design" claim)
- Speed hump: about 3-4 in (7.5-10 cm) high, about 12 ft (3.7 m) long, parabolic, design speed about 15-20 mph. Source: FHWA traffic-calming ePrimer, Univ. of Kentucky safe-design page.
- Speed table: flat-topped, about 22 ft (6.7 m) long (a car's wheelbase fits on top), higher design speed (about 25-30 mph). Source: Sacramento County NTMP.
- Sources disagree on table height (3-4 in vs 6-8 in) and ramp lengths. The film must say "typical", never "standard".
- Also real: short rubber/portable bumps (about 5 cm high, well under 1 m long), often harsher at the same speed.

## Same-condition comparison is possible (quarter-car model, `benchmarks/speed_bump/quarter_car_check.py`)
Assumed typical car values (400 kg sprung, 40 kg unsprung, 22 kN/m spring, 1.5 kNs/m damper, 200 kN/m tyre), NOT calibrated to a real car. Same 7.5 cm height, same car:

| speed | short 0.9 m | hump 3.7 m | table 6.7 m |
|---|---|---|---|
| 15 km/h | 0.69 g | 0.26 g | 0.23 g |
| 20 km/h | 0.81 g | 0.33 g | 0.24 g |
| 30 km/h | 1.08 g | 0.52 g | 0.36 g |
(peak body vertical acceleration)

Reading: at equal height and speed, the shorter the ramp the harder the body is pushed (about 3x between 0.9 m and 3.7 m). Direction matches the planned story ("how quickly the road lifts the car"). Hump vs table differs much less than short vs long.
Caution: body rise comes out above the bump height (about 10 cm for 7.5 cm) because the assumed damping is light; the film must not show the body rising more than a physically plausible amount, and no acceleration number should appear as a real-car measurement.

## Consequences for the plan
1. Compare **short rubber bump vs a 3.7 m hump** (or hump vs table) at the same height, speed and car; do not claim "round vs flat" is the cause, the length is.
2. On-screen numbers only as "SIMULATION, ASSUMED CAR"; no "safe speed" claims.
3. Hook frame must show two wheel paths in the first 3 s (same car, same speed), reusing the opening-camera and callout machinery from the ramp film.
4. Reuse list from the ramp film: shard renderer + proof/assembler, derived callouts, caption/QA gates, contact-sheet check. New: car + suspension model, bump geometry, wheel-path overlay.

## Next steps (waiting for owner choice)
Low-res preview of both passes (4-6 frames/s, small res) -> scene QA -> parallel full render on free runners -> edit -> final QA -> owner approval. No upload by the agent.

## Preview log (2026-11-15) and required gates
| preview | layout | pixel gate result | verdict |
|---|---|---|---|
| run 1 | side view, both lanes | not measured | scene a thin band, white sky: FAIL (looked at) |
| run 2 | chase from behind, high | not measured | cars small, no body motion visible: FAIL |
| run 3 | chase from behind, low | cars fill 10.8 % of height (need >= 22 %), body motion not visible | FAIL: full render on hold |
| run 5 | split: one side camera per car, stacked | see below | pending |

Evaluation department, new mandatory checks for this episode (`benchmarks/speed_bump/preview_gates.py`): both cars and both bump shapes visible in the first frame, cars fill >= 22 % of the panel height, body motion visible, bump shapes differ on screen (objective, pixels); question text within 1 s, a visible difference within 3 s, narration hook within 0.5 s (UNVERIFIED until a person confirms on the real video).
Not allowed to be exaggerated: the body motion must be drawn 1:1 with the model (no vertical scaling). If it is too small to see at 1:1, the scene must get closer (wheel arch close-up) or add a true-scale reference graph, never a magnified body.
