# Photorealism test: A / B / C on the wheel-entering-gravel stretch (frames 30-120)

Local Blender 5.0.1 Cycles CPU, 540x960, 24 samples, same frames and cameras. Not a production render; nothing uploaded.

| level | what changes | what the frames show |
|---|---|---|
| A | nothing (existing look) | box truck, smooth tyres, uniform tan stones |
| B | bevelled edges; tyre tread (lugs and grooves) with road dust; clear-coated, dirty cab paint; mottled trailer; stones mixed from dark to light with fine bump | tyres read as rubber with a tread, trailer and cab are no longer flat colour, stone sizes/tones vary. Bed colour and brightness kept as in A after a first B attempt turned the gravel cold and dark (lower-frame mean RGB within ~4 % of A now) |
| C | B plus a sprung body: cab/chassis pitch and heave follow a damped second-order response (1.6 Hz, damping 0.28) after the tyres bite | the stills differ from B by only 0.4 (frame 30) to 0.01 (frame 90) mean grey levels: the effect is a few tenths of a degree and only matters in motion; it has not been evaluated on a moving sequence yet |

Honest limits: the truck is still a box model, the stones are still spheres, the sky/sun are unchanged, no real asset or photo
texture is used, and nothing here is calibrated physics. B is better than A on materials, not "photoreal". C is unproven.

Run it: `--realism A|B|C` on `render_runaway_ramp.py` (default A, so existing manifests and CI render exactly as before).
Evidence: `docs/evidence/realism-A-vs-B-frames90-120.jpg` (left A, right B; frames 90 and 120).
