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

## Production render, realism B (run 43583071422, commit 504f1fe, 1080x1920, 30 fps, 32 s)
All 35 jobs succeeded. Every QA gate PASS (visual_activity: average beat 0.97 s, longest static 2.5 s, 7 changes in the first 5 s;
black_opening, captions_visible, motion_plausibility, narration_screen_match, first_three_seconds, caption_safety).
MP4 recovered from the final-job log and **verified**: SHA-256 `2360a2f8426eba57083a2dbb8062eb975aff3ede703003d32e9bfcea3689251f`
equals the hash the run reported (`RAMP_FILM_PASS`); h264 1080x1920 30 fps 32.0 s + aac. Frames reviewed: `docs/evidence/runaway-ramp-round4-realismB-contact-sheet.jpg`.

Motion profile (`motion_profile.py`, picture rows, 15 fps):

| | median frame change | share < 4 | registered beats | longest without a beat |
|---|---|---|---|---|
| round 3 (A) | 5.36 | 0.39 | 31 | 5.0 s |
| round 4 (B) | 6.54 | 0.31 | 37 | 2.0 s |
| reference clip (earlier measurement) | 14.7 | - | - | - |

Still true: stylised box truck, sphere stones, assumed (not calibrated) coefficients; far below the reference's motion; no viewer
test; audio pronunciation/noise/sync not verified. Callouts "25x MORE DRAG" (resistance ratio) and "24x FARTHER" (distance ratio) are
different quantities but read as inconsistent. Not uploaded, not merged, no PR. Production gates are open and should be closed again
(`if: false`) unless another run is wanted.

## Captions + continuous opening camera (branch road-ramp-captions-camera-20261114, preflight run 43610425893, commit e30a14c)
Changes: callouts computed from the model ("25x MORE DRAG THAN PAVEMENT" = ratio of the assumed coefficients 0.25/0.01; "PAVEMENT GOES 24x FARTHER" =
3,184 m / 133 m, smaller than 25 because the bed's resistance ramps in over 12 m and the tyres sink; the pavement distance matches the closed-form
v^2/(2 c g) within 1 %); frames 1-285 are one continuous truck-anchored camera move (ramp_camera.py, audited: no hold, subject visible 100 %,
max acceleration 103 m/s^2 <= 120) with a smooth playback-rate ease instead of a hard step and a continuous nose track through first tyre contact.
Offline gates before CI: narration_screen_match and first_three_seconds PASS. CI preflight (360x640, free runner, all 10 jobs green): every gate PASS
(visual_activity, black_opening, captions_visible, motion_plausibility, narration_screen_match, first_three_seconds, caption_safety).

| | previous B preflight | now |
|---|---|---|
| average beat | 0.97 s | 0.84 s |
| changes in the first 5 s | 7 | 9 |
| longest static stretch | 2.5 s | 2.5 s (unchanged, now elsewhere in the film) |

Not done / not verified: no full-resolution render of this version, no side-by-side with the 2360a2f8 film yet, audio pronunciation / noise / sync not
verified (only the existing loudness and silence gates), nothing about viewer quality. Preflight only: deliverable false, upload not authorised.
