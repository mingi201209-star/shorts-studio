# EP.07: ESC (electronic stability control), follow-up to EP.06 ABS

## Why this topic
- Opening readable in the first second: the same swerve on a wet road; the bottom car (no ESC) turns past 45 degrees at 0.5 s of film
  time and spins, the top car (ESC) stays within 12 degrees. (EP.05 lesson: the crash or slide itself must be visible in frame one.)
- Detailed hardware (owner: keep the parts detailed): yaw-rate sensor with a glass lid and tuning-fork element, steering-angle sensor
  (slotted code disc, optical reader) on the column, hydraulic unit (valve block, 12 valve caps, pump motor, ECU cover, brake lines),
  and EP.06's brake mirrored to the outside front wheel. X-ray shots keep the car body as a faint glass shell.
- Series link: same car, road and brake as EP.06; "the same valve block and pump as your ABS".

## Model (benchmarks/esc_stability/esc_motion.py, gate `esc_physics`)
Single-track car with saturating tyres on a wet road (rear grip slightly lower), the same swerve for both drivers. Without ESC the rear
saturates and the car spins (130 deg); ESC compares the yaw rate with the steering-based reference and brakes the outside front wheel
(the gate checks it is always the outside one); the ESC car stays within 15 deg. Not calibrated to a real car.

## Result (2026-11-19)
- Narration 13 lines, 42.3 s, all audio gates PASS.
- Whole-film preview: frames rendered in run 44524920519; assembled in run 44537462643: every gate PASS (esc_physics, scene_alignment,
  telemetry_matches_model, visible_action, no_scene_text, loop_closes, smoothness, black_opening, captions_visible). 1021 frames, 42.5 s.
- Loop gate: at 80 km/h under a following camera neighbouring frames already differ by about 6-7 (mean gray), so the seam is now compared
  with the steps right next to it instead of a fixed 6.0 (seam 6.95 vs neighbours 6.14 / 6.80).
- NOT verified: voice pronunciation, sound-off readability, human first view. The owner uploads.
