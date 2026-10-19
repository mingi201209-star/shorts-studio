# Episode 2 — shoulder rumble strip alerts (EN, 30 seconds)

**Launch lane:** Hidden Engineering of American Roads. This is the second of seven initially agreed topics, not a generic new-topic engine.

The source is an authored original CC0 Innerscene sedan packed into the hash-pinned guardrail Blender scene. It must be verified at the exact SHA-256 referenced in the manifest. Animated 3D is an explanatory slow-motion demonstration, **not an engineering tire-contact solver**.

## Fixed 30s shot plan

Each of six segments has 150 authored native frames at 30fps (total exactly **900** at 1080×1920 Cycles32). Distinct visual stages:

1. Driver warning in wide full-car view, immediate visual of recessed road grooves
2. Real shoulder milling, not painted stripes
3. Rotating tyre crossing actual road depression geometry
4. Audible/tactile vibration explained by contact motion, without physically spurious sound waves
5. Wide shoulder location and stripe context
6. Driver still must take corrective action, no self-steering false claim

**Evidence:** FHWA longitudinal rumble strips and stripes, cited in the manifest. **Narration:** English, approximately 70–80 words, six 5-second segments. Measured English TTS and forced/aligned captions remain a release blocker: neither is silently substituted by a generic robotic placeholder.

## Rendering and release gates

A production renderer must use **absolute global frame numbers** and the same deterministic car trajectory even when the shots are independently rendered by GitHub Actions shards. No per-shard reset, no loops, no static-frame cloning. Proof records must show the pinned car scene SHA, Cycles 32, 1080×1920 and 30fps.

The manifest itself is a **plan**, not finished footage. Do not increase weekly completed inventory until a real 900-frame 30-second English MP4 passes source/proof/frame QA, audio, captions and human visual assessment. YouTube uploads require user manual action.

Check timing contracts:

```bash
python -m shorts_studio.factory.rumble_episode2 --manifest examples/factory/rumble-episode2-30s.json --start 1 --end 30
```

## Actual isolated full-quality frame gate

The source binary verified by visual review is NOT the different 7MB guardrail scene from an older Actions run. It is preserved as a checksum-verified public GitHub prerelease asset:

https://github.com/mingi201209-star/shorts-studio/releases/tag/rumble-episode2-scene-a82e0582-20261018

The native render smoke uses the exact hash-pinned Blender 5.0.1 executable, the source asset with SHA-256 a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877, fixed native 1080x1920/Cycles32, and two separately calculated moving frames. No new footage uses preview/upscaling/interpolation. QA checks exact numbered PNGs, image decode, each frame hash, absolute trajectory, original model, camera evidence, and no upload authorization.

The earlier six 450x800/Cycles7 storyboard frames passed creation but FAILED editorial expectations (too much zebra-striping). The final revised narrow shoulder rumble groove geometry keeps the rest of the driving lane level. This is still not a release-ready 30-second film; final TTS, safe subtitles, source evidence review, edit pacing and 900 unique native frames are outstanding.


## Full-film implementation — 2026-10-19

All six native Cycles32 storyboard cameras were rendered in run39210381736 at f307f067a424c9b97cb85f729348155d9c9308d8 and visually inspected. Existing test/smoke checks also passed. This remains editorial review, not approval.

The isolated full-film workflow uses thirty contiguous 30-frame shards with absolute global indices1..900. Existing native/source/camera QA remains intact. FFV1 carries every source RGB pixel losslessly; each shard and final assembly independently compare decoded RGB SHA256 values. The final H264 encode happens once after caption compositing. Missing/duplicate frames, changed shot cameras at shard joins, different source hashes or reduced Cycles/resolution fail the assembly.

English narration uses six real en-US-AndrewNeural +5% captures, raw provider MP3 provenance plus exact PCM tails and genuine word boundaries. The script is88words with32measured caption cues. No speech acceleration, invented alignment or upper overlays. Local AAC preflight maximum detected silence0.710708s,total4.839603s at-35dB,d0.3; original <=0.9s/max and <=5s/total gates retained. Comfort still needs subjective listening.

Custom code is episode-specific integration of existing factory source/timeline/shard QA, timing types/validation, prior audited English-caption layout, FFmpeg FFV1/libx264/ASS and Pillow font measurements; no alternative media engine or provider is introduced. Source reference was repaired from404 to the current official FHWA two-lane-roads page in the manifest. No physical tire solver or upload approval is claimed.

Full workflow writes native frame render times and final encode time. They measure stages, not a proven five-minute total. A managed worker cannot resume this completed campaign or configure a different root through the installed manager API; the authorized operator is working in this isolated PR56 worktree. Manager state/policy/root were not modified.


## Recovery from measured native job timeouts

Original run39211610129 produced real accepted30-frame shards, but eight slow ranges(151,181,391,421,481,511,541,571) reached the45-minute runner limit. Frame151-job logs show roughly102seconds/frame, stopping after176of180. These partial unexported images are not counted as accepted footage. Other original ranges continue independently and are preserved.

Recovery renders ONLY those terminal failed ranges as24ten-frame jobs after a live job/artifact nonoverlap guard. It does not restart source jobs that are still active. After initial recovery, a planning job waits for the original run to become terminal, unions old30/new10 artifact coverage, and schedules any remaining truly missing ten-frame blocks. Independent accepted shards are retained even if a different job fails; no continue-on-error or quality-gate bypass is used.

Assembly still requires exactglobal1..900, unchanged renderer/source hashes, native1080x1920/Cycles32, unique original/decodedRGB frames, all6fixed shot cameras, source mesh/wheel gates, measured English captions and original AAC silence gates. Mixed FFV1 segment timestamps are normalized to the authored global30fps clock with setpts=N/(30*TB), without creating or dropping source frames. Report records reused/new counts and the original cache run.

Regression:31focused tests pass, including missing/overlapping/partial/oversized/mismatched mixed-span rejection; Ruff clean. Workflow YAML and embedded Python parsed; isolated coordinator fixtures verified zero-missing and late-missing paths and rejected overlapping or absent artifacts. Fixtures test scheduling only, not production rendering or user acceptance. Original production and new recovery outcomes must still be checked live.
