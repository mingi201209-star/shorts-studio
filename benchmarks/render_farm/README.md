# Two-repository render scheduler A/B experiment (2026-10-18)

**Hypothesis:** splitting one small Blender render across multiple GitHub repositories might reduce job queue time. This is **not** expected to multiply the owner's overall GitHub Actions concurrent-run quota.

Repositories:
- Primary: `mingi201209-star/shorts-studio`, branch `render-farm/single-20261018` (2 GitHub-hosted runner matrix jobs) or `render-farm/multi-20261018` (shard 0).
- Independent public worker: `mingi201209-star/shorts-render-worker`, branch `render-farm/multi-20261018` (shard 1).

The **same** Blender road-rumble procedural scene and verifier files are SHA-identical in both repositories. There are 6 authored native moving frames split into two shards, each 3 frames. Both modes use the same Ubuntu 24.04 runner class, apt Blender, 2 render threads, Cycles 6 samples, **test-only denoising disabled** (Ubuntu apt Blender 4 does not provide OpenImageDenoiser), 320x576, and fixed camera. This is deliberately a short low-cost infrastructure probe, **not a Shorts quality benchmark or production change**.

Procedure:
1. Push the coordinator commit on branch `render-farm/single-20261018`; wait for the complete workflow.
2. Push worker and coordinator refs for `render-farm/multi-20261018` close together; wait for both independent workflow runs.
3. Compare elapsed wall time from earliest enqueue to last completed worker; account for setup/install, queue waiting, render time and download/merge overhead. Inspect job-specific time spans.
4. Download all four artifacts using local `gh` authentication on the phone, **not cross-repository `GITHUB_TOKEN`**. Verify each shard's original code checksum and all decoded original frame checksums; confirm frame 1-6 coverage without overlap.
5. Report measured time, rather than assuming speedup. Stop at 2 repos if user account-level runner concurrency is already saturated or results are equal/slower.

No merge, no full episode render, no YouTube upload, no token copied into workflow, no external billing API. Keep artifact retention at one day to reduce artifact storage overhead; persist metadata in a PR comment instead. Keep existing main and QA unchanged.
