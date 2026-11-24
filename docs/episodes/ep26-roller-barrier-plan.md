# EP.26 plan: the rolling barrier (why this guardrail is covered in spinning rollers)

Owner request 2026-11-24, after EP.25: "이번엔 그 로드레일 감기는 것처럼 신기한 걸로 더 만들어" (this time, more amazing things like the
guardrail curling one). EP.13 (the guardrail end terminal peeling the rail into a coil) is the reference: road hardware doing
something you would never expect, shown mid-event in frame 1. New topic: the Korean rolling barrier, a guardrail lined with yellow
foam rollers that spin when a car slides into them.

Why this topic: the shape that worked (EP.13, EP.21): big road hardware in the middle of a strange event in frame 1, the whole
subject in the picture, one counter-intuitive idea (the barrier does not stop the car, it rolls it back onto the road), big plain
numbers. Comment hooks: "should every sharp curve have these?", Korean roads, guardrails that wreck cars.

One thread, 11 lines (36.8 s, 192 wpm, voice -6 %): why is this guardrail covered in spinning yellow rollers -> a rolling barrier
made in South Korea for dangerous curves -> a plain steel rail scrapes and drags at the car -> the rollers are barrels of tough foam
on steel posts -> they spin instead of scraping -> the foam squashes to soak up the hit -> the spinning turns part of the crash into
rotation -> so the car keeps rolling forward and is steered back toward its lane -> one version passed a 62 mph crash test for
American roads -> Korea already has more than sixty miles of them -> that's why some sharp curves are lined with spinning yellow
rollers (loops into line 1).

Frame 1 (hook rule): from above the barrier just ahead of the crash, the red sedan pressed into the rollers on a sharp mountain bend,
rollers squashed and spinning, the rails bowing; held through the first line.

Shots (12): A1 hero, B drone behind the car racing down to the bend, C the same crash into a plain steel W-beam (it bends back,
sparks), D a pair of rollers cut open (yellow skin, foam, steel sleeve on the shaft), E from above as the car slides in and the
rollers spin up, F straight down on the rollers as the foam squashes, G low behind: a row of rollers whirling, H1 alongside: the car
rolling on at speed, H2 high chase: back in the middle of its lane, I straight down like a crash-test camera: the whole crash, J
flying along another bend lined with rollers, K loop: the car coming down to the bend into frame 1.

Model benchmarks/roller_barrier/roller_motion.py (gate roller_physics: a 1,500 kg car at 100 km/h and 25 degrees, planar rigid body
against the barrier face; foam and posts give way with damping, a plain steel rail scrapes with sliding friction, rollers are spun up
by the car's side instead; the car keeps 88 % of its speed and leaves at -8.8 degrees on the rollers, 73 % on steel; 25 kJ into
the rollers' spin, 61 kJ into the foam, 196 kJ scraped off by steel; after the barrier the driver steers back to the lane and brakes,
for the picture only), layout roller_world.py (a mountain road matched to the model's frame: the car drives its lane down a straight
at 25 degrees and does not make a sharp left bend; gate world_layout), timeline roller_timeline.py, renderer render_roller_3d.py
(forested hillside, rock cut, valley, ridges, a curve warning sign; the barrier with every roller pair placed along the road edge, the
pairs the car can reach as their own meshes that spin, squash and give way; the steel W-beam for shot C; sparks; tyre marks; fast
rollers drawn smeared as a camera would), sound roller_sfx.py, assembly assemble_roller_film.py, CI .github/workflows/ep26-film.yml
(request examples/experiments/roller-film-request.json), tests tests/test_ep26_roller.py (incl. no camera inside the car, the
barrier, the trees or the ground).

## Audience data
(to be recorded at 48 h and 7 days)

## Preview
(local low-res run and CI to be recorded)
