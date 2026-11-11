# Jersey barrier episode - quality round 2

Branch `road-paint-retroreflective-20261106`. No PR, nothing merged to `main`, nothing uploaded.

## Result

| item | value |
|---|---|
| v2 (previous) sha256 | `3a35aadca37257c88a040c093cd8733189e8c9d1708b80f11b32c63239e23b3e` |
| v3 (this round) sha256 | `2aa07569d31257cb4b3a785a3d84a181879c1db55ca7dc2a5568ac4731db3b47` |
| v3 format | 1080x1920, h264 + aac, 32.000 s |
| render | production run 43027922317 (32 shards x 30 frames, 32 samples, free standard runner) |
| assembly | run 43112905031 (assemble-only, reuses the rendered shards) |
| preflight (low-res, full length) | run 43026151363 PASS |

Same-timestamp comparison (top row v2, bottom row v3, t = 0.4 1.0 1.8 2.6 6 10 14 17 21 26 s):
`docs/evidence/jersey-barrier-v2-vs-v3.jpg`

## Gates on the full-resolution v3 (real video)

- Original QA: visual_activity PASS, black_opening PASS, captions_visible PASS (plus silence/loudness/duplicate/black-frame checks inside the film QA, unchanged).
- motion_plausibility PASS, narration_screen_match PASS (6 of 6 sentences), first_three_seconds PASS, caption_safety PASS.
- The black caption band (rows 1400+) is intentional and was kept; captions sit in rows 1408-1540.

## Per axis

1. Physical motion: car motion now comes from a small simulation (`jersey_barrier_motion.py`), not keyframes. Tyre rides up the 55 degree lower face, suspension compresses, body does not touch. Simulated numbers (4 deg, 12 m/s): first tyre contact 0.36 s, wheel lift 12.8 cm, suspension compression 5.9 cm, minimum body gap 7 cm, steered back to lane. Flat wall: body takes the hit, no lift.
2. Narration vs picture: each sentence has a required on-screen event, checked against per-frame telemetry during that sentence's real spoken window.
3. First 3 s: tyre on slope ~0.57 s, body lifted ~0.9 s, steered away ~2.53 s (distinct events, not camera moves).
4. Captions: no overlap, no clipping, no cue under 0.25 s.
5. Audio: en-US-AndrewNeural +5%, silence and loudness gates passed.

## Limits (not hidden)

- The model is a simplified single-track plus quarter-car simulation, not a validated crash simulation. Numbers are plausible, not measured.
- Suspension travel is only about 6 cm, so it is subtle on screen.
- The gates check simulation state and geometric visibility (ray cast, pixel size), not image understanding. A person still has to look.
- The semi-transparent body in the macro shot is a cutaway device, stated as such.
- The 20:34 UTC runs 43096850044, 43096850061, 43096850035 stayed `queued` and GitHub refused cancel and force-cancel (409). They are stale; the work was re-run as 43112905031/2/11.

## Safety record

No open PR for this branch, no conflicting unattended run, no STOP file, no `main.py` or `create_scene` change in this branch. Production `native`/`final` gates are closed again (`if: false`).

## Next

- Human review of v3 against the five axes; decide on upload (not done).
- Optional: longer suspension travel if a real source supports it; second camera angle at the contact point.
