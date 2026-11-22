# EP.19 plan: spike strip (tyre deflation device)

Owner request 2026-11-22: "다음거 만들어봐. 퀄리티 높게" (make the next one, high quality).

Why this topic: a police spike strip is something people have seen in chase videos; the twist (the spikes are hollow so the tyre does
NOT burst) answers a real question and follows EP.16 (blowouts) without repeating it. Frame 1: low behind the front wheel on the
strip, quills already in the tread. Quality work: EP.16's deformable tyre, quills with a real hypodermic bevel that shows the bore
(macro), quills leaving their holders at the model's capture time and turning with the tyre, air jets whose length follows the
model's vent speed, a cut-away of the tyre with the quill through the tread, the tyre squashing as it deflates (time-lapse), shots
timed so the quills face the camera. 29.6 s, 11 shots (22.3 cuts a minute), 196 words a minute.

Model benchmarks/spike_strip/spike_motion.py (gate spike_physics: flat in 30.2 s, 1,500x slower than a burst, car stops at 31.3 s),
timeline spike_timeline.py, renderer render_spike_3d.py, sound spike_sfx.py, assembly assemble_spike_film.py, CI
.github/workflows/ep19-film.yml (request examples/experiments/spike-film-request.json), tests tests/test_ep19_spike.py.

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run: all 11 gates PASS (710 frames, 29.6 s; mix -15.2 LUFS, every line at least 12.6 dB above the effects). Fixed on
the way: the rear tyre took the same quill as the front (telemetry gate); D and G cameras re-aimed.
CI run 44990573970 (commit d6b9b1e): all 11 gates PASS; 710 frames, 29.6 s; first cut 1.30 s, 22.3 cuts/min, 196 wpm; mix -15.2 LUFS,
true peak -1.9 dBFS, every line at least 12.8 dB above the effects. Copy: ep05-review/EP19-spike-strip.mp4. Not listened to yet.

## v2 (2026-11-22): opening re-cut for the viewed rate
The opening is one held shot through the first line with the whole car/machine in the event (hero 3/4 or mid-wide) instead of a
1.3 s close-up cut to a weaker shot; checked by the new opening_hook gate (benchmarks/hook_gate.py).
CI run 44998408295 (commit ca1e350): all 12 gates PASS incl. opening_hook (opening held 2.68 s; car 77-100 % in frame, 73 % of the
width). Copy: ep05-review/EP19-spike-strip-v2.mp4.
