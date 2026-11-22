# EP.20 plan: the "can opener" low rail bridge (crash beam vs a box truck's roof)

Owner request 2026-11-22: "다 올렸고 다음거 만들어" (EP.16-19 v2 all uploaded; make the next one).

Why this topic: the shape of EP.13 (69.2 % viewed): everyday road hardware with a hidden mechanism that is satisfying to watch, the
strange event already happening in frame 1. A box truck's roof being peeled open like a can by the steel beam in front of a low rail
bridge is a famous sight (Durham's "11foot8" bridge), and the question behind it has a clean answer: the beam is there on purpose to
take the hits, and a truck roof is 0.040 in aluminium on thin bows, so the steel wins and the roof peels while the lower cab rolls
under. Overlap check (docs/series-plan.md list + EP.12-19): no earlier episode used a bridge strike, a crash beam or a box body.

One thread, 11 lines (32.5 s, 197 wpm, voice -3 %): why it peels trucks -> rail bridge, 11 ft 8 in -> a steel beam out front takes
the hits -> the roof is aluminium thinner than a dime -> the steel wins: rivets pop, the roof peels back -> the cab is lower and rolls
under -> this truck is 13 ft, 16 in too tall -> a sensor turns the light red -> raised 8 in in 2019 -> trucks still hit it -> that's
why it's called the can opener (loops into the first line).

Frame 1 (hook rule, benchmarks/hook_gate.py): close, elevated 3/4 view from behind the truck's left side: the whole truck, the striped
beam and the bridge, the roof skin already rolled up against the beam (1.7 m peeled), shards and sparks in the air; held 2.49 s
through the first line in slow motion (x0.25) while the peel runs to 4 m and the truck stops.

Shots: A1 the peel (hero), B the rail bridge with a freight train and the truck driving in (the red sedan passes under easily),
C the beam takes the hit, D x-ray roof (skin over bows), E rivets popping and the roof rolling (x0.12), F the cab rolls under,
G level with the beam: the top 16 in of the box glow red, the red line marks 11 ft 8 in, H the detector ray broken by the box, the
warning beacons and the signal turning red (the truck stops), I the 2019 raise at the abutment (new shims, the red line keeps the old
height), J a truck still hits the raised beam (8 in), K loop back into frame 1.

Model benchmarks/can_opener/opener_motion.py (gate opener_physics: 16 in too tall, 8 in after the raise, skin thinner than a dime,
cab below the beam, energy balance within 1 %, peel 3.97 m (old) / 5.06 m (raised) of the 6.4 m box, peak 2.3 g), timeline
opener_timeline.py, renderer render_opener_3d.py (procedural box truck whose walls, front, roof skin, rails, bows and rivets deform
from the model every frame; shards, sparks and flying rivets launched at the model's times), sound opener_sfx.py, assembly
assemble_opener_film.py, CI .github/workflows/ep20-film.yml (request examples/experiments/opener-film-request.json), tests
tests/test_ep20_opener.py (incl. the camera never inside the truck, beam, columns, bridge, signal, poles or trees).

Narration capture: edge-tts at -3 % (the +5 % take ran at 212 wpm); line 9 written as "twenty nineteen" because the TTS merged
"In 2019" into one timed word.

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res runs (787 frames, 32.8 s): all 12 gates PASS (opening held 2.49 s, the whole truck in frame, 49 % of the width at the
smallest; 20.1 cuts/min, 197 wpm; loop seam 1.53 vs steps 2.43/1.05; mix -15.2 LUFS, true peak -1.9 dBFS, every line at least 8.5 dB
above the effects). Fixed on the way: the hero camera (ten framings tried: a 9 m truck in a 9:16 frame; the peel made a tall rolling
curl of skin so it reads at phone size), the box panels' normals (the plywood liner was outside: the box looked tan), the bridge,
sixteen-inch, sensor and cab-under shots re-aimed, the locomotive given a cab and a long hood, the scene built with the data API
(operators took about 6 min per render shard), effects lowered under lines 3, 6, 10 and 11.
CI: pending.
