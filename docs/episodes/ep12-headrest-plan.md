# EP.12 plan: headrest (One Difference series)

Rules applied: overlap check (no earlier episode is about rear impacts or the neck), one thread (hit -> seat pushes the back -> head stays
-> neck bends -> low: whip / high: caught -> how to set it), first-frame rule from the EP.09/EP.10 data (big side close-up of the two
drivers, one label per half, the hit at 0.2 s, readouts only after 1.5 s).

- Model: benchmarks/headrest/head_motion.py (rear-impact half-sine pulse, 10 mph delta-v; head on a spring-damper neck; headrest foam
  contact after a 4 cm backset; gate `head_physics`). Not calibrated.
- Film: 13 lines, 41.3 s at +15 % (examples/episodes/ep12-audio). Renderer render_head_3d.py, assembly assemble_head_film.py, CI
  .github/workflows/ep12-film.yml (request examples/experiments/head-film-request.json), tests tests/test_ep12_headrest.py.
- Publish kit: examples/episodes/ep12-publish-kit.

## Audience data
(to be recorded after upload)
