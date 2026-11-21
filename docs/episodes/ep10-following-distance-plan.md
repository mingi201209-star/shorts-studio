# EP.10: following distance (the 3-second rule)

- Same fast, dense format as EP.09: 13 lines at +15 % rate, 38.7 s; a fact, timer, bar or count on almost every shot.
- Opening: labelled split (3-SECOND GAP / 1-SECOND GAP, SAME SPEED · 60 mph · SAME DRIVER) with live mph and GAP bars; the 1-second car
  rear-ends the car ahead at 0.96 s of film time; the 3-second car stops 40 m behind.
- Model (benchmarks/following/follow_motion.py, gate follow_physics): car ahead brakes at 0.8 g; both followers react after 1.5 s and brake
  the same; plastic impact. Numbers on screen come from it: 40 m / 44 yd reaction distance at 60 mph, 46 m vs 86 m, 11 m vs 46 m for 30 vs
  60 mph, 54 m / 59 yd for a 2-second phone look.
- Scene: straight road with a sign for the 1-2-3 count, blue follower with the stylised driver, a red copy of the car ahead with glowing
  brake lights, impact debris, a phone for the last fact.
- Frozen-frame risk in the top-down and sign shots was checked locally before the CI render (no frozen frames).
- Run 44811594362: every gate PASS on the first CI run; 934 frames, 38.9 s.
- NOT verified: voice pronunciation at the faster rate, sound-off readability, human first view. The owner uploads.

## Audience data (owner screenshot 2026-11-21, about 5 h after upload in the chart)
23.7 % viewed (kept watching) / 76.3 % swiped away; average view duration 0:40 on a 41.8 s Short (about 96 %).
Reading: the people who stay watch nearly all of it, but three in four leave in the first second. The opening is two small cars far
away on a wide road with four label boxes over it; the rear-end hit at 0.96 s is too small to read.
