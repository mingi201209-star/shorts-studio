# Guardrail V2 — isolated native-resolution visual proof

Development experiment only. It does **not** replace Shorts Studio's production renderer, remove existing quality floors, or certify physical crash behavior.

## First goal
Make W-beam **side-face deformation visually obvious** from a fixed camera. V2 alters the hero camera to an elevated oblique angle and adds a thin cyan undeformed-rail contour as a comparison reference; the 3D shape-key rail bends under localized Gaussian falloff. Nearby steel posts pivot from soil-contact locations, and a separately licensed CC0 Sedan GLB follows a controlled illustrative trajectory. **NOT a crash simulation**. No engineering claims are inferred from the illustrative deformation amplitude; check FHWA guardrail evidence before production.

Technical acceptance includes:
- True rendered source resolution 1080×1920 at 100%, Cycles 16 samples and denoising
- Camera unanimated and unparented
- All sedan mesh bounding boxes remain within a 5% camera margin at frames 1, 22 and 40 (not merely the car origin)
- Reference rail guide exists
- Rail world-space shape changes from frame 1 to 40 and camera-space projected displacement **>=40px** (an experimental visibility threshold, not a physical dimension)
- Full-native images at frames 1 (before), 22 (contact) and 40 (peak)
- Same 3 frames distinctive and individually SHA checked for artifact integrity
- Editorial review **not** replaced by these numeric gates

Measured on phone with Blender 5.0.1 ARM64: the initial 43mm camera yielded projected rail motion **100.6px** but visibly cropped the sedan. This visual-QA finding caused a camera framing revision (22mm and leftward fixed aim). After revision, projected rail displacement remained **51.7px**, and full vehicle bounding boxes remained inside 5% frame margins at frames 1,22,40. This is a *geometry and framing QA pass only*, not editorial realism acceptance.

## V3 contact-solved revision (editorial QA response)
Editorial review of CI run 39006222977 failed V2 for a toy-looking sedan, understated rail deflection and a car that never touched the rail. Measured with the new gate, the V2 scene left a **146 mm** car-to-rail gap at frame 22 and **212 mm** at frame 40, so the rail bulged on its own.

V3 changes:
- The sedan follows an explicit 25° encroachment (the NCHRP 350 / MASH test angle), is redirected parallel to the rail, then tail-slaps and exits. It is scaled so the 0.71 m W-beam top sits at a realistic height relative to the car.
- Rail deflection is **solved per frame from the car's own world-space mesh points** inside the rail height band, not hand-placed. The deflection spreads along the tensioned beam, the corrugation flattens under load, and a plastic residual remains (peak 0.53 m, residual 0.37 m). The rail is one shape key per frame with constant interpolation.
- Posts (1.9 m spacing) carry blockouts and bolts and rotate about the soil pivot so their top follows the solved rail. Bolts no longer float when the rail moves.
- The undisturbed W-beam continues upstream, the ground is long enough to hide its end, and texture noise uses object coordinates, so nothing stretches.
- Car materials changed to coated metallic paint, glass, rubber and machined metal. The camera is fixed, elevated and front three-quarter, so the nose-into-rail contact is visible instead of hidden behind the body.

New fail-closed gates (all V2 gates kept):
- Car/rail contact gap per rail column at frames 22 and 40 must be within −25…+30 mm (touching, not penetrating). Frame 1 must show an approach gap above 100 mm.
- World-space rail deflection at frame 40 must be ≥ 0.35 m. Projected displacement ≥ 40 px (V3 measures 97.5 px).

Local measurement (Blender 5.0.1 ARM64): contact gap 0.323 / 0.013 / 0.013 m at frames 1/22/40, car bounds inside 5% margins at all three frames. Still a **conceptual illustration, not a crash simulation**. The CC0 sedan geometry itself remains low-poly, and a better licensed vehicle asset is still an open editorial item.

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
