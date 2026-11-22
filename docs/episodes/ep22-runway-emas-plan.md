# EP.22 plan: runway arrestor bed (EMAS): a jet ploughs into crushable blocks

Owner request 2026-11-22: "야. 이정도 이상의 퀄리티로 몇편 더 뽑아놔" (make several more at EP.20's quality or better).

Why this topic: a "what is that" first frame (an airliner sinking into the ground at the end of a runway) with a clean hidden
mechanism: the bed is crushable, bubbly concrete; the tyres sink in and every block they crush takes away speed. It is the airport
cousin of the runaway truck ramp, but the mechanism is crushing (not loose gravel rolling resistance on an uphill grade) and the
subject is an airliner; no other episode used aircraft or crushable concrete.

One thread, 11 lines (34.4 s, 193 wpm, voice -3 %): why is the end of this runway built to crumble -> jets sometimes run off the end
-> airports add a bed of crushable concrete blocks -> light and full of bubbles -> the blocks crush under the plane -> the tyres sink
in like deep sand -> every crushed block takes away speed -> built to stop a jet at 80 mph (70 kt) -> it has stopped more than two
dozen planes with hundreds aboard -> crews replace the crushed blocks -> that's the gray pad at the end of some runways (loops).

Frame 1 (hook rule): high view from behind the jet's left side: the whole aircraft already 27 m into the bed, dust clouds at the
gears, chunks in the air, rubble-filled ruts behind the wheels; held 2.52 s through the first line in slow motion (x0.52).

Shots: A1 hero, B the jet racing at the end of the runway (head-on, red end lights), C aerial of the bed as the jet enters it, D the
foam inside the blocks on the bed's front edge, E the left main gear crushing into the blocks (under the wing), F the wheels deep in
the bed with chunks spraying, G the ruts growing behind the jet from above, H the stop from the side, I the jet at rest, J clean-up
time-lapse (towed out, ruts filled with new blocks), K loop into frame 1.

Model benchmarks/runway_emas/emas_motion.py (gate emas_physics: 70 kt = 80.6 mph, energy balance within 1 %, stops 93 m (306 ft)
into a 140 m bed after 5.1 s, peak 0.75 g, the bed takes 80 % of the energy), timeline emas_timeline.py, renderer render_emas_3d.py
(procedural 737-class jet with beacon, strobes and landing lights; about 4,400 blocks crushed under each gear as it passes; rubble in
the ruts; chunks and dust from every gear at a rate that follows the speed; runway, chevrons, end lights, perimeter road, bay, far
shore), sound emas_sfx.py, assembly assemble_emas_film.py, CI .github/workflows/ep22-film.yml (request
examples/experiments/emas-film-request.json), tests tests/test_ep22_emas.py (incl. the camera never under the bed or inside the
fuselage, a wing, an engine or a gear).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run (832 frames, 34.7 s): 11 of 12 gates PASS; visible_action FAILED (the shot of the jet running off the end of
the runway ended 0.03 s after the nose gear reached the bed). Fixed by ending that shot 0.2 s earlier (the nose 6 m short of the bed,
past the end of the runway). Opening hook: held 2.52 s, the jet at least 90 % in frame and 89 % of the width in the first second;
19.0 cuts/min, 193 wpm; mix -15.3 LUFS, every line at least 8.9 dB above the effects; loop seam 1.43 vs steps 2.15/1.69.
CI: pending.
