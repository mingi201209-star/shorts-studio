# EP.23 plan: exploding manhole covers (a 300 lb lid in the air above a city street)

Owner request 2026-11-22: "야. 이정도 이상의 퀄리티로 몇편 더 뽑아놔" (make several more at EP.20's quality or better).

Why this topic: a "wait, what?" first frame (a manhole cover in the air above a column of fire on an ordinary street) with a
hidden cause most viewers have never thought about (road salt, old cable insulation, gas in the vault) and an answer they can
spot on their own street (covers full of holes). No other episode went under the street or used fire, gas or electricity.

One thread, 11 lines (35.9 s, 180 wpm, voice +6 %): why do manhole covers sometimes blast into the air -> power cables run through
vaults under many streets -> in winter salty meltwater drips onto old cables -> the salt eats the insulation until it arcs -> the
burning insulation gives off flammable gas that fills the vault -> one spark and the gas explodes -> it can launch a cast-iron
cover of up to 300 lb -> so New York's utility is swapping in vented covers -> the gas escapes through the holes instead of
building up -> others are latched: they pop up a few inches, vent and drop back -> that's why some city covers are full of holes
(loops into line 1). Line 10 was shortened and the voice sped up after a first take at 168 wpm (38.9 s).

Frame 1 (hook rule): low view down the street, the cover 3.1 m up and turning over against the sky, a column of fire under it,
sparks and slush flying, a vented cover in the foreground; held 3.01 s through the first line in slow motion (x0.13).

Shots: A1 hero, B the street cut open (the vault under the road, cars and buildings above), C meltwater dripping onto the salty
cables, D arcs at the splice, E time-lapse of the gas filling the vault, F the spark, the flame through the vault, the cover lifting
(cut open), G the cover flying up against the low sun, G2 crashing down beside the hole and wobbling like a coin, H a vented cover
breathing smoke, I the gas staying low under it (cut open, time-lapse), J a latched cover popping up 3.5 in and dropping back,
K loop into frame 1.

Model benchmarks/manhole_blast/manhole_motion.py (gate manhole_physics: 300 lb cover; under a solid cover the gas reaches its lower
flammable limit after 8.3 min, under a vented cover it levels off at 2.0 % (39 % of the limit); the blast peaks at 70 kPa (10 psi),
throws the cover out at 10.5 m/s to 6.5 m (21 ft), it lands 1.5 m from the hole after 2.4 s; gas work on the cover within 1 % of its
energy; a latched cover is caught at 3.5 in and back on its seat after 0.47 s), timeline manhole_timeline.py, renderer
render_manhole_3d.py (winter street at sundown, a vault with racks, salted cables, a splice that chars and glows, duct banks, a
puddle; the cut through asphalt, gravel and soil with a water main and phone ducts; drops, arcs, gas haze, fire and smoke puffs,
sparks, slush; three covers: solid, vented, latched), sound manhole_sfx.py, assembly assemble_manhole_film.py, CI
.github/workflows/ep23-film.yml (request examples/experiments/manhole-film-request.json), tests tests/test_ep23_manhole.py (incl.
the camera never under the street, in a building, the parked car or the fire, and on the open side of every cut).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run (868 frames, 36.2 s): all 12 gates PASS. Opening hook held 3.01 s, the cover and the fire 100 % in frame and
55 % of the width in the first second; 19.9 cuts/min, 180 wpm; mix -15.2 LUFS, every line at least 11.0 dB above the effects; loop
seam 0.47 vs steps 3.12/3.46. On the way: the first fire and smoke were true volumes (100 s a frame at a quarter size, and too
faint) and are now soft surface puffs (3-5 s); the flying cover was lost against dark brick, so the hero and launch shots look along
the street with the sky behind it; the spark, the blast and the latch are timed to the words "spark", "explodes", "pop up" and
"drop back".
CI (run 45086567065, 868 frames at 720x1280, 16 samples, composed to 1080x1920): all 12 gates PASS. Opening hook held 3.01 s, the
cover and the fire 100 % in frame and 55 % of the width in the first second; mix -15.2 LUFS, every line at least 11.0 dB above the
effects; loop seam 0.17 vs steps 2.63/1.60. Film sha256 632fed4c5e1f00620d4f5ef38cf83c01917f4faff2fd02a33a438e21b05bb26e.
