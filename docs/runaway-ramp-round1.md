# Runaway truck ramp (gravel arrester bed) — round 1

Status: **rendered and QA-passed on free GitHub runners; HOLD for human review; not uploaded; not merged to main.**

## What the film claims (and only this)
A 20,000 kg truck with failed brakes enters a level gravel bed at 90 km/h. Its tyres sink and push stones aside; rolling resistance stops it in about 133 m, where the same truck coasting on pavement would take about 3,184 m.

## Assumptions (not verified)
- Rolling-resistance coefficients 0.25 (loose gravel) and 0.01 (pavement) are **assumed**. 0.25 is the illustrative value in a published worked example (Design News, "The case of the chicken brake"); Arizona DOT's review of arrester beds says field tests are still needed to predict minimum values. The film labels them "assumed".
- Tyre sink 0.16 m, bed depth 0.6 m are drawn values, labelled "drawn".
- The truck is built from primitives and is not deformed. Stones and dust are ballistic bookkeeping for the picture, not a granular-flow simulation. `physically_calibrated` is False everywhere.

## Evidence
- Motion model: `benchmarks/road_safety/runaway_ramp_motion.py` (energy audit ratio 0.996; 10 unit tests in `tests/test_runaway_ramp.py`).
- Preflight (full length, 360x640, every gate): run 43452812617 attempt 2 — all gates PASS. Attempt 1 failed only because the report job hit a GitHub artifact egress limit (HTTP 503) before any gate ran; the failed job was re-run.
- First preflight (run 43447578677) failed visual_activity (6.0 s static), caption_safety (two-line captions), narration_screen_match (event points outside the frame, shot boundaries) — fixed in the film, no gate was relaxed.
- Production: run 43458903344, 32 shards x 30 frames, 1080x1920, 32 Cycles samples, cinematic look. Final MP4 sha256 `02e93936fcf334d730894840c783c1d4ba8f58e408e517c66185b8de73e5d9ee` (decoded from the job log and re-hashed: identical), 960 frames, 30 fps, 32.0 s.
- Gates in the final run: visual_activity PASS (max static 5.0 s — at the limit, no margin), black_opening PASS, captions_visible PASS, motion_plausibility PASS, narration_screen_match PASS (gravel_spray 0.867 s vs 0.8 s needed — thin), first_three_seconds PASS, caption_safety PASS.
- Frames: `docs/evidence/runaway-ramp-final-frames.jpg` (from the real MP4), `docs/evidence/runaway-ramp-preflight-sheet.jpg`.

## Known weaknesses
- Visual quality is a stylised explainer, not studio-grade: primitive truck, flat terrain, no recorded foley or HDRI.
- The top-down comparison shot's labels are small.
- content match is simulation-state telemetry, not image understanding. Human first-view is UNVERIFIED. Retention effects are unverified.

## Open items
`upload_authorized: false`. Production gates (`native`, `final`) in `.github/workflows/runaway-ramp-production.yml` are re-closed (`if: false`).
