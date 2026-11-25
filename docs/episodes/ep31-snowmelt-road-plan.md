# EP.31 plan: the road that sprays water (why is this road spraying water in a snowstorm)

Owner brief 2026-11-25: "다른거 몇개 더 만들어놔" (make a few more, different ones). Third of three new topics (EP.29 the blade
lifter, EP.30 the swivel bridge, EP.31 this).

Why this topic: a road doing something that looks wrong (spraying water in a snowstorm), the whole subject in frame 1, one
counter-intuitive idea (groundwater is warmer than snow, so water melts it), and a twist people argue about in the comments (why
doesn't it freeze? the ground sinks).

One thread, 10 lines (37.5 s, 192 wpm, voice -10 %): why is this road spraying water in a snowstorm -> in snowy parts of Japan
sprinklers are built right into the street -> nozzles down the middle of the road spray out water -> pumped from deep underground
where it stays around fifty degrees -> warmer than snow, so the snow melts as soon as it lands -> it started in Nagaoka in the 1960s
-> it works there because the snow falls near freezing so the water doesn't turn to ice -> the catch: lots of water, and the ground
can sink -> newer roads keep the warm water in pipes under the pavement -> that's why some streets in Japan wash their own snow away
(loops into line 1).

Frame 1 (hook rule): a snowy street at dusk from a pedestrian's height, a row of jets spraying across the wet, rust-stained asphalt,
a car coming through with its headlights on; the subject (the sprayed stretch and the car) fully in frame and half the width; held
through the first line.

Shots (13): A1 hero, B the town under snow from the air with its wet street, C a nozzle up close, D cut open along the centre line:
down the well to the warm water deep underground (the main under the nozzles, the casing, the screen and the pump in the gravel), E
flakes vanishing as they land in the water (rings where they land), F the whole street with the mountains, G1 wet snow falling past
the street lamps, G2 the jets coming down and the water running to the gutter (rings, the moving film), H1 a long row of jets, H2 cut
open: the ground sinking round the well while the casing stays (it sticks up out of the road), I the newer road: warm pipes under a
see-through window of asphalt, no jets, J the car driving on through the spray, K loop into frame 1.

Model benchmarks/snowmelt_road/snowmelt_motion.py (gate snowmelt_physics: 12 C (54 F) groundwater at 0.30 L/min per square metre
melts 2.7 cm of fresh snow an hour, more than a heavy 2.5 cm; the film keeps 19 W/m2 to spare with the air near 0 C and would freeze
at -10 C; about 180 m3 of water an hour per kilometre of street; pipes giving 250 W/m2 keep up with the same snowfall), world
snowmelt_world.py (the street, nozzles every 3 m and their jets, the falling snow, the car keeping left, the well and the layers),
timeline snowmelt_timeline.py, renderer render_snowmelt_3d.py (houses with snow-laden roofs and lit windows, covered sidewalks,
utility poles, lamps and wires, snowbanks, the town and mountains; droplets, flakes and rings rebuilt every frame from the world
model; the cut-open ground in a trench), sound snowmelt_sfx.py, assembly assemble_snowmelt_film.py, CI .github/workflows/ep31-film.yml
(request examples/experiments/snowmelt-film-request.json), tests tests/test_ep31_snowmelt.py (incl. no camera in the road, the
houses, the snowbanks or the car).

## Show what each line says (owner rule 2026-11-25)
Every line was checked against its shot. Changed: line 2 ("in snowy parts of Japan sprinklers are built right into the street")
now starts high over the snowy town and comes down into the street to the row of jets; line 6 ("started in the city of Nagaoka in
the nineteen sixties") is drawn as old sepia film with a vignette (gated: warm and nearly colourless, the neighbours in colour);
line 7 ("the snow falls near freezing") shows snow falling past a thermometer whose red column stops at the blue freezing mark
(no numbers). The v1 CI film (all gates passed) is superseded.

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
Local low-res run (whole film, 162x288 at 3 samples, 4 shards): every gate PASS on the first run (906 frames, 37.75 s, pace 20.7 cuts/min at 192 wpm, opening shot 2.73 s with the subject 100% in frame and 52% of the width, mix -15.0 LUFS, speech 15.1 dB over the effects, loop seam 0.47 against steps of 3.43). Found and fixed in the test stills before it: the car's headlights (a 75 degree cone at 500 W) threw conic-section blotches on the house fronts (now a flat low beam), the house meshes were smooth-shaded so the window grid bent into curves (now flat), the jets read as white wire loops (now uneven, breaking streams of clear droplets), the flakes were diamonds (now rounder and smaller), the section shots showed the empty sky under the cut (the ground now goes down 260 m and the cut is a trench).
CI: (to be recorded)
