# EP.15 plan: median cable barrier (in the style of EP.13/EP.14)

Owner request 2026-11-21: "다음거 만들자. 이 스타일로" after EP.13 (guardrail end) got the channel's first comment.

Applied (docs/episode-playbook.md): an everyday road mystery (the wires down the middle of the highway); frame 1 is the red car already
caught in the ropes, pushing them into a V; first cut at 1.30 s; 19.6 cuts a minute; 195 words a minute; 30.6 s; one thread; no text
but the captions; EP.13 house style; one-emoji title. Overlap check: EP.13 was the guardrail end terminal (energy absorbed by a head
running down a rail) and the earlier jersey barrier and sand barrels episodes; this one is the stretch-and-redirect of tensioned ropes.

Thread: why thin cables -> a car crossing the median meets oncoming traffic -> three ropes on flimsy posts -> posts fold -> ropes
stretch like a slingshot, about eight feet -> the long stretch slows it gently -> the tension steers it back along the median -> not a
wall, a steel net -> that's what the wires are for (loops into the opening catch).

Model benchmarks/cable_barrier/cable_motion.py (gate cable_physics: peak 7.8 ft, 2.7 g, 13 posts fold, ends on its own side),
timeline cable_timeline.py (pace gate), renderer render_cable_3d.py, sound cable_sfx.py, assembly assemble_cable_film.py, CI
.github/workflows/ep15-film.yml (request examples/experiments/cable-film-request.json), tests tests/test_ep15_cable.py.

## Audience data
- 81 min after upload (owner's Studio, 2026-11-21): 173 views and stalled, 13.7 % viewed (86.3 % swiped away), average 0:11 of 30.7 s,
  0 hypes. The lowest viewed rate of any upload.
- Reading: the swipe happens on frame 1. It is a head-on view of a car that looks parked on grass behind three thin white lines:
  no visible speed, no violence, mostly sky and lawn (also the thumbnail). The rule "frame 1 is a violent, readable event" was met
  on paper (the ropes are pushed in) but not on screen. Second suspects for those who stayed: 4 s of the car just driving (3-7 s)
  and 3.5 s of empty posts (7-11 s).

## Preview
CI run 44916163743 (commit aadc883): all 11 gates PASS (physics, pace, alignment, telemetry, visible action, no text, loop,
smoothness, black opening, captions, audio mix); 736 frames, 30.7 s; first cut 1.30 s, 19.6 cuts/min, 195 wpm; mix -15.2 LUFS, true
peak -1.8 dBFS, every line at least 10.9 dB above the effects. Copy: ep05-review/EP15-cable-barrier.mp4. The sound mix has not been
listened to by a person.
