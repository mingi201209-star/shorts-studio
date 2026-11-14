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

---

# Round 2 (review-driven)

Review of round 1 (77/100): first 3 s too calm, 10-22 s (cutaway + comparison) too static. Round 2 changes, no QA gate relaxed:

- Opening: truck starts closer (contact at ~0.4 s), spray and dust roughly doubled, a red "BRAKES FAILED" warning over the speed read-out for the first ~2.4 s.
- Cutaway: a wheel rolls across the slab, sinks in and throws stones ahead of it (replaces the static slice).
- Comparison: a second, orange truck (the same truck coasting on pavement at constant speed, an illustration) keeps running down the paved lane while the green truck stops.
- Two new telemetry events are required by the manifest (`wheel_rolling_visible`, `paved_truck_moving_visible`); `dust_cloud_thick` is counted as a later opening onset.

Evidence:
- Offline (local telemetry, 960 frames) predicted the telemetry gates; it also caught two real problems before CI: opening events clustering inside 0.3 s (first_three_seconds FAIL by 0.034 s; fixed by counting the later dust onset) and the warning text vanishing (z-fighting with its plate; fixed).
- Preflight run 43514943060 attempt 2: every gate PASS (attempt 1: three shards failed only at the Blender download, `curl: (22) ... 403`).
- Production run 43520329487 attempt 3: 32 shards, 1080x1920, 32 samples. 9 shard-attempts failed at the Blender download with the same 403 and were re-run; the production workflow now retries the download (`--retry-all-errors`). Final MP4 sha256 `2dc2795ffaf3231da8fc747b3962a7b2f3e63fbc45fe231fc34c2218add4e221` (decoded from the job log, re-hashed: identical), 960 frames, 30 fps, 32.0 s.
- Gates in the final run: visual_activity PASS (max static still 5.0 s, at the limit), black_opening PASS, captions_visible PASS, motion_plausibility PASS, narration_screen_match PASS, first_three_seconds PASS (onsets at 0.667, 0.767, 0.933, 2.367 s), caption_safety PASS.
- Comparison image: `docs/evidence/runaway-ramp-round1-vs-round2.jpg` (top round 1, bottom round 2, same timestamps).

Honest limits: the change is incremental (warning, closer start, rolling wheel); the truck is still primitives and the terrain flat. Human first-view and retention are UNVERIFIED. The 133 m / 3 km figures rest on assumed resistance coefficients. `upload_authorized: false`; production gates closed.
