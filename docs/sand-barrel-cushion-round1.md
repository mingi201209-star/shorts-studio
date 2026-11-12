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

---

# Round 2 (after reviewing the delivered cut)

Review notes on v1: collision physics (deceleration, barrel deformation and energy absorption) not clear enough; the translucent orange/green planes read as unexplained markers; captions should follow natural phrases. The opening collision was to stay.

| item | v1 | v2 |
|---|---|---|
| sha256 | `042c4275b35e1b0be25b71f59a36450076e8c494ee57aa38577ab1731eda1a11` | `722b353bdd4c53738eb4a46ffba7846822f994534fc71842a139e2867f269089` (matches `CUSHION_FILM_PASS`) |
| preflight | run 43208540621 | run 43229162635 PASS |
| render | run 43210308630 | production run 43230778727 (32 shards, free standard runner, assembled in the same run) |

Same-timestamp comparison (top v1, bottom v2, 12 timestamps): `docs/evidence/sand-barrel-v1-vs-v2.jpg`.

## What changed, and what backs it

1. Barrel deformation: each barrel is squashed (down to 45% of its length) while the simulated nose pushes into it and bursts at 0.45 m depth; sand launch time follows. Event `barrel_crushing` is gated in sentence 1.
2. Deceleration: a speed read-out taken from the simulation counts down on screen (90 km/h to 0). Wall case reaches 0 almost at once; array case falls over about six metres. It is a text object parented to the camera; event `speed_readout_visible` is gated in sentences 1, 3, 4, 5 (true by construction while shown, not an image measurement).
3. Orange/green planes removed. Two length bars from the first-contact line, labelled WALL 1 m and BARRELS 6 m, with matching stop lines on the ground. Event `distance_bars_visible` gated in sentence 5.
4. Captions: phrase-aware cues (`caption_phrases.py`, opt-in `grouper=` on the audio builder; shared `caption_groups` unchanged), each at most 24 characters so every cue stays on one line inside the safe rows. The first attempt used 31-character cues; two-line cues rose to row 1400 and `caption_safety` failed, so the limit was tightened rather than the gate relaxed.

## Gates on the real v2 video

Original QA PASS (visual_activity longest hold 3.0 s, black_opening, captions_visible), motion_plausibility PASS, narration_screen_match PASS (6 of 6), first_three_seconds PASS, caption_safety PASS.

## Still open

- Barrel deformation is a squash of a rigid barrel plus a burst, not material deformation; energy absorption is shown through speed falling and sand being thrown, not through a drawn energy graph.
- In the raised view the `WALL 1 m` label partly overlaps a line and can read as cut off.
- Audience-retention numbers (e.g. "continue watching" share) are not available to this session; nothing in this record depends on them.
- Process slip: editing the shared `curious_mechanics_audio.py` auto-started the old road-paint production workflow (its `paths` list that file); it was cancelled within minutes.
