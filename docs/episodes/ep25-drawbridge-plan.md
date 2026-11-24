# EP.25 plan: the drawbridge (why this road stands straight up)

Owner request 2026-11-24, after EP.21 reached 21,000 views at 73 % viewed and 93 % average viewed: "만든거 말고 새걸로 만들어" (not the
ones already made: a new one). The proposed sand-barrel crash cushion and breakaway posts had been made before (crash cushion,
breakaway sign), so the topic is new: a Chicago-type double-leaf bascule bridge.

Why this topic: the shape that worked twice (EP.13, EP.21): big road hardware doing something strange, shown mid-event in frame 1
with the whole subject in the picture, one counter-intuitive idea, big plain numbers. Here the road itself stands straight up while
cars wait and a sailboat passes; the hidden part is a counterweight in a pit under the street that balances thousands of tons like a
seesaw, so two motors about as strong as a car's engine lift it in about a minute. Comment hooks: being stuck at a drawbridge,
Chicago's bridge lifts, "bascule is French for seesaw".

One thread, 11 lines (34.2 s, 195 wpm, voice -10 % after a take at 207 wpm): why does this road stand straight up -> a drawbridge,
Chicago has dozens -> each half weighs thousands of tons -> yet two motors no stronger than a car's engine lift it in about a minute
-> the secret is hidden in a pit under the street -> a counterweight heavier than the road hangs behind the pivot -> like a seesaw it
balances the road almost perfectly -> so the motors only have to give it a nudge -> as the road tips up the counterweight swings down
into the pit -> that's why it's called a bascule, French for seesaw -> and when the next ship comes, up it goes again (loops into
line 1).

Frame 1 (hook rule): from the street behind the waiting cars, the hero bridge's east leaf standing at 78 degrees, its lane markings
running straight up, bridge houses and lowered gates on both sides; held through the first line.

Shots: A1 hero, B from the east bank: three drawbridges up along the river and the sailboat, C from the water: the raised leaf's
steel overhead, D time-lapse from the water: a leaf up in about a minute, E cut open: the pit under the street (road down), F the
counterweight behind the pivot as the leaf starts up, G the leaf and the counterweight as one seesaw, H the pinion turning against the
curved rack, I time-lapse cut open: the counterweight swinging down into the pit as the road goes up, J from the river: both leaves
upright, K loop: the road down, then up again into frame 1.

Model benchmarks/bascule_bridge/bascule_motion.py (gate bascule_physics: a 3,600 t leaf, a 9,000 t counterweight, balanced to
0.3 % so the leaf closes by itself; a 60 s opening to 78 degrees needs at most 192 hp, inside two 108 hp motors; without the
counterweight about 21,000 hp, 108 times more; the counterweight drops 8.4 m into the pit), timeline bascule_timeline.py, renderer
render_bascule_3d.py (river, walls and riverwalk, brick and glass towers, three bascule bridges with deck, lane marks, girders,
railings and lamp posts, bridge houses, gates and red lights, waiting cars with the CC0 sedan in house red, a sailboat; on the hero
bridge the trunnions, the pit, the counterweights, the curved rack, the pinion and its motor, cut open along the middle in section
shots), sound bascule_sfx.py, assembly assemble_bascule_film.py, CI .github/workflows/ep25-film.yml (request
examples/experiments/bascule-film-request.json), tests tests/test_ep25_bascule.py (incl. no camera inside the counterweight's swing,
under the water or in the cut street).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run (827 frames, 34.5 s): all 12 gates PASS. Opening hook held 2.13 s, the raised leaf 100 % in frame and
63 % of the width in the first second; 19.2 cuts/min, 195 wpm; mix -15.2 LUFS, every line at least 11.3 dB above the effects; loop
seam 0.21 vs steps 0.52/0.85. On the way: two cameras were inside towers, the cut-open shots were blocked by land that was not cut,
the pit was dark (work lights and a fill light), the gear close-up was under the machinery floor and later inside the
counterweight's swing (moved; a test now keeps every camera out of that swing).
CI: pending.
