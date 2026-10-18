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

## 2026-10-18 continuous-motion implementation

The imported CC0 sedan already exists; this revision does not rebuild a car.
The owner's uncommitted two-mirror repair was preserved before editing in a
separate worktree and backup patch. Both assemblies are anchored to the cabin;
all mesh children retain constant parent-relative transforms during animation.

Four measured tyre-centre pivots reuse the imported tyre/rim/spoke meshes.
Their angle follows accumulated path distance divided by the measured wheel
radius. The rigid car no longer rolls through the road; suspension/body
deformation is outside this illustrative model. The fixed lens widens from
22 to 20 mm to keep the exit in frame. Relative shape keys use Blender 5 action
channel bags with linear interpolation, preserving a partition of unity at
half frames. Posts use linear interpolation too.

The initial full-frame audit found failures missed by the 1/22/40 still checks:
45 tyre-ground violations, 10 late-frame margin violations, and an incorrectly
interpreted contact-push field. That field measures encroachment beyond the
original rail line; it is not proof of ongoing contact with the deformed rail.
The declared primary contact interval is frames 12–48. All frames still check
penetration, and every new rail displacement peak requires actual nearby
contact, including after that interval. This caught three phantom-load frames
52–54. The solver now iterates the car envelope against the actual sagged beam
height band instead of taking vertices above the beam as a load source.

`validate_motion.py` fails closed on:
- all 90 vehicle bounds inside the existing 5% margin;
- both mirror stalk/shell gaps and every mesh part's relative matrix;
- four tyre-ground gaps (-5 to +15 mm visual tolerance);
- wheel angle versus measured travel;
- actual beam/car gap, including the original -25/+30 mm contact criteria;
- primary contact, and new deformation peaks without contact;
- car/frame displacement <=120 mm, rotation <=3 degrees/frame, and rail
  displacement <=120 mm/frame (continuity diagnostics, not crash limits);
- shape-key unity/positivity at every half frame.

The original native resolution, >=16 sample scene setting, fixed camera,
>=40 px projected displacement and >=0.35 m deflection gates remain.
`check_motion_regressions.py` injects disconnected mirror and displaced rail
geometry into separate temporary in-memory scenes and requires rejection.
No production engine, TTS, caption, semantic, retention or safe-area gate changed.

Look development reuses CC0 Poly Haven assets: suburban_field_01 HDRI for
illumination/reflections only and asphalt_01 diffuse. All external assets use
exact SHA-256 checks in both CI and look application; images are packed into
the transferable .blend. The visible sky is synthetic. Sources:
https://polyhaven.com/license
https://polyhaven.com/a/suburban_field_01
https://polyhaven.com/a/asphalt_01
https://docs.blender.org/api/5.0/bpy.types.Object.html
https://mwrsf.unl.edu/reportResult.php?reportId=499

Blender's maintained import, matrix, keyframe, node and rendering APIs supply
the underlying implementations. Custom code is limited to this authored
scene's mesh naming, contact illustration and failure checks; a general crash
solver would not certify this uncalibrated asset or its material response.

CI now gates the scene before rendering nine contiguous 10-frame native
ranges (1080x1920, Cycles 32 samples), validates all 90 PNGs including original
proof frames 1/22/40, encodes H.264 at CRF17, and verifies dimensions, frame count,
30 fps and 3.0 s duration. The resulting clip is **visual-only development
evidence**, not an uploadable narrated Short.

Editorial status remains separate: the car silhouette is visibly low-poly.
Neither geometric PASS, denoising nor a higher sample count proves premium
appearance, scientific crash fidelity or viewer satisfaction. Review the full
motion and the final native frames before deciding whether to expand the film.
Keep the PR draft. No merge, publishing, paid API or new cloud service.

Continuous renders retain Cycles persistent data (official Blender 5 performance option). This changes cache lifetime, not resolution, samples or QA floors. Ten-frame CI shards avoid the prior 30-frame timeout risk.

## Graphite visual-quality iteration

Set VISUAL_VEHICLE_VARIANT=graphite and supply the pinned graphite GLB in VISUAL_V2_ASSET. The legacy default and its same-frame gates are preserved. See [ASSETS.md](ASSETS.md) for licensing, axes, wheel/attachment mapping and the restrained roadside geometry. CI checks both variants before rendering the graphite clip.

## Splice hardware continuity correction

The new independent surface audit rejects the previous graphite scene: the
24 splice-bolt centres can be as far as 86.1 mm from the actual deformed beam
surface. The old fixed local bolt offset was already separated from its
corrugation row; rotating the entire support about its soil pivot introduced
further vertical and horizontal mismatch under load.

Each bolt now follows its own corrugation row, including flattening, with an
8 mm outward centre offset. Blockouts translate with the beam centre. Post
geometry shears above the buried foot to meet the beam displacement and sag,
while the soil footprint stays fixed. This is authored geometric motion,
not calibrated steel deformation or a crash simulation.

The full-motion gate now measures all 24 bolt centres against interpolated
beam-surface segments at every frame (25 mm maximum) and requires all 12
post footprints to remain within 1 mm of their initial positions. A real
displaced-bolt mesh mutation must fail, alongside the existing detached
mirror and lost-contact cases. Car contact reports include the witness mesh
and world position so approach, strike, peak, redirection and exit can be
reviewed reproducibly. Existing car, tyre, camera, continuity, resolution
and visual-displacement thresholds are unchanged.

Editorial acceptance remains pending until the exact-head rendered frames
and video have been reviewed. The previous revision remains available on
the backup branch; this PR stays draft.
