# Static 3D asset library

This opt-in CLI imports the existing Render Fast object shelf into immutable,
content-addressed bundles. It preserves the renderer and does not publish videos.

```bash
python -m shorts_studio.asset_library --library /absolute/asset-library import-shelf /absolute/object-shelf
python -m shorts_studio.asset_library --library /absolute/asset-library search --asset wheel --view side
python -m shorts_studio.asset_library --library /absolute/asset-library search --motion native_animation
```

Import automatically discovers completed shelf bundles, validates all three file
hashes and sizes, cross-checks source/model/image metadata, then copies the bundle
atomically under a library lock. Repeated import is idempotent. Partial, corrupt,
symlinked or unsupported entries are reported and excluded (CLI exits 2 when
any entry is rejected). Source files are never changed.

Lookup verifies the stored bytes again. Current supported objects are sedan,
wheel, rail and post, with side or three-quarter views. A static asset cannot
satisfy a native animation request. The returned model path can be used by a
scene builder, but no renderer automatically selects it yet.

Registration verifies integrity only. It does not establish visual quality,
Blender compatibility, physical behavior, editorial approval or licensing.
These shelf files remain explicitly unapproved for production and have
unverified license packaging. Model-specific Blender load and dependency
audits, portable license provenance, scene animation, and phenomenon QA are
required before final production.

The existing seven imported shelf views were independently opened with Blender
5.0.1 on the VPS. Their audits found no missing image/library dependencies,
zero animated objects and zero rigid bodies. This observation does not upgrade
future imports. The earlier Blender 4.0.2 runtime could not read these files.
Camera, geometry, lighting and materials can be reconstructed from the static
bundles; reusable collision or wheel-motion behavior has not been proven.
