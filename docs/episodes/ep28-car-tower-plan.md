# EP.28 plan: the car towers (why are hundreds of new cars stacked in a glass tower)

Owner pick 2026-11-25: "후자" (the latter: the robotic parking tower) from the two topics left after EP.27. Topic: the CarTowers
at Volkswagen's Autostadt in Wolfsburg, two 48 m glass silos where a robot on a central mast stores new cars that arrive from the
plant through a tunnel and fetches them for their buyers; a Guinness record as the fastest automatic parking system.

Why this topic: the shape that worked (EP.13, EP.21): a machine in the middle of a strange, mesmerizing motion in frame 1 (a car
riding up a glass tower full of cars), the whole subject in the picture, one counter-intuitive idea (no ramps, no drivers: a robot
packs 400 cars on the land of a few dozen), big plain numbers (seven feet a second, 400 cars, under two minutes).

One thread, 11 lines (37.9 s, 196 wpm, voice -10 %): why are hundreds of new cars stacked in this glass tower -> a car tower next to
a factory in Wolfsburg Germany -> new cars roll in from the factory through a tunnel -> a robot arm on a central mast picks each one
up -> it turns to face an empty bay and climbs almost seven feet a second -> then it slides the car in like a book onto a shelf ->
with no ramps or lanes the cars pack in tight -> each tower holds four hundred cars on twenty floors -> when a buyer arrives the robot
brings their car down in under two minutes -> the fastest automated parking system in the world -> that's why new cars here wait in
a glass tower for their owners (loops into line 1).

Frame 1 (hook rule): from the lawn, the whole hero silo with floor on floor of new cars behind the glass, the red car on the robot's
yellow fork rising inside; held through the first line.

Shots (12): A1 hero, B the two silos, the glass hall, the canal and the factory with its four chimneys from the air, C in the tunnel:
the red car rolling in on its carrier, D the transfer station under the silo: the arm takes it up the shaft, E1 through the open
column: it turns to face its bay, E2 from the top of the open column: it races up toward us, F from outside straight into its bay:
the fork slides it in, G up the facade: floor on floor of cars, H 400 cars on 20 floors with the twin beside it, I fetched for its
buyer (time-lapse), J riding down with it in the open column, K loop into frame 1.

Model benchmarks/car_tower/tower_motion.py (gate tower_physics: 2 m/s = 6.6 ft/s; 400 cars on 20 floors; a silo about 49 m tall;
the slowest fetch 72 s, under two minutes and the published 104 s; a car turning on the fork clears the stored cars by 0.14 m; bays
2.23 m wide at their inner end; about 1.1 m^2 of land per car against about 25 in a ramped garage), timeline tower_timeline.py,
renderer render_tower_3d.py (lawn, lagoon, the glass hall, the canal, the factory with four chimneys, trees; two glass silos with
mullions, floor rings, ring lights, a steel mast, two carriages each with a fork, about 650 stored cars; the hero silo keeps one
column of bays open so the cameras can look in; the tunnel with its carriers and the transfer station under the silo), sound
tower_sfx.py, assembly assemble_tower_film.py, CI .github/workflows/ep28-film.yml (request
examples/experiments/tower-film-request.json), tests tests/test_ep28_tower.py (incl. no camera in the stacks, the twin, the ground,
the red car or the carriage's sweep).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run (915 frames, 38.1 s): all 12 gates PASS. Opening hook held 3.15 s, the silo 100 % in frame and at least 58 % of
the width in the first second; 18.9 cuts/min, 196 wpm; mix -15.1 LUFS, every line at least 15.8 dB above the effects. On the way:
the first hook camera stood inside the glass hall (moved the hall), the tunnel and the transfer station were dark because the
lawn slab cut through them (ceilings now under it, a shaft opened under the silo), the floor rings blocked the open column (now a
slot through every floor), and the turn shot started with its camera underground (it now starts once the carriage is up).
CI (run 45561757009, 915 frames at 720x1280, 16 samples, composed to 1080x1920): all 12 gates PASS. Opening hook held 3.15 s, the
silo 100 % in frame and at least 58 % of the width in the first second; mix -15.1 LUFS, every line at least 15.8 dB above the
effects; loop seam 0.01 vs steps 0.70/0.83. Film sha256 3b3d87d0f14215deebc7fc89c77628488cdd024cf1901da2d8d000b9e7301316.
