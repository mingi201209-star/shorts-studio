# EP.29 plan: the blade lifter (why is this truck holding a giant blade up at the sky)

Owner brief 2026-11-25: "다른거 몇개 더 만들어놔" (make a few more, different ones). Three new topics: EP.29 the blade lifter,
EP.30 the bridge-building machine that walks, EP.31 the road that sprays water to melt snow.

Why this topic: a machine doing something you would never expect on a road (an 85 m blade pointing at the sky on a mountain bend),
the whole subject in frame 1, one counter-intuitive idea (tilt it up and it sticks out half as far), big plain numbers (60 degrees,
almost a football field, 12 mph, the 20 mph wind limit).

One thread, 11 lines (39.2 s, 193 wpm, voice -15 % after a take at 203 wpm): why is this truck holding a giant blade up at the sky
-> a wind turbine blade up a mountain road -> lying flat it can't get around these bends -> the trailer tilts it up as steep as
sixty degrees -> at that angle it sticks out only half as far -> it can swing the blade sideways to clear cliffs and trees -> almost
as long as a football field -> the truck crawls at about twelve miles an hour -> over twenty miles an hour of wind and the trip stops
-> the mountain roads don't have to be rebuilt -> that's why you might meet a wind turbine blade pointing at the sky (loops into
line 1).

Frame 1 (hook rule): from the road ahead of a sharp right bend, the rig coming round with the blade at 60 degrees, swung toward the
road, its red tip high in the sky; held through the first line.

Shots (12): A1 hero, B the winding road from the air, C from above: a blade lying flat sticks straight out off the bend over the
trees (the real blade hidden), D from the valley: the blade tilting up from 35 to 60 degrees, E side by side: tilted, it reaches
half as far as a flat one, F1 behind the rig: the blade swinging toward the road ahead, F2 over the rock cut and the trees, G the
whole rig from the valley, H in front of the rig and its escort, I stopped in a gale (leaves streaking, a windsock out, the blade
swaying), J the bend from the air, the road as it is, K loop into frame 1.

Model benchmarks/blade_lifter/blade_motion.py (gate blade_physics: an 85 m blade (279 ft), 60 degrees tilt (cos 60 = half the
reach), 20 degrees swing, 12.4 mph, a 22.4 mph wind limit; lying flat it would hang up to 54 m off the road and run into the trees
and the hillside; tilted and swung it stays at least 18 m above them; the wind's push at the limit is about 40 % of what holds the
rig upright, twice the limit would tip it), timeline blade_timeline.py, renderer render_blade_3d.py (the mountain land, road and trees
of EP.26 without the barrier; tractor, multi-axle lifter trailer, slewing ring, tilting cradle, the blade with a red tip; escort cars
with amber beacons, the CC0 sedan in house red leading; the translucent flat blade; leaves, a windsock and a swaying blade in the
gale), sound blade_sfx.py, assembly assemble_blade_film.py, CI .github/workflows/ep29-film.yml (request
examples/experiments/blade-film-request.json), tests tests/test_ep29_blade.py (incl. no camera in the land, the trees, the blade or
the rig).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
(local low-res run and CI to be recorded)
