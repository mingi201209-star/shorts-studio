# Runaway truck ramp: upload readiness (draft, nothing is published; `upload_authorized` stays false until the owner says otherwise)

Decision recorded 2026-11-15: this film is the **candidate for the second upload**. The film is published only after (1) the final 32 s cut is rendered and
checked, (2) the owner approves it, (3) the owner posts it. No agent action uploads anything.

## Gate list (a gate that is not PASS blocks the upload; "not verified" is not PASS)

| # | Gate | What counts as PASS | Status now |
|---|---|---|---|
| 1 | Full 32 s final render | 960 frames, 1080x1920, 30 fps, native QA green, MP4 recovered and its SHA-256 equals the runner's | **PASS (2026-11-15)** - production run 43662175061 (26/26 jobs), full-res final `7e68d974...5dece` (round-2 camera, realism B, derived callouts; round 3 skipped by decision). The 540x960 review copy was recovered through job logs: 960 frames, 32.000 s, H.264 + AAC, sha256 `1e8f16b8...01c2` equals the runner's, every 200 kB chunk hash matched. The full-res file itself stays in the Actions artifact (not recovered here) |
| 2 | Narration matches the picture | `narration_screen_match` + `first_three_seconds` PASS on the final, plus a human look at the six sentences against the frames | gates PASS on the final (run 43662175061). Looked at 1 frame/s of the recovered copy against the captions: truck + BRAKES FAILED -> wheel in gravel -> 3-step cutaway (sinks in / stones pile up / pile pushes back) -> 25x label -> 133 m vs 3,184 m with 24x -> road-sign style closing. Weak spot, not blocking: seconds ~8-9 show a trailer wall and empty ground while the narration says "digging through them quickly" |
| 3 | No clipped captions, no black frames | `caption_safety`, `captions_visible`, `black_opening`, blackdetect clean on the final MP4 | **PASS** - gates PASS; blackdetect on the recovered copy found nothing; captions are single-line inside the black band. Cosmetic: on the cutaway shots the "BED DEPTH ~0.6 m (DRAWN)" label runs past the picture edge and "ORIGINAL SURFACE" overlaps the wheel (not a caption, not blocking) |
| 4 | Voice: pronunciation, noise, sync | loudness/silence gates PASS **and** a person listens once | gates PASS: -16.7 LUFS integrated (about 2.7 dB under -14), LRA 1.6 LU, no clipping flagged; silences between sentences at 4.48-4.98, 9.54-10.04, 14.07-14.57, 19.42-19.94, 25.90-26.42 s match the gaps of RAMP_SPOKEN_WINDOWS within 0.04 s. **Pronunciation and how the voice sounds are NOT verified** (neural TTS; I cannot listen); caption-to-speech sync checked only through these windows, not by ear |
| 5 | No serious visual error | frame-by-frame look at the whole clip (continuous playback, not stills), including the cutaway and the closing loop | **partly done** - 1 frame/s contact sheets of the whole recovered copy plus scene-change detection (cuts at 9.5, 14.9, 18.6, 26.4, 30.0 s, all at planned shot changes) show no serious error and a clean loop back to the distant-truck opening. A real-time playback by a person is still needed (not PASS until the owner watches) |
| 6 | Owner approval | explicit "yes, upload" after watching the final MP4 | **conditional (2026-11-15)**: owner watched the review MP4, no further round-3/realism work; posts after (a) listening once to the voice (pronunciation, noise, caption sync) and (b) the assumption disclosure below is in the posted text. Upload not executed |

Allowed to be imperfect: realism (box-model truck, sphere stones). Not allowed: narration that the picture does not show, awkward cuts, clipped text, black frames.

## Honest content notes to keep (they protect the channel)
- The film is a **simulation with assumed values** (gravel 0.25 g, pavement 0.01 g, 20 t, 90 km/h): the on-screen HUD says "ASSUMED" and the description must too.
  "25x more drag" is the ratio of those two assumptions; "24x farther" is the simulated stopping distances (3,184 m vs 133 m).
- It is 3D animation, not footage. Decide in YouTube Studio whether the "altered or synthetic content" disclosure applies (the narration is a synthetic voice);
  the answer is the owner's.

## Assumption disclosure (condition b)
- In the picture: the HUD shows `GRAVEL 0.25 g | PAVEMENT 0.01 g (ASSUMED)` from about 15 s, and `SIMULATION | 20,000 kg TRUCK | NO BRAKES` from the start (small text). The narration does not say "assumed".
- Therefore put it in the posted text: first line of the description and the pinned comment (draft below). "25x" = ratio of the two assumed resistance values; "24x" = simulated distances, not a guarantee for any real road.
- Pinned-comment draft: "Simulation with assumed values (gravel 0.25 g, pavement 0.01 g, 20 t, 90 km/h). The 25x and 24x figures come from those assumptions, not from a measured road."

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
