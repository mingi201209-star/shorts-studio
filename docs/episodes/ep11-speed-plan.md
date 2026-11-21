# EP.11 plan: speed, 30 vs 40 mph into the same wall (One Difference series) - SHELVED, not uploaded

Owner review 2026-11-21: overlaps EP.04 (car into a wall, crush rails) and EP.10 (stopping distance), and the explanation jumps between
five ideas. Kept in the repo for reference only; see the new rules in docs/series-plan.md.

Changed from the series plan's 50 / 60 km/h: the channel's audience is US, so the film uses mph, and 30 vs 40 mph gives a clearer picture
(energy +78 % instead of +44 %, crush 53 vs 70 cm, 3- vs 5-story fall).

- Model: benchmarks/speed_energy/speed_motion.py (linear crush stiffness, plastic; gate `speed_physics`). Not calibrated.
- Film: 13 lines, 42.0 s at +15 % (examples/episodes/ep11-audio); crash lands at 0.71 s in a labelled split (30 MPH green / 40 MPH red,
  SAME CAR · SAME WALL) with live speed and crush readouts; x-ray crush rails; crumple-zone-left bracket; energy bars; 3- vs 5-story drop
  next to a building; braking split with a cone where the 30 mph car stops; stylised driver; loop.
- Renderer benchmarks/speed_energy/render_speed_3d.py, assembly assemble_speed_film.py, CI .github/workflows/ep11-film.yml
  (request examples/experiments/speed-film-request.json), tests tests/test_ep11_speed.py.
- Publish kit: examples/episodes/ep11-publish-kit.

## Audience data
(to be recorded after upload: viewed %, average duration, subscribers per 1,000 views at about 2 h and 24 h)

## Preview
CI run 44835332391 (commit 4db3f21): every gate PASS (physics, alignment, telemetry, visible action, no scene text, loop, smoothness,
black opening, captions), 1014 frames, 42.25 s. v1 (run 44829009527) failed smoothness: 19 frozen frames in the loop run-in, fixed with a
camera push-in onto the opening shot.
