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

## Static top-down comparison (frames 605-793), level B/C only
At level A the camera holds a high top-down view for ~3 s. At B/C one continuous move eases from that view down into an oblique
chase of the pavement truck. Local 360x640, every 8th frame, shared visual-activity rule (cropped to the picture rows):

| | registered beats in the shot | longest stretch without one | median change between samples |
|---|---|---|---|
| A (old) | 2 | 5.07 s | 0.24 |
| B (continuous move, first half only) | 7 | 3.47 s | 2.49 |
| B (also the opening of the shot rises from oblique to top-down) | 10 | 1.60 s | - |

Local measurement only; the manifest now carries `"realism": "B"` (the renderer reads it when `--realism` is not given), so the CI preflight renders level B and runs all gates.

## CI preflight with realism B (run 43575903085, commit bd3c095, 360x640, free runner)
All gates PASS: visual_activity (average beat 0.97 s, **longest static stretch 2.5 s, previously 5.0 s**, 7 changes in the first 5 s),
black_opening, captions_visible, motion_plausibility, narration_screen_match, first_three_seconds, caption_safety.
Report: `RAMP_PREFLIGHT_REPORT status PASS`, preflight only (`deliverable: false`, `upload_authorized: false`).
Not yet done: a full-resolution production render at level B (production workflow `native`/`final` stay closed), and a viewer-level
judgement of the realism. Level C is not enabled in the manifest.
