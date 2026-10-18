# Pinned vehicle assets

Both models are original unbranded Innerscene assets under CC0. Binary assets
are downloaded at build time and verified; no model binaries are committed.

| Variant | Source | SHA-256 |
|---|---|---|
| legacy | https://www.innerscene.com/tools/library/3d-parts/sedan-car-42109739 | 4cb896f740de4da871c1d87c4af2b734db3d1e8fac852e308f1fca03a63b25d3 |
| graphite | https://www.innerscene.com/tools/library/3d-parts/graphite-four-door-sedan-eed96d12 | feb0be31d153ddb42dc15ae52a651e214e85ab67e31bec4282b00f9d47c9b597 |

The graphite source has 304 mesh objects / 134151 vertices, a curved body shell,
separate tyre/rim/hardware assemblies and a cabin. More vertices are not treated
as a quality certificate: compare rendered geometry and motion against legacy.

Source graphite forward is -X. The adapter rotates it +90 degrees around Z to
the project's -Y forward convention, then uses measured tyre vertices to set
the local ground origin. All render geometry is preserved. The tyre meshes
determine four rolling pivots; only wheel and rotor parts rotate. Brake calipers
stay with the body. Mirror cap, housing, plinth and insert attachment checks
use explicit source part names and preserve the existing 25/20 mm gap limits.

The adapters reuse Blender's official glTF importer, matrices, KDTree and
keyframe APIs. The small custom code exists to map these two authored naming/
axis conventions into the existing scene; it is not a generic physics solver.
See https://docs.blender.org/api/5.0/bpy.types.Object.html .

Both variants run the original still and full-frame gates plus actual negative
Blender cases in CI. Legacy remains the default local option for rollback;
CI's delivered visual clip selects graphite only after both preflights pass.

## Roadside look

The graphite look reuses the previously pinned CC0 Poly Haven HDRI and asphalt.
Road markings are placed on the real asphalt surface, not centimetres above it.
A deterministic rolling field, short sparse blade geometry and linked pebbles
replace the featureless field. All vegetation remains behind the contact
corridor and below the beam. The camera and all motion contracts stay fixed.
The cyan undeformed reference remains available to geometry QA but is hidden
in the styled graphite render.

This is still an explanatory kinematic illustration, not an engineering crash
simulation. Visual fidelity and full-motion review remain separate from numeric
gates; narration / a finished uploadable Short are outside this look proof.

Graphite uses opaque tinted explainer glazing with 0 transmission / alpha 1, including the source glass.001 material. The source 94% transmission produced noisy cabin glazing in preview; this explicit look avoids that artifact without lowering render samples or geometry gates.
