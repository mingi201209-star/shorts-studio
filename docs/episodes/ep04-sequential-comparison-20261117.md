# EP.04 sequential comparison — approved direction (2026-11-17)

## Owner decision
Do **not** split the portrait screen into CRUMPLE above / RIGID below. Show the two full-screen **one after the other**, with the same camera, speed, barrier, visual scale, and a consistent impact reference. Focus on the physical event rather than explanatory text. Duration may grow only to show new meaningful physical action, never by holding a static frame or repeating footage pointlessly.

## Implementation scope (not yet implemented)
- Current code uses `crumple_motion.SEGMENTS` comparison IDs C/C2/C3 with `layout="stack"` and `panels=("crumple","rigid")`. Do not change only this field: the renderer, compositor, check_range, and safety gates assume stacked panels.
- Replace each stacked comparison beat with **two non-overlapping full-height beats**: first CRUMPLE then RIGID. Preserve one fixed comparison camera and identical framing for both. Label the currently visible car with a single small CRUMPLE or RIGID sign, never add title cards, arrows, bars or extra text.
- Rebuild the timeline against **actual fixed narration cue timestamps**. Narration must describe what is visible **during that beat**; if narration cannot be aligned without inventing restraint geometry, revise that sentence before any audio recapture. Do not falsely claim belts/airbags are visible.
- Ensure real simulated contact, folding and stop are shown on each beat, not merely the car in a different pose. If slowing motion for readability, state this as illustrative in video metadata.
- Update `render_crumple_3d.py` (render one full frame per frame), `assemble_crumple_preview.py` (full-frame composition), `check_range.py`, `crumple_motion.py` (segments and sync events), and all affected gate tests **together**.
- Keep existing physics, penetration, cabin integrity, audio timing, captions, text safe area, no-black-opening and scene-evidence thresholds. Update expectations only where the old split-screen assumption is inherently invalid, with regression tests proving the new full-frame behavior.
- No render or artifact upload until static/unit tests pass and the operator explicitly authorizes a bounded preview. No paid render, VPS render, main merge, or YouTube upload.
- First inspect latest main, open PRs and CI. If a change regresses established checks, revert the specific change before continuing.

## Suggested editorial rhythm (not final timestamps)
1. Full-screen CRUMPLE: approach, impact, front rails folding, cabin remaining intact.
2. Full-screen RIGID: same camera/speed, impact and shorter stopping stroke.
3. Full-screen X-ray: replay only the necessary physical detail while narration explains it.
4. Full-screen cabin view: nose deformed, safety cell intact.
No simultaneous top/bottom panels. Each comparison must remain understandable when muted; human playback remains NOT_VERIFIED until actually reviewed.

## Completion evidence
Static tests for no stack segments and no two-panel frame; full-height geometry and captions; fixed comparison camera/scale; timeline cue-to-action contract; unchanged physics. Actual playback evidence must be checked separately and must not be inferred from gate PASS.
