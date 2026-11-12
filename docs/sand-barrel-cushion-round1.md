# Sand-barrel crash cushion episode (topic 3 of the road-safety lane)

Branch `road-paint-retroreflective-20261106`. No PR, nothing merged to `main`, nothing uploaded (`upload_authorized: false`).

## Result

| item | value |
|---|---|
| video | `sand-barrel-cushion.mp4`, 1080x1920, h264 + aac, 32.000 s |
| sha256 | `042c4275b35e1b0be25b71f59a36450076e8c494ee57aa38577ab1731eda1a11` (matches `CUSHION_FILM_PASS`) |
| preflight (low-res, full length) | run 43208540621 PASS |
| render | production run 43210308630: 32 shards x 30 frames, 32 samples, free standard runner |
| assembly + gates | assemble-only run 43222045615 (the production `final` job died on a truncated shell block of mine; fixed, shards reused) |

Frames at 22 timestamps from the real 1080x1920 video: `docs/evidence/sand-barrel-cushion-frames.jpg`.

## Gates on the real video

- Original QA: visual_activity PASS (longest hold 4.0 s), black_opening PASS, captions_visible PASS, plus silence/loudness/duplicate/black-frame checks inside the film QA, unchanged.
- motion_plausibility PASS, narration_screen_match PASS (6 of 6 sentences), first_three_seconds PASS (first barrel bursts at 0.43 s, nose dive at 1.23 s), caption_safety PASS.
- Caption band (rows 1400+) kept as designed; no safe-area rule relaxed.

## What the film claims, and what backs each claim

1. Barrels burst on contact: every barrel hides and launches its sand the frame the simulated nose reaches it.
2. A barrel is a thin plastic shell packed with sand: one barrel drawn cut open (cutaway device).
3. Sand has to be sped up and the car pays for it: sand grains leave at 0.92-1.12 x the car's speed at that instant (momentum accounting, force = sand mass per metre x speed^2).
4. Back barrels hold more sand: rows of 90 to 640 kg per barrel; translucent shells show the levels (cutaway device); mean deceleration first third 4.7 g, middle third 7.0 g, peak 10.3 g at 4.75 m.
5. Wall about 1 m, barrels about 6 m: same car, same 25 m/s; wall stop 0.89 m (assumed crush 0.9 m, 35 g), array stop 6.3 m. Orange/green planes are reference markers, not objects.
6. Used in front of hard concrete ends: intact array in front of a striped concrete end, car passing in the next lane.

## Limits (not hidden)

- Not a validated crash simulation. Rigid car, no body crush drawn; sand mass, shell force, crush distance and pitch stiffness are generic assumptions, so numbers are plausible, not measured.
- Real arrays hit off-centre and at angles; this is a head-on centred hit only.
- Gates check simulation state and geometric visibility (ray cast, pixel size), not image understanding. A person still has to look.
- Visibility pixel floors were lowered for three events only (25-30 px per 30 cm for metre-scale subjects seen from above or far away; 12 px for the closing wide shot). These floors are new in this episode; no shared QA threshold was changed.
- The sedan's wing mirror reads oddly in the close shot (low camera, window out of frame).

## Safety record

No open PR for this branch, no conflicting unattended run, no STOP file, `main.py` and `create_scene` untouched. Production `native`/`final` gates are closed again (`if: false`).
Stale runs from earlier work (43096850044, 43096850061, 43096850035) were queued and refused cancel; they are unrelated to this video.
CI hygiene fixed along the way: `test` and `render-smoke` had failed since the first cushion commit (`ModuleNotFoundError: benchmarks`); tests now add the repo root to `sys.path`. Latest `test` and `render-smoke` are green.

## Next

- Human review of the video; upload decision (not done).
- Optional: off-centre / angled hit; a measured source for sand mass and crush distance; fix the mirror in the close shot.
