# Runaway truck ramp: upload readiness (draft, nothing is published; `upload_authorized` stays false until the owner says otherwise)

Decision recorded 2026-11-15: this film is the **candidate for the second upload**. The film is published only after (1) the final 32 s cut is rendered and
checked, (2) the owner approves it, (3) the owner posts it. No agent action uploads anything.

## Gate list (a gate that is not PASS blocks the upload; "not verified" is not PASS)

| # | Gate | What counts as PASS | Status now |
|---|---|---|---|
| 1 | Full 32 s final render | 960 frames, 1080x1920, 30 fps, native QA green, MP4 recovered and its SHA-256 equals the runner's | **open** - last full render is the realism-B film `2360a2f8...` (old camera, old callouts); the round-3 opening and the new callout texts are not in a full cut yet |
| 2 | Narration matches the picture | `narration_screen_match` + `first_three_seconds` PASS on the final, plus a human look at the six sentences against the frames | gates PASS on the current code (offline and CI preflight); final cut not yet checked |
| 3 | No clipped captions, no black frames | `caption_safety`, `captions_visible`, `black_opening`, blackdetect clean on the final MP4 | PASS on the old final; re-check on the new final |
| 4 | Voice: pronunciation, noise, sync | loudness/silence gates PASS **and** a person listens once | gates PASS on the old final; **pronunciation and sync are not verified** (the voice is a neural TTS; I cannot listen) |
| 5 | No serious visual error | frame-by-frame look at the whole clip (continuous playback, not stills), including the cutaway and the closing loop | open |
| 6 | Owner approval | explicit "yes, upload" after watching the final MP4 | waiting |

Allowed to be imperfect: realism (box-model truck, sphere stones). Not allowed: narration that the picture does not show, awkward cuts, clipped text, black frames.

## Honest content notes to keep (they protect the channel)
- The film is a **simulation with assumed values** (gravel 0.25 g, pavement 0.01 g, 20 t, 90 km/h): the on-screen HUD says "ASSUMED" and the description must too.
  "25x more drag" is the ratio of those two assumptions; "24x farther" is the simulated stopping distances (3,184 m vs 133 m).
- It is 3D animation, not footage. Decide in YouTube Studio whether the "altered or synthetic content" disclosure applies (the narration is a synthetic voice);
  the answer is the owner's.

## Draft metadata (edit freely; not posted)
- Title options: "Why Truck Runaway Ramps Are Made of Gravel" / "How Gravel Stops a Truck With No Brakes" / "A Runaway Truck Hits Gravel: Why It Stops in 130 m".
- Description (draft): "A 20-tonne truck with failed brakes enters a gravel arrester bed. Why does loose gravel stop it so much faster than pavement? This is a 3D simulation with
  assumed values (rolling resistance about 0.25 g on gravel vs 0.01 g on pavement), not real footage. #shorts #engineering #roads #physics #CuriousMechanics"
- Pinned comment (poll): "Which hidden road-safety mechanism next? 1) Why guardrail ends curl away 2) Why rumble strips make that sound 3) Why bridges have gaps - reply with a number."
  (Topics are examples; pick from what the channel already planned.)

## What to compare after posting (the first road-sign film is the baseline)
Baseline (first road-sign film, as reported by the owner): 2,535 views, +2 subscribers, 66.9 % viewed instead of swiped away, average view 23 s of 32 s.
Record for this film at 24 h and 48 h: views, "stayed to watch" %, average view duration, subscribers gained, impressions and click-through if shown, the first-3-second
retention dip, traffic source mix (Shorts feed vs other). One film per topic is a very small sample: a difference of a few hundred views or a few points of retention is
not evidence by itself; look at the retention curve shape (where viewers leave) before changing the formula. Do not change title, thumbnail or description for the first
24 h unless something is wrong, so the comparison stays readable.

## Order of work from here
1. Finish round 3 (opening 190-285) and its checks; decide pass/fail on the recovered MP4, not on numbers.
2. If round 3 passes: full 32 s render on free runners (15-frame shards for the heavy early frames), final assembly with the real narration, native QA, MP4 recovery with hash check.
3. Owner watches the final MP4 and listens to the voice once (gates 4-6).
4. Owner approves and posts. Shared camera-quality module and the R2 handoff come after the upload, not before.
