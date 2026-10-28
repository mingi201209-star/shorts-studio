# Premium / Fast native asset pipeline

This opt-in path preserves the existing Shorts renderer. It creates clean native
3D clips and reusable Blender scenes; it does not publish or grant final Short
approval.

## Supported initial generator

Premium constructs an owned procedural wheel (rubber tire, alloy rim, hub, seven
spokes and an orange motion marker), renders a Cycles32 portrait thumbnail, saves
the Blender source and generating Python source, verifies file provenance, and
automatically registers the bundle in the static asset library.

Fast searches the library for matching source provenance and loads the same
model without regenerating geometry. A fresh scene cache can still find the
registered model. Existing legacy shelf assets remain searchable; their original
unverified license status is preserved.

Two native scene presets demonstrate recomposition:
- rolling: centre translation and wheel rotation obey v = radius * angular speed;
- locked: the same model translates while its angular rotation stays zero.

The camera stays fixed. The floor, lighting and actual per-frame marker position
are measured. This is an explicit kinematic illustration, not a force/friction/
collision simulation. Physics validation and final production approval remain
false. Topic narration, captions, factual editorial review and existing final
video gates remain required for a complete Short.

## Commands

Use Blender 5.0.1 and the project's Python environment with Pillow and NumPy.
The native profile is 1080x1920, 30fps, Cycles32, CPU, fixed seed 42.

```bash
python -m shorts_studio.dual_mode --library /assets/library --cache /assets/case-cache --blender /tools/blender --receipt /evidence/premium.json --frames 30 premium --motion rolling
python -m shorts_studio.dual_mode --library /assets/library --cache /assets/case-cache --blender /tools/blender --receipt /evidence/fast-same.json --frames 30 fast --motion rolling
python -m shorts_studio.dual_mode --library /assets/library --cache /assets/case-cache --blender /tools/blender --receipt /evidence/fast-new.json --frames 30 fast --motion locked
python -m shorts_studio.dual_mode --library /assets/library --cache /assets/case-cache --blender /tools/blender --receipt /evidence/scenes.json list-scenes --motion locked
```

A complete scene is registered in the scene cache only after native QA passes.
It contains scene.blend, original frame PNGs, motion.json, the encoded clean clip
and proof.json. Scene listing revalidates the source/decoded frames, motion and
output hashes. A receipt is never silently overwritten.

## Cache and recovery

Keys bind the model bundle, complete producer/registry/validator source hashes,
linked binary dependency hashes, Blender version, Pillow/NumPy versions, platform,
frame count, motion parameters and native profile. Audio and caption text do not
enter these clean-visual cache keys. Dependencies are rechecked before a scene is
published and before a cache hit is returned. Corruption fails closed.

Commands have process-group timeouts. Failed staging directories retain their
diagnostics under .failed-* and cannot qualify as completed scenes. Local file
locks prevent duplicate writers. Inspect the existing PID and receipts before
retrying an uncertain external job.

## Controlled comparison

A benchmark requires a fresh scene/source cache and a new receipt path:

```bash
python -m shorts_studio.dual_mode --library /assets/library --cache /assets/fresh-benchmark --blender /tools/blender --receipt /evidence/comparison.json --frames 8 benchmark
```

It measures a real Premium cold build/render, a Fast hit for the same scene, and
a Fast new-scene render using the same asset. The first two clips must be bit
identical. The new locked scene must contain fresh native frames and must not
regenerate the model.

Completed stages are checkpointed next to the receipt in a .phases directory.
After reconciling an interrupted job, repeat the same command with --resume.
Changed inputs cannot relabel existing measurements. An interrupted cold phase
without a completed timing checkpoint needs a new cold experiment; its partial
evidence is retained. Ordinary Premium/Fast runs can reuse independently verified
completed assets/scenes.

Report exact tested frame counts and end-to-end times. An 8-frame experiment is
8/30 seconds of clean native motion, not a full Short or a 30-second speed claim.
Cached clip reuse is distinct from accelerating a newly composed scene. No fixed
five-minute cold-render guarantee is implied.

## Automatic clean sequence assembly

Use a JSON sequence with explicit scene keys and optional inclusive native frame
cuts. The compositor validates each complete source scene again, copies original
native PNGs with per-frame provenance, encodes without interpolation and verifies
the decoded result. Repeated original frames are rejected rather than extended
to fill duration. If two scenes deliberately share the same initial pose, select
an explicit nonduplicate cut; no automatic hidden trim is performed.

Example sequence:
{"parts":[{"key":"<rolling scene key>"},{"key":"<locked scene key>","start":2}]}

python -m shorts_studio.dual_mode_compose --cache /assets/case-cache --sequence /evidence/sequence.json --output /evidence/assembled

The result is sequence.mp4 plus frame-level mapping and output hashes. It is a
clean motion asset sequence: audio/subtitle QA is not applicable, and final
production approval remains false. Existing complete-Short gates are still
required after narration and captions are added.

## One-command workflow and review

python -m shorts_studio.dual_mode_pipeline --library /assets/library --cache /assets/fresh-cache --blender /tools/blender --receipt /evidence/comparison.json --review /evidence/review --frames 8

The supported rolling/locked recipe performs the checkpointed benchmark, checks
visible orange-tracer displacement in actual rendered pixels, selects explicit
native source cuts, composes the clean sequence, and packages the videos, pose
contact sheet and measured report. An orchestration lock rejects duplicate
writers. Use --resume only after reconciling a stopped job; completed artifacts
are revalidated, not silently overwritten.

The recipe explicitly omits the locked scene's shared initial pose from the
combined sequence. This source cut is recorded in its provenance map. It does
not interpolate frames or extend a static picture.

python -m shorts_studio.dual_mode_preview --root /evidence/review --port 8766

The review server binds only to 127.0.0.1, serves only hash-bound manifest files,
supports byte ranges and disables caching. Videos loop for inspection; each
clip's actual native frame count and duration are shown. It is read-only and
does not approve or publish videos.

Geometry QA projects actual mesh vertices, rather than rotating empty corners
of the mesh bounding box. It checks positive camera depth and the actual lowest
mesh point within 2mm of the demonstration ground, as well as the declared
centre/radius relation. These checks establish visible kinematic alignment,
not force/friction/collision simulation validity.
