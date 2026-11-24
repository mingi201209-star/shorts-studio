# EP.21 plan: rockfall ring net (a 20-ton boulder caught above a mountain road)

Owner request 2026-11-22: "야. 이정도 이상의 퀄리티로 몇편 더 뽑아놔" (make several more at EP.20's quality or better).

Why this topic: the EP.13 shape again (road hardware with a hidden mechanism that is satisfying to watch, the strange event in frame
1): a steel net on a mountain slope that catches a boulder like a trampoline, and the hidden part is in the ropes: ring brakes, loops of
steel tube that shrink as they slip and turn the rock's speed into heat. Overlap check: EP.15 used cables to catch a car head-on
(rigid posts, no brakes); this is a net that gives way on purpose, with energy-absorbing brakes, against falling rock. No other
episode used rockfall.

One thread, 11 lines (35.1 s, 188 wpm, voice -3 %): how does a net stop a 20-ton boulder -> nets on the slopes above roads -> woven
from steel rings like chain mail -> it doesn't stop the rock dead -> it stretches more than twenty feet -> the ropes pull through
brake rings -> the loops shrink and bend, turning speed into heat -> a slow stop keeps forces low, nothing snaps -> the biggest stop
20 tons at 60 mph -> crews clear the rock and replace the brakes -> that's what the nets on cliffs are for (loops into line 1).

Frame 1 (hook rule): close view from below the net's middle span: the boulder already 4 m deep in the net, the net bagging around it,
posts leaning, chips and dust in the air; held 2.31 s through the first line in slow motion (x0.21) while the net stretches to 8 m.

Shots: A1 hero, B the road with the red sedan and the barrier above (the boulder bouncing down), C chain-mail rings close up with the
boulder coming behind them, D the hit seen along the barrier, E the stretch against the red outline of the net's rest plane, F the
retaining rope down to its brake, G the brake loop face-on shrinking and glowing, H the rock at rest, nothing broken, I below the
caught rock looking up, J clean-up time-lapse (rock cleared, net springs back, new brake loops), K loop into frame 1.

Model benchmarks/rock_net/rocknet_motion.py (gate rocknet_physics: 20 t at 60 mph = 7.2 MJ, within the 8,000 kJ top class; braking
distance 8.4 m (27 ft), stop in 0.53 s, energy balance within 1 %, brakes take 85 %, peak 1.4 MN = 7.2 g against 24 MN for a rigid
0.3 m stop; brake loops shrink from 0.35 to 0.14 m), timeline rocknet_timeline.py, renderer render_rocknet_3d.py (about 2,000 steel
rings that follow the bulge and turn with the net surface, ropes, brake loops whose size and glow come from the model, a faceted
boulder, chips and dust, slope, scree, pines, valley, mountains), sound rocknet_sfx.py, assembly assemble_rocknet_film.py, CI
.github/workflows/ep21-film.yml (request examples/experiments/rocknet-film-request.json), tests tests/test_ep21_rocknet.py (incl. the
camera never under the slope, in the net, the boulder or a post).

## Audience data
- Owner, 2026-11-24: "a success": 21,000 views and still climbing; 73 % and 93 % (owner's words: 시청률 73 %, 조회율 93 %; read
  as 73 % viewed rather than swiped away and 93 % average percentage viewed, the same pair EP.13 reported as 69.2 % / 90 %).
- The best upload so far, above EP.13 (9,000 views, 69.2 % / 90 %), and the first made under the held-opening rule
  (benchmarks/hook_gate.py) to report back. Why it worked: frame 1 is the whole strange event already happening (a 20-ton boulder
  deep in a bagging steel net, held 2.31 s with the net span 99 % in frame); one counter-intuitive idea (it doesn't stop the rock
  dead: it stretches more than twenty feet, and brakes turn the speed into heat) shown by a satisfying motion; the size of the
  numbers (20 tons, 60 mph); 188 wpm, 35 s, a loop.

## Preview
Local low-res run (848 frames, 35.3 s): 11 of 12 gates PASS; opening_hook FAILED (the middle span 77 % in frame in the first second).
Fixed by re-aiming the hero camera (checked in Blender: 99-100 % of the span in frame over the first second). Also fixed on the way:
the dust spheres were built 50 m under their origin (invisible), the slope's blocky grass squares (one blended ground material now),
the brake glow (was washing out to white), several cameras re-aimed (closer to the pocket, the brake loop face-on). 18.7 cuts/min,
188 wpm; mix -15.2 LUFS, every line at least 12.7 dB above the effects; loop seam 1.54 vs steps 1.62/1.03.
CI (run 45079309564, 848 frames at 720x1280, 16 samples, composed to 1080x1920): all 12 gates PASS. Opening hook held 2.31 s, the
middle span at least 99 % in frame and 54 % of the width in the first second; 18.7 cuts/min, 188 wpm; mix -15.2 LUFS, every line at
least 12.7 dB above the effects; loop seam 1.73 vs steps 2.26/1.31. Film sha256 57ddd5140a6c8890816d377cc803e46993496e3f21ce1d30400f1595889270be.
