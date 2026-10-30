# Curious Mechanics: three ways to plan the same Short

The same road-groove topic will be explored in three forms: explanation first, visual reversal, and a question-led story. The experiment asks whether an unfamiliar viewer can understand the situation, become curious about a visible event, follow a new causal development, and get a specific payoff.

This is a preproduction contract, not three finished videos. It does not establish growth, distribution, viewer preference, or readiness for publication. The original reference episode remains unmodified.

## Common topic and source
Question: Why do shallow grooves beside a lane make a car rumble?
FHWA describes rumble strips as milled or raised pavement elements intended to alert drivers through vibration and sound when a vehicle leaves the travel lane:
https://highways.dot.gov/safety/proven-safety-countermeasures/longitudinal-rumble-strips-and-stripes-two-lane-roads
The depicted example is a milled shoulder strip. Do not imply that every rumble strip has this construction, steers a car or guarantees a successful response. Native vehicle motion and sound remain stylized explanations unless separately measured.

## A: explanation first
The opening names rumble strips and their warning function, then demonstrates the milled surface, repeated tire contact and the driver response.

## B: visual reversal
Begin with a shallow-looking road surface and a tire that visibly encounters grooves. Reveal the actual recesses, then explain why the rumble is intentional. The contrast must exist in the physical footage, with no misleading scale change, zoom loop or painted fake groove.

## C: question-led story
A car reaches the shoulder and begins to rumble. Ask what the road is communicating, trace the signal through contact and vibration, then answer with lane departure and the driver's response. A viewer should need no prior knowledge of the channel.

The complete English narration and required visual evidence for each beat are in `examples/experiments/curious-mechanics-rumble-formats.json`.

## Controlled comparison
Keep facts, target length, narrator, natural speech rate, renderer quality, source asset pool, mixing and initial packaging comparable. Measure actual narration duration; 30 seconds is a target until synthesis and alignment are verified. Distinct versions from one topic are a format exploration, not proof of a universally superior format.

Blind the labels and counterbalance viewing order. A viewer who already watched one version is no longer unfamiliar with the topic for a three-second comprehension test. Separate the first-view response from later comparative preference.

## Five editorial requirements
1. Understand the situation within three seconds.
2. See a physical event that creates curiosity.
3. Receive a meaningful new fact or change in the middle.
4. Get a specific answer at the ending.
5. Learn the mechanism from 3D, beyond seeing a car move.

Every assessment needs actual playback, timestamps, a concrete observation and reviewer uncertainty. A written script, a missing file or a passing technical job cannot supply an editorial PASS. Sample every changed beat and transition: in the Comet diagnostic, the fixed sampler skipped the 47.10–50.10s comparison entirely.

## Production readiness
The latest audited cache is a 0.5-second native technical proof, not a ready 30-second film. Verify the pinned source scene, dependencies and rights, then inspect native opening/contact proofs before full renders. Keep all existing provenance, native-motion, voice, measured-caption, semantic, safe-area and final-video checks. Store technical QA and editorial review separately, both bound to the real output.

No score is currently populated and no winner is selected. These documents do not enable an automatic gate, modify the Comet worker, reset its counters, change a voice/model, spend money, merge a PR or publish a video.

Next production action: verify and render the shared physical mechanism, then produce the three cuts from validated clean native footage. Publication remains subject to the user's separate approval.

## Recovery and speech-cadence check
The prior 30-second English review was recovered from retained artifact 12171404885 and matched its recorded SHA-256 b0c4d3f72cb4e0315cc12ab5533aa4255ddd30906cf4c0400a65cc4760aa83df. The retained archive contains the captioned final and audio/QA, but no clean native clips. The upstream native-chunk artifact list returned no available files. It cannot be treated as clean footage for three new narrations.

The initial word-count estimate was superseded by actual synthesis. See the execution findings below; the JSON contains measured audio schedules.

## Execution on 2026-10-29

Source recovery succeeded: the retained GitHub release `rumble-episode2-scene-a82e0582-20261018` contains the original 2,267,793-byte Blender scene, matching SHA-256 `a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877`. The release and historical PR #50 asset record identify the legacy Innerscene sedan as CC0. Dependency checks now reject missing referenced image files and record packed/external image evidence.

Actual synthesis exposed a planning defect: the initial 59–61-word drafts supplied only about 20 seconds of audio. Expanded factual narration is captured using the existing `en-US-AndrewNeural` voice at the existing `+5%` rate. All three final 30-second mixes pass the existing silence and loudness gates. Captions use the provider's actual word boundaries and measured font widths. The JSON beat timings now follow measured audio, superseding the initial hand-written schedule and word-count estimates above. No audio time stretching or invented word timing is used.

