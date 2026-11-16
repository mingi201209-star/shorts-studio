# EP.03 speed bumps: planning check (nothing rendered, nothing uploaded)

## Real-world shapes (secondary sources; check ITE primary documents before any "design" claim)
- Speed hump: about 3-4 in (7.5-10 cm) high, about 12 ft (3.7 m) long, parabolic, design speed about 15-20 mph. Source: FHWA traffic-calming ePrimer, Univ. of Kentucky safe-design page.
- Speed table: flat-topped, about 22 ft (6.7 m) long (a car's wheelbase fits on top), higher design speed (about 25-30 mph). Source: Sacramento County NTMP.
- Sources disagree on table height (3-4 in vs 6-8 in) and ramp lengths. The film must say "typical", never "standard".
- Also real: short rubber/portable bumps (about 5 cm high, well under 1 m long), often harsher at the same speed.

## Same-condition comparison is possible (quarter-car model, `benchmarks/speed_bump/quarter_car_check.py`)
Assumed typical car values (400 kg sprung, 40 kg unsprung, 22 kN/m spring, 1.5 kNs/m damper, 200 kN/m tyre), NOT calibrated to a real car. Same 7.5 cm height, same car:

| speed | short 0.9 m | hump 3.7 m | table 6.7 m |
|---|---|---|---|
| 15 km/h | 0.69 g | 0.26 g | 0.23 g |
| 20 km/h | 0.81 g | 0.33 g | 0.24 g |
| 30 km/h | 1.08 g | 0.52 g | 0.36 g |
(peak body vertical acceleration)

Reading: at equal height and speed, the shorter the ramp the harder the body is pushed (about 3x between 0.9 m and 3.7 m). Direction matches the planned story ("how quickly the road lifts the car"). Hump vs table differs much less than short vs long.
Caution: body rise comes out above the bump height (about 10 cm for 7.5 cm) because the assumed damping is light; the film must not show the body rising more than a physically plausible amount, and no acceleration number should appear as a real-car measurement.

## Consequences for the plan
1. Compare **short rubber bump vs a 3.7 m hump** (or hump vs table) at the same height, speed and car; do not claim "round vs flat" is the cause, the length is.
2. On-screen numbers only as "SIMULATION, ASSUMED CAR"; no "safe speed" claims.
3. Hook frame must show two wheel paths in the first 3 s (same car, same speed), reusing the opening-camera and callout machinery from the ramp film.
4. Reuse list from the ramp film: shard renderer + proof/assembler, derived callouts, caption/QA gates, contact-sheet check. New: car + suspension model, bump geometry, wheel-path overlay.

## Next steps (waiting for owner choice)
Low-res preview of both passes (4-6 frames/s, small res) -> scene QA -> parallel full render on free runners -> edit -> final QA -> owner approval. No upload by the agent.

## Preview log (2026-11-15) and required gates
| preview | layout | pixel gate result | verdict |
|---|---|---|---|
| run 1 | side view, both lanes | not measured | scene a thin band, white sky: FAIL (looked at) |
| run 2 | chase from behind, high | not measured | cars small, no body motion visible: FAIL |
| run 3 | chase from behind, low | cars fill 10.8 % of height (need >= 22 %), body motion not visible | FAIL: full render on hold |
| run 5 | split: one side camera per car, stacked (primitive car) | cars 24 % of panel height (width fully used); body motion hump 1.9 % ok, short 0.9 % (< 1.2 %); bump mask failed on the hump panel (looked at: bump IS visible, pale yellow, gate colour threshold needs calibration) | composition better, pitch visible on the hump at 1:1, car looks like a toy -> upgrade the car model first |
| run 6 | split, pinned CC0 sedan (same car posed from both sims) | not run (gate colour thresholds still to be calibrated for the grey car) | looked at: car reads as a real sedan, hump pitch visible at 1:1, short bump = wheel jolt with almost no body motion (model result), bump shapes readable. Candidate for the full render; open items below |

Evaluation department, new mandatory checks for this episode (`benchmarks/speed_bump/preview_gates.py`): both cars and both bump shapes visible in the first frame, cars fill >= 22 % of the panel height, body motion visible, bump shapes differ on screen (objective, pixels); question text within 1 s, a visible difference within 3 s, narration hook within 0.5 s (UNVERIFIED until a person confirms on the real video).
Not allowed to be exaggerated: the body motion must be drawn 1:1 with the model (no vertical scaling). If it is too small to see at 1:1, the scene must get closer (wheel arch close-up) or add a true-scale reference graph, never a magnified body.

## Open items before a full render (from run 6)
1. Cars travel toward screen-left; put the camera on the other side so travel is left to right.
2. Panels at 1080x720 (not 1080x960) so the lower band carries a true-scale suspension/body-height trace and captions.
3. Sky is nearly white at the horizon; lower exposure or a slightly deeper sky.
4. Hook: question text in the first second ("SAME CAR. SAME SPEED."), narration revised to "short bump = sharp jolt, long hump = slow rise and tilt" (not "gentler"), assumptions line ("simulation, assumed car").
5. Calibrate the pixel gates for the grey sedan; add speech plan, manifest, assembler and QA gates for this episode.
6. Voice and first-3-seconds items stay UNVERIFIED until the owner confirms.

## Final film (2026-11-15): 100 % 3D, no text/graphs; production run 43691317419
- Picture = CC0 sedan + two bumps + road + sky, five cameras (rear 3/4, side, wheel close-up, front 3/4, top); layouts hump-left/short-right or hump-top/short-bottom. Only the burned-in captions of the narration are 2D.
- Full-res final `speed-bump-shapes.mp4` sha256 `79e3d759b2cb133094f3435ae6551461f99c018b67a8f49f44e481a96b9cae09` (960 frames, 1080x1920, 32 s); 540x960 review copy `8e24d9ae…582d` recovered through job logs, every chunk hash and the whole-file hash matched.
- Gates PASS: narration numbers vs simulation (2.2x / 2.1x / 5.5x), narration-picture timing (spoken starts 0, 4.55, 9.66, 14.96, 20.45, 26.32 s), first 3 s (first contact 1.01 s), captions single-line in the safe area, visual activity (cuts every 2.5-3.5 s), black opening, duplicate frames, assumed values spoken, all-3D/no overlays, loudness -16.5 LUFS.
- NOT verified: voice pronunciation and sync (a person must listen), human first view, whether the short-vs-long difference reads without any on-screen text. Weak spots: car small in the rear/front 3/4 shots; the bump/car identification relies on the narration. Simulation values are assumed (not calibrated).

## v2 (X-ray) production result — run 43703551974

- All gates PASS on the real encoded video: original QA (13 cuts, average 2.46 s, longest static 4.0 s), content QA (ratios 2.2 / 2.1 / 5.5; picture timing; first contact 1.48 s; caption rows 1447-1498; assumptions declared; all 3D, no overlays), loudness -16.4 LUFS.
- Film sha256 `ed2c52761ac23fe6572a2b60774a2a1d59fea97e542c92a78a10492853f76a17`; review MP4 (540x960) sha256 `d08d42694f9946e86a6cb58419e7d2245ccc5d302c6a186f0395376c13301f34` recovered through job logs and hash-verified; no black frames or silence gaps in the review copy.
- Fallback v1 film kept: `79e3d759b2cb133094f3435ae6551461f99c018b67a8f49f44e481a96b9cae09`.
- UNVERIFIED: voice pronunciation/sync, human first view, whether the X-ray reveal reads well, noise in translucent frames. Not uploaded.

## v3 (explain) production result — run 43716546602

Owner feedback on v2 (X-ray): scenes repeat and the picture stutters like lag; asked to remove repeats and add new scenes explaining the principle.

- Cause of the stutter: the simulation pose was sampled at 30 Hz and held for ~4 frames under slow motion (motion only every 4th frame). Fix: pose sampled at 600 Hz (`RENDER_HZ`). Measured on the recovered videos: v2 consecutive-frame diff pattern 0.0 0.0 0.1 1.1 (burst every 4th frame); v3 continuous 0.3-0.4 every frame (share of frames with motion >0.3: 0.35 -> 0.65).
- Repeats removed: five passes of the same bump became A, P, B, C, E with different cameras (rear3q, wheel, front3q, profile, side, tyre, top, high3q); new principle scene: the front wheel hub path drawn as a 3D tube (short bump = steep rise, long hump = gentle), no graphs, no text plates.
- Narration rewritten as six single-sentence beats (total-silence gate), 36.5 s, 1095 frames; spoken starts [0, 4.59, 10.62, 16.8, 24.13, 29.27] s.
- Gate history (none relaxed): static 7.0 s in the wheel shot -> shot split with a new camera; total silence 6 s -> fewer sentence pauses; shard range fixed to 1095 frames.
- Final gates PASS: visual activity (19 cuts, avg 1.92 s, max static 3.5 s), narration numbers (2.2 / 2.1 / 5.5), picture timing, first three seconds (first contact 1.48 s), caption safety, assumptions declared, all 3D / no overlays, loudness -16.4 LUFS.
- Film sha256 `8ca41a1c26db07f61ec2d281e44cb79f2c5c4425af8f181e4a1fb04cb55fc598`; review MP4 sha256 `a406426e49f4ae36a8b366eefbb17068b9944f04d79febf8361fd7e90667c47c` (recovered from job logs, chunk and whole-file hashes verified; no black frames, no silence gaps).
- Fallbacks kept: v2 X-ray `ed2c52761ac23fe6572a2b60774a2a1d59fea97e542c92a78a10492853f76a17`, v1 `79e3d759b2cb133094f3435ae6551461f99c018b67a8f49f44e481a96b9cae09`.
- UNVERIFIED: voice pronunciation and sync, human first view, whether the hub-path trail reads well on a phone. Not uploaded.

## v4 (reveal) production result — run 43776644423

Owner feedback on v3 (explain), from 12 extracted frames: weak first 3 s (two cars side by side give no reason to watch), X-ray not dramatic enough, suspension difference between the bumps not clear enough, black band at the bottom too big (captions look detached from the picture).

Changes:
- First 3 s: low front 3/4 camera, both cars big (long hump on top, short bump below), first contact 1.48 s; hook narration "These two bumps are exactly the same height so why does one hit so much harder."
- X-ray: scan-line reveal sweeping front to rear (world-space plane, glowing edge), 88-118 frames (about 3.0-4.0 s), then a tight spring/damper close-up; springs glow hotter with compression.
- Full-height 1080x1920 picture, captions on the picture (black outline + shadow, rows 1441-1506, above the Shorts overlay); no black band.
- Wide shots moved from the tall 540x1920 layout to the 1080x960 stack layout (the tall panel left two thirds empty); lens shift for the remaining tall shots.
- 35.0 s / 1050 frames: a 36.5 s target added slack = silence and broke the total-silence gate (5.45 s > 5 s); 35.0 s passes. Gates not relaxed.
- Caption measurement: the "bright pixels in the band" check assumed a black band; with captions on the picture it counted sky and glow. Now measured against the caption-free composed frame, same frame number (same two requirements: caption pixels exist in the band, none at the bottom edge).

Final gates PASS: visual activity (22 cuts, avg 1.59 s, max static 3.5 s, 3 changes in the first 5 s), narration numbers 2.2 / 2.1 / 5.5, picture timing (starts 0, 4.47, 10.51, 16.71, 24.05, 29.21 s), first three seconds, caption safety (rows 1441-1506), assumptions declared, all 3D / no overlays, loudness -16.2 LUFS. Recovered review MP4: no black frames, no silence gaps; per-frame motion median 0.68 (v3 0.40), the reveal frames show per-frame diff 4-5 against a 0.6 baseline.

- Film sha256 `4a95b721420615eadb30b85350a552f76612e7420897c27e4e68fd81fbb12b36`; review MP4 sha256 `1f1eda775aca1a1e889ce1ad91cd26887dd2f5a9fecdbb1afdc26cbc6e639113` (chunk and whole-file hashes verified).
- Fallbacks kept: v3 explain `8ca41a1c26db07f61ec2d281e44cb79f2c5c4425af8f181e4a1fb04cb55fc598`, v2 X-ray `ed2c5276…`, v1 `79e3d759…`.
- UNVERIFIED: voice pronunciation and sync, human first view (curiosity in the first 3 s), whether the reveal reads as dramatic on a phone, whether the spring difference between the two bumps is clear enough in continuous playback. Not uploaded.

## Final cut (v5, 31.0 s, 930 frames) - owner request "final quality pass"

Baseline: reveal v4 (film 4a95b721…, review 1f1eda77…). The file 1000020413.mp4 could not be opened in this session.

What changed
- One condition for both bumps: same car, 20 km/h, same suspension, same 7.5 cm height; only length differs (0.9 m vs 3.7 m).
- Narration claims are rate based and checked by a gate: hub lift 4.06x, spring squeeze 2.39x, body jolt 2.38x (single-speed variant of `narration_numbers`).
- New gate `picture_events_match_cues`: each structure appears when its words are spoken (6 cues, delta 0.0 s).
- Six single-sentence narration beats, 31.0 s. The simulation disclosure is in `examples/experiments/speed-bump-description.txt` (posted description), not in the voice.
- Captions burned over the picture (no black band); caption safety rows 1408-1540.
- Shot list has no repeated camera back to back; longest static 3.0 s; average cut 1.4 s.

Evidence (run 43823830373, production, head 36adb83)
- All 10 QA gates PASS: visual_activity, black_opening, captions_visible, narration_numbers, narration_picture_timing, picture_events_match_cues, first_three_seconds, caption_safety, assumptions_declared, all_3d_no_overlays.
- Loudness -16.3 LUFS; no silence over 0.9 s; no black frames.
- Film sha256 2ba58ef424a7649bbf8a2f70c39ae0b72406c0b12569bd7b9b037adc0c05705c; review 91b10d3c637c570313715a8393b1828b70bf805b0c178918e6ab1cf82315af80 (recovered by run 43837853072, whole-file sha verified).
- Smoothness (mean gray frame diff): median 0.607 as reveal, frozen frames 0 vs 33 in reveal.

History: a shard-range slip (1051/960 left over from the reveal copy) was caught and fixed before production; audio gates failed twice on length and were fixed by shortening, never relaxed.

UNVERIFIED: voice pronunciation and sync were not heard; human first view; phone readability; spring heat legibility; tyre contact at full resolution.

## Final cut v2 (v6, 31.0 s, 930 frames) - owner review of 1000020414.mp4 (6 more problems, merged with the first 4)

Plan: `docs/ep03/speed-bump-final-v2-fix-plan.md`. Revert point to v5: commit 7fb7781 (film sha 2ba58ef4…).

Changes
- Impact at 0.63 s (first pass lead 0.7 m). A second pass (frames 142-322, lead 2.2 m) puts the front wheel on the bump exactly as the spring close-up starts: in v5 both bumps were already behind the car when the spring was explained.
- X-ray shots look down onto asphalt; brighter body rim; sky share median 0.20 (v5: 0.44-0.65).
- Camera list: no two neighbouring shots share a camera; new views: left side (body heave), raised side (spring rest-length ruler, body rest tick, red peak tick), closing replay with hub + body trails.
- 3D LONG / SHORT signs beside the bumps (long on top in every shot); hidden in the wheel/spring close-ups.
- Drawn wheel follows the rigid tyre envelope within 4 mm (v5 drew the wheel up to 17 mm above and 21 mm into the short bump because the simulated tyre compliance was drawn as rigid motion). The simulated 21 mm tyre flex is not drawn; the description says so.

Evidence (production run 43859190581, head c690615; all 14 gates PASS)
- first_impact_within_1s 0.63 s; tyre_road_contact 4.0 mm (rendered telemetry 4.0 mm); suspension_timing: spring squeeze peaks 5 film frames after the wheel lift and returns to rest; xray_readability 0.20; spring_tracks_simulation r=0.997 (long) / 1.0 (short), 25 / 52 px change, spring pixels found in 100 % of frames; signs_visible 419 frames with both signs, pixels found in every sampled frame; shots_are_distinct; plus every earlier gate (narration numbers 4.06 / 2.39 / 2.38, cue sync, captions, loudness).
- Film sha256 0581d5dfd359b5bff2e8e364263978c110a2cb0b5709a9c45b9654e8d22b5b71; review 540x960 fe5516db297f0148d23f5e36af250e1871aba3fbed3f2627750ac4458941c887 (recovered by run 43872947943, whole-file sha verified).
- Smoothness (mean gray frame diff): median 0.819 (v5 0.607), frozen frames 0, no silence over 0.9 s.
- Preflight history: 4 low-resolution preflights; failures were sign size and visibility (one sign hidden behind the car), a spring-length gate that measured the yellow bump paint, and a sky-share measure on a cropped panel. Thresholds set blind were changed only after reading rendered frames; the pass criteria themselves were not relaxed.

UNVERIFIED: English TTS pronunciation/naturalness and sync as heard; human first view; phone readability; tyre contact at full resolution seen by a person; the signs are cut at the picture edge in some wide frames; spring colour change legibility.
