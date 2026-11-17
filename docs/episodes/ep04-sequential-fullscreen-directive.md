# EP.04 — Sequential full-screen collision comparison (owner decision, 2026-11-17)

## Binding production decision
Remove all stacked/split-screen comparison shots. Show exactly one vehicle at a time, full portrait frame, using the existing car mesh, crash physics and X-ray geometry. The old split comparison in segments C, C2, C3 is NOT an acceptable final presentation.

## Narrative-to-visual sequence
1. CRUMPLE, full screen: frontal collision, nose visibly compresses. Narration names the designed-to-crush front.
2. X-ray, full screen: show internal crush rails actually folding, large enough to distinguish in motion.
3. RIGID, full screen: replay the same initial speed, mass and barrier with short stopping stroke. Narration describes the rigid stop **during** this shot.
4. CRUMPLE, full screen: replay to make longer deformation/stopping interval perceptible; use matched framing and time scales where claiming a comparison.
5. Intact cabin, full screen: hold deformed front and unchanged safety cell in the same view as the narration names them.
6. Closing exterior/X-ray: no new text.

The difference in average force cannot be directly *seen* from crush depth alone. Avoid presenting a visual proof of force unless a grounded comparison is added; alternatively revise the voiceover to explain only the visibly demonstrated distance/time difference. Do not silently retain narration about seat belts/airbags unless those systems are visibly demonstrated or the line is rewritten to match what is shown.

## Technical implementation constraints
- Rework `benchmarks/crumple_zone/crumple_motion.py` segment timeline and speech cue mapping together; no simple switch from `stack` to `full` with two panels because the assembler would overlay cars.
- Every full-screen segment has exactly one panel: `("crumple",)` or `("rigid",)`.
- Recheck `render_crumple_3d.py` camera, label visibility, `PANEL_ROWS`, and `assemble_crumple_preview.py` placement. Recheck semantic gates that currently assume simultaneous comparison.
- Keep source audio immutable until replacement timing is approved; a new narration take needs an explicit plan for synchronization, and should not be represented as existing audio PASS.
- No split-screen, extra explanatory text, bars, arrows or occupant added.
- Do not pad duration with frozen frames; extend only where each shot conveys a new physical step.
- Existing tests/gates must not be weakened to force a PASS. If a gate assumes stacked comparison, update its specification and regression tests to check sequential equivalence, with evidence.
- No new render or artifact until the plan/code has passed static tests and explicit render authorization.

## Status
This file records the approved creative direction. It does **not** claim the renderer, narration, CI or final video has been changed or validated.