The original isolated wheel opening lacked the new-viewer context. The opt-in experiment shows the original complete sedan and lane edge first, then cuts to the existing wheel and actual road-section geometry. A native lateral entry precedes the warning; the final lateral change depicts a driver response. Motion remains an uncalibrated explanatory illustration. Wider context framing required extending real road geometry. A new projection check rejects a clipped full vehicle in context/response shots, or a clipped required wheel in mechanism inserts. Preview/layout frames are never promoted as production footage.

Implementation is isolated from the original renderer and canonical timeline. The experiment's native QA retains all original shard thresholds and adds manifest/timeline/plan bindings and framing evidence. Render inputs are hashed before rendering and checked again before accepting provenance. The resumable queue verifies each original PNG and its lossless decoded clip, refuses uncertain partial shards, and allows only one render queue. It contains no publisher or paid API path.

Execution order: final bound layout checks, native 0–3-second and contact motion proofs for each variant, actual playback review, full 900-frame versions, full existing technical/semantic/caption checks, then timestamped five-criterion comparison and user review. The original queue's `--last-frame 90` rendered proofs. It is now stopped by the render-host policy below; the full-frame stage runs only in GitHub Actions. Neither stage automatically declares editorial approval. Full videos and a winner remain pending.


## GitHub render migration on 2026-10-30

The VPS is a controller, verification and storage host, never a render host. Its Blender queue was deliberately stopped with 353 PNGs preserved, including an incomplete C contact shard. Do not restart it or classify that partial shard as an automatic retry request.

GitHub standard `ubuntu-24.04` runners completed pilot run 41027081755 at source head `5209eef3ed8be786b4326b761b01b4d533ede7cc`. All three jobs and exact-head checks succeeded. Downloaded A/B 91–120 and C 241–270 passed native QA again and every RGB frame decoded from each FFV1 clip exactly matched its PNG. Their render-only times were 2557.428, 1491.642 and 1472.830 seconds respectively; parallel run elapsed time was about 44 minutes. This is a 90-frame pilot, not three finished films.

A small contact sheet includes all 30 consecutive C contact frames and three samples each from the two other pilot shards. The wheel and milled grooves stay visible with no obvious black edge or crop in these samples. This is limited image-sequence inspection, not full-resolution playback or an unfamiliar human comprehension test. Editorial approval and the five-item final comparison remain pending.

Fourteen accepted shards cover 420 of the required 2700 frames. The production matrix contains exactly the 76 missing 30-frame ranges, using at most 18 public standard runners simultaneously. Existing completed shards are reused only after current manifest, plan, timeline, source, renderer and original-PNG bindings pass again. The deliberately partial VPS C shard remains preserved and is not reused as a complete proof. Failed jobs preserve partial PNGs and render logs; no automatic retries are enabled. Production output still needs complete coverage, cross-shard checks, actual existing Andrew audio and measured captions, semantic/final QA and user review. No paid runner, purchase, merge or publication is enabled.


## Exact camera correction after native rendering

The first full GitHub run completed all76 jobs successfully. Per-shard validation does not prove cross-shard camera equality. The strict assembly check exposed a 0.000001m x-coordinate discrepancy: wheel spin was left at each shard's first frame while the car was fitted at the global shot anchor, so floating-point bounding-box centring varied. No visual defect or calibrated physical claim follows from that tiny number; the exact equality gate remains unchanged.

A separate no-render GitHub audit reproduced both A/C failures and then checked the candidate over all90 ranges/32shots. The candidate cameras match exactly across ranges. The production patch now fits wheel spin at the same global anchor and restores the absolute native spin before projection/rendering. The original source bytes are retained by SHA for honest historical validation. Current fixed-source audit additionally checks the restored absolute wheel angles at all2700 frame positions without producing images.

Only A91–120, A211–240, C211–240 and B721–750 are scheduled for corrective native rendering. Their previous PNGs/FFV1 clips remain preserved. Reused shards must pass their exact historical renderer/input/pixel checks and match the canonical fixed cameras; corrected shards must pass the fixed renderer/input/pixel checks. A mixed-source final must list actual hashes per shard, never relabel older pixels as a newer renderer or weaken camera equality. Full-film assembly/semantic/final QA/editorial approval still remain pending.
