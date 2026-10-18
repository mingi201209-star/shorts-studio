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
