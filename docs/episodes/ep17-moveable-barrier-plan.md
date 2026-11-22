# EP.17 plan: moveable barrier ("zipper" machine)

Owner request 2026-11-22: "ㅇㅋ 만들어" after EP.13 took off (9,000 views and climbing, 69.2 % viewed, 90 % average viewed).

Copies EP.13's shape: road hardware with a hidden mechanism that is satisfying to watch, working in frame 1 (the yellow machine with
the concrete wall snaking through it in an S, from above, traffic passing); one question, one thread; no text; house style.
First cut 1.30 s; 14 shots (25.5 cuts a minute); 187 words a minute; 32.9 s. Overlap check: EP.15 cable barrier and the earlier
jersey barrier were about stopping cars; this is about moving the wall.

Thread: why is the machine swallowing a wall -> it moves the wall a lane over with traffic flowing -> a chain of pinned blocks -> 1,500
lb each -> wheels grab the T tops -> an S track lifts and slides it twelve feet -> the blocks drop into a new line, still locked ->
morning: an extra lane for the busy side; night: it zips back -> that's why some walls change sides every day (loops into frame 1).

Model benchmarks/road_zipper/zipper_motion.py (gate zipper_physics), timeline zipper_timeline.py, renderer render_zipper_3d.py, sound
zipper_sfx.py, assembly assemble_zipper_film.py, CI .github/workflows/ep17-film.yml (request
examples/experiments/zipper-film-request.json), tests tests/test_ep17_zipper.py.

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run: all 11 gates PASS (790 frames, 32.9 s; mix -15.2 LUFS, every line at least 9.0 dB above the effects).
Then: machine wheels moved clear of the wall (new gate), traffic off the lanes next to the machine, entry shots from the right. CI: pending.
