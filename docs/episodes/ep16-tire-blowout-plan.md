# EP.16 plan: tyre blowout (first episode under the still-frame rule)

Owner request 2026-11-21: "1" (new topic after EP.15's 13.7 %).

Applied: frame 1 must read as violent as a still at phone size (docs/series-plan.md, EP.15 data): a low side view under the front
wheel with black rubber pieces sprayed into the air against the red car and sky, the dust of the burst, the tyre flat on its rim.
First cut 1.30 s; 14 shots (26 cuts a minute); 193 words a minute; 32.2 s; one thread; no text but the captions; house style.
No shot of the car just driving longer than 2.1 s. Overlap check: hydroplaning (EP.09) was tread and water; nothing on tyre heat.

Thread: why tyres explode -> it starts days earlier with a low tyre -> the sidewall bends at the bottom and springs back -> 15 times a
second at 60 mph -> bending makes heat -> heat cooks the belt bond -> the tread peels, the tyre bursts -> tyres lose a pound a month
-> that's where the shreds on the highway come from (loops into the burst).

Model benchmarks/tire_blowout/blowout_motion.py (gate blowout_physics), timeline blowout_timeline.py, renderer render_blowout_3d.py
(procedural deformable tyre with a cut-away window and two steel belts), sound blowout_sfx.py, assembly assemble_blowout_film.py, CI
.github/workflows/ep16-film.yml (request examples/experiments/blowout-film-request.json), tests tests/test_ep16_blowout.py.

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
CI run 44933230150 (commit 161c680): all 11 gates PASS; 773 frames, 32.2 s; first cut 1.30 s, 26.1 cuts/min, 193 wpm; mix -15.2 LUFS,
true peak -1.9 dBFS, every line at least 11.5 dB above the effects. Copy: ep05-review/EP16-tire-blowout.mp4. Not listened to yet.
