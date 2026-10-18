# Shorts Factory — Phase 1: safe reusable planning

This is a **read-only manifest validator and per-shot dependency planner**. It does not render, synthesize voice, verify observed motion or publish a Short.

Usage:

```bash
python -m shorts_studio.factory examples/factory/guardrail.json --registry examples/factory/rigs.json --cache-dir /tmp/factory-cache
```

Exit 2 means a rig is blocked. Both supplied sample topics intentionally remain blocked until their native Blender rigs are implemented. Exit 0 means render prerequisites are planned, **not** that a video is upload-ready.

- Preserve native 1080×1920, 30fps, original per-frame animation, Cycles32 and fixed cameras.
- Audio changes must not invalidate native visual cache keys.
- Any cache hit requires exact provenance metadata; future renderer must verify decoded pixels and checksum after creating proof.json.
- Quality gates, original production entrypoints, engine defaults, main, PR #50 and YouTube upload remain unchanged.
- Next phase is one working native 3D template, a small rendered motion preview, two topic variants and full QA.
