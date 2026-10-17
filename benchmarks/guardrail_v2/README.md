# Guardrail V2 — isolated native-resolution visual proof

Development experiment only. It does **not** replace Shorts Studio's production renderer, remove existing quality floors, or certify physical crash behavior.

## First goal
Make W-beam **side-face deformation visually obvious** from a fixed camera. V2 alters the hero camera to an elevated oblique angle and adds a thin cyan undeformed-rail contour as a comparison reference; the 3D shape-key rail bends under localized Gaussian falloff. Nearby steel posts pivot from soil-contact locations, and a separately licensed CC0 Sedan GLB follows a controlled illustrative trajectory. **NOT a crash simulation**. No engineering claims are inferred from the illustrative deformation amplitude; check FHWA guardrail evidence before production.

Technical acceptance includes:
- True rendered source resolution 1080×1920 at 100%, Cycles 16 samples and denoising
- Camera unanimated and unparented
- Reference rail guide exists
- Rail world-space shape changes from frame 1 to 40 and camera-space projected displacement **>=40px** (an experimental visibility threshold, not a physical dimension)
- Full-native images at frames 1 (before), 22 (contact) and 40 (peak)
- Same 3 frames distinctive and individually SHA checked for artifact integrity
- Editorial review **not** replaced by these numeric gates

Measured on phone with Blender 5.0.1 ARM64 prior to first CI: fixed camera and native resolution passed, projected rail motion **100.6px** (frame 1 vs 40). This was a *geometry QA pass only*.

## Reproduce
From the repository root with official Blender 5.0.1 and the CC0 Sedan already available:
```bash
export VISUAL_V2_OUTPUT=/tmp/guardrail-v2
export VISUAL_V2_ASSET=/path/to/sedan-original.glb
blender -b -t 4 --python benchmarks/guardrail_v2/build_scene.py -- scene 100 16
blender -b -t 4 "$VISUAL_V2_OUTPUT/guardrail_v2_local.blend" --python benchmarks/guardrail_v2/validate_scene.py
```

To render proof stills, set a requested frame manually and run Blender native; the parallel PR workflow does this for frames 1,22,40. Images are artifacts, not deliverable production MP4s.

Sources: [FHWA Guardrail 101](https://highways.dot.gov/safety/rwd/reduce-crash-severity/guardrail-101), [CC0 sedan model](https://www.innerscene.com/tools/library/3d-parts/sedan-car-42109739). The external GLB is downloaded only at CI run time after an exact SHA-256 check. No paid provider, auto-upload, YouTube publish, or auto-merge.

## Release gates still missing
Physical-motion fidelity, premium PBR look, body/rail contact credibility, 0–5s actual visual hook from a full 3s video, no misleading crash-test implication, correct subtitle-safe composition, voice human audition. Do **not** convert this PR to production until those have been demonstrated. If native stills are disappointing, keep the branch draft and iterate without modifying `main`.
