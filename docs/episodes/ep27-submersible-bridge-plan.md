# EP.27 plan: the submersible bridge (why this road sinks into the sea)

Owner pick 2026-11-24: "1" from three proposed topics after EP.26 (more amazing road machines like the EP.13 guardrail curl).
Topic: the submersible bridges at the ends of the Corinth Canal in Greece, which lower the road about 8 m under the water so ships
can sail over it.

Why this topic: the shape that worked (EP.13, EP.21): road hardware in the middle of a strange event in frame 1 (the road running on
into the sea behind a closed gate), the whole subject in the picture, one counter-intuitive idea (the bridge goes down, not up, so no
mast is too tall), big plain numbers (26 ft, 13 ft a minute). Comment hooks: driving over it just after it comes up, Greece, waiting
for a bridge.

One thread, 11 lines (32.9 s, 197 wpm, voice -8 %): why is this road sinking into the sea -> a bridge across the Corinth Canal in
Greece -> when a ship is coming gates stop the traffic -> then the whole road sinks about twenty-six feet underwater -> at about
thirteen feet a minute -> and settles almost on the bottom of the canal -> ships sail right over the top of the drowned road -> with
nothing above the water no mast is ever too tall -> a lift bridge would need towers taller than the masts -> once the ship has passed
the road rises again dripping wet -> that's why drivers here sometimes wait for their road to come back up (loops into line 1).

Frame 1 (hook rule): from the approach behind the waiting red car and the lowered gate, the road running on into the sea as the
water floods over it; held through the first line.

Shots (12): A1 hero, B above the canal cut looking down it to the bridge and the sea, C behind the red car as the gate comes down,
D under water: the whole deck sinking, E the deck's end sliding down past depth bands on the quay (the speed), F under water: the
deck settling into its pit in a cloud of silt, G under water looking up: the tall ship's hull passing over the drowned road, H from
the quay: the masts going by with nothing over them, I the towers a lift bridge would need (translucent), J1 the ship going on into
the cut, J2 the road rising out of the water with water pouring off it, K loop: cars waiting behind the gates as the road starts
down, into frame 1.

Model benchmarks/submersible_bridge/sinking_motion.py (gate sinking_physics: a 33 m deck from 1.2 m above the water to 8 m below it
(26.2 ft) at 4 m (13.1 ft) a minute with soft starts and stops, 142 s each way; the road stops 0.5 m above the canal bed; 4.2 m under
the keel of a tall ship (3.8 m draft, 38 m masts) while it is over the deck; the gates down whenever the road moves or is under; a
lift bridge for the same masts would need 45 m towers), layout sinking_world.py (the canal cut along +y, the chamber between concrete
quays at the bridge, the pit, the breakwaters and the sea), timeline sinking_timeline.py, renderer render_sinking_3d.py (land,
limestone cut, turquoise water as a volume, quays with depth bands, the deck, gates and lights, the control house and a few houses,
cars with the CC0 sedan in house red, the tall ship, the translucent lift bridge, foam, bubbles, silt, pouring water and drips),
sound sinking_sfx.py, assembly assemble_sinking_film.py, CI .github/workflows/ep27-film.yml (request
examples/experiments/sinking-film-request.json), tests tests/test_ep27_sinking.py (incl. no camera in the land, the deck or the
ship, under-water cameras under the water and the others above it).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run (796 frames, 33.2 s): all 12 gates PASS. Opening hook held 2.24 s, the deck 100 % in frame and at least 42.3 % of
the width in the first second; 21.7 cuts/min, 197 wpm; mix -15.2 LUFS, every line at least 12.2 dB above the effects. On the way:
the first hook camera behind the cars could not see the water at all (the quays hide it; now from the approach, higher, the road
running on into the sea), the aerial along the sea showed the canal as a thin strip (now from above the cut looking down it), the
under-water shots were murky (clearer water, closer cameras), the lift-bridge ghost was too faint. The loop shot's start was then
moved away from a house roof.
