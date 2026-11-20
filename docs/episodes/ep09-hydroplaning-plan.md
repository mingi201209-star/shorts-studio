# EP.09: hydroplaning (owner: "make it interesting like other Shorts, packed with content")

- Pace: 13 dense lines at +15 % speaking rate, 147 words in 38.4 s (EP.08: 38.7 s for about 115 words); a new shot every 2-4 s.
- Opening: labelled split (NEW TREAD / WORN TREAD, SAME PUDDLE · 90 km/h · 32 psi) with live km/h and GRIP bars from the model; the worn
  car floats at 0.21 s of film time and runs wide off the bend.
- Facts with fact cards: tread depth (new about 8 mm, legal limit 1.6 mm), grooves as drains, the water wedge, the NASA rule of thumb
  (9 x sqrt(psi) mph; 32 psi -> about 51 mph / 82 km/h), the penny test, what to do when floating.
- Model: benchmarks/hydroplaning/hydro_motion.py (gate hydro_physics): single-track car, puddle on a bend, front grip collapses above an
  onset speed from the rule of thumb (lower for worn tread); same look-ahead driver in both cars.
- Scene: bending wet road, glossy puddle, spray from tyres in water, lab set (tread sections with grooves, sipes, wear bars; flowing and
  pooling water; wedge cutaway; plain coin), stylised driver whose wheel turns with the model's steering.
- Smoothness: lab close-ups froze in the first renders (140 -> 8 -> 5 frozen frames); fixed with water flowing through the grooves and a
  camera that tracks along them and never fully stops (checked locally before the CI render).
- Final run 44757477863 (frames from 44750915033): every gate PASS, 928 frames, 38.7 s.
- NOT verified: voice pronunciation at the faster rate, sound-off readability, human first view. The owner uploads.
