# EP.18 plan: wedge (anti-ram) barrier

Owner request 2026-11-22: "13번처럼 역동적이고 사람들이 처음 볼 때 'ㅅㅂ 이거 뭐지' 라고 생각할 만한 소재로 만들어봐" (dynamic like EP.13, a
thing people see for the first time and think "what the hell is that").

Why this topic: a steel wall that jumps out of the road and stops a car dead is strange, violent and mechanical, like EP.13's head
peeling the rail. Frame 1: the red car already crushing into the striped face, glass and sparks in the air, its rear lifting; at 1.3 s
the wall is seen jumping out of the road. One question, one thread; no text; house style; 31.97 s, 11 shots (20.6 cuts a minute),
197 words a minute. Overlap check: nothing earlier on security barriers; the crush uses EP.03's crush map but the story is the
barrier.

Thread: why did a wall jump out -> a security barrier, up in about a second -> a hinged plate in a concrete pit -> pistons swing it up
nearly three feet -> a car doesn't just bounce off -> struts push the crash into buried concrete -> the car stops dead, rear flips up
-> tested ones stop a 15,000 lb truck at 50 -> that's what those striped plates at secure gates are for (loops into frame 1).

Model benchmarks/wedge_barrier/wedge_motion.py (gate wedge_physics), timeline wedge_timeline.py, renderer render_wedge_3d.py, sound
wedge_sfx.py, assembly assemble_wedge_film.py, CI .github/workflows/ep18-film.yml (request examples/experiments/wedge-film-request.json),
tests tests/test_ep18_wedge.py.

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run: all 11 gates PASS (767 frames, 32.0 s; mix -15.2 LUFS, every line at least 9.2 dB above the effects). Then B moved
low behind the plate (the car charging in, the plate shooting up).
CI run 44980254232 (commit 818d023): all 11 gates PASS; 767 frames, 32.0 s; first cut 1.30 s, 20.6 cuts/min, 197 wpm; mix -15.2 LUFS,
true peak -1.9 dBFS, every line at least 9.7 dB above the effects. Copy: ep05-review/EP18-wedge-barrier.mp4. Not listened to yet.

## v2 (2026-11-22): opening re-cut for the viewed rate
The opening is one held shot through the first line with the whole car/machine in the event (hero 3/4 or mid-wide) instead of a
1.3 s close-up cut to a weaker shot; checked by the new opening_hook gate (benchmarks/hook_gate.py). CI: pending.
