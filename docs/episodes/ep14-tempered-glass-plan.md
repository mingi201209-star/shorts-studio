# EP.14 plan: tempered glass (first episode built on the competitor research)

Owner request 2026-11-21: "apply this and make the next one" (docs/competitor-analysis-2026-11-21.md).

Applied: first cut at 1.30 s (a pace gate fails the build after 1.5 s); 23.5 cuts a minute; one question; 171 words a minute;
35.8 s (Zack D. Films' median is 35 s); an everyday mystery (glass cubes everyone has seen on the road); frame 1 is the whole side
window already bursting into cubes; EP.13's house style (golden hour, red car, depth of field, sound design); no text but the
captions; one-emoji title. Overlap check: no earlier episode is about glass.

Thread: why cubes -> tempered (heat, air quench) -> surface sets, core squeezes it -> about 4x stronger -> energy locked in ->
break the surface and it all lets go -> crack front at nearly a mile per second -> blunt cubes, not shards -> windshields are
laminated -> that's why emergency hammers are made for side windows (loops into the opening burst).

Model benchmarks/tempered_glass/glass_motion.py (gate glass_physics), timeline glass_timeline.py (with the pace gate), renderer
render_glass_3d.py (the CC0 cab gets a real window opening cut into it), sound glass_sfx.py, assembly assemble_glass_film.py, CI
.github/workflows/ep14-film.yml (request examples/experiments/glass-film-request.json), tests tests/test_ep14_glass.py.

## Audience data
(to be recorded at 48 h and 7 days, per the research)

## Preview
CI run 44901815322 (commit 9f825cf): all 11 gates PASS (physics, pace, alignment, telemetry, visible action, no text, loop,
smoothness, black opening, captions, audio mix); 858 frames, 35.8 s; first cut 1.30 s, 23.5 cuts/min, 171 wpm; mix -15.2 LUFS,
true peak -1.9 dBFS, every line at least 12.2 dB above the effects. The sound mix has not been listened to by a person.

## v2 (owner review 2026-11-21: "parts overlap the car")
Measured against this car's body: the cabin set's headrests reached 1.31 m through the 1.26 m roof, the dashboard top poked up
through the hood at the windscreen base, and the cabin floor showed below the doors. Floor and dashboard top hidden, headrests
lowered 0.12 m. Whole film re-rendered in CI.
