# GPU Cycles render acceleration — cost-capped proof (2026-10-20)

Status: **TEST PROTOCOL / NO GPU ALLOCATED / NO PRODUCTION SETTINGS CHANGED**

## Purpose and go/no-go criteria

Determine whether a dedicated NVIDIA GPU genuinely accelerates Shorts Studio's **same native 3D scene** by >=10x **end-to-end**, without lowering its visual or source-provenance gates. A consumer Blender score or a different scene is not proof.

- Base project: `mingi201209-star/shorts-studio`
- Current production baseline `main`: `fcd20fd78851b18c550b1e433bee46ee34313c1d`
- **Unmerged episode #2 sample**: PR #56, exact head `b8bed7c56f0a72d815916eabedb3455f6a030cd2`, not main.
- Source (immutable published `.blend`): SHA256 `a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877`.
- Renderer: `benchmarks/road_safety/render_rumble_episode2.py`, Blender 5.0.1, 1080x1920, Cycles32, 30fps, original individual frames, fixed shot cameras.
- Manifest: `examples/factory/rumble-episode2-30s.json`; original source and renderer hashes must be recorded with every benchmark result.
- Native verification: `python -m shorts_studio.factory.rumble_native_shard_qa --out ... --manifest ... --renderer ...`.
- Initial representative absolute frames: `151`, `451`, `751` (separate shot contexts). If promising, use an unchanged contiguous `151..160` workload as the paired CPU/GPU comparison.

## Existing evidence / blockers

- PR #53 A/B/A persistent-data optimization showed **1.01x**, not material.
- Older full native guardrail footage: around 67m52s (run 39111993576); cache-audio assembly around 2m19s (run 39118313523). Different content means these are **context**, not the denominator in a GPU/CPU speedup computation.
- PR #56 reports a separate same-pipeline 10-frame CPU experiment around 772 seconds, and some production frames taking ~102s each (source scene/renderer revision must be matched before reusing any of this as a measured baseline).
- The current renderer explicitly sets `scene.cycles.device="CPU"`, fixed thread count; simply renting an NVIDIA server will **still run on CPU** until a benchmark-only adapter configures GPU devices.
- PR #56 exact-head test run 39265406180 succeeded; native proof run 39265399493 and smoke run 39265399622 each have six and one respectively successful terminal jobs. These are not proof of a GPU speedup or of publication readiness.
- A live paid GPU provider/account is **not connected** for this experiment. No API credential, purchase or charge is authorized by this protocol.

## Bounded GPU experiment, once a provider/cost limit is approved

1. Download a clean immutable checkout at PR #56 exact SHA; verify its renderer script digest and published source scene digest. Refuse input drift and any preexisting active render collision.
2. Install exactly Blender 5.0.1 on the candidate GPU machine; capture `nvidia-smi`, GPU PCI model, driver, VRAM, vCPU/RAM, CUDA/OptiX availability and Blender version.
3. Run unchanged CPU input and capture wall and per-frame timings, peak memory, proof and SHA-256 for rendered images. Reuse an *identical head/source/render settings* CPU result only if its evidence satisfies this step; don't compare with an unrelated old guardrail or rumble revision.
4. Prepare a **temporary benchmark-only renderer copy** under a mirrored repository structure; change only CPU-versus-GPU device selection and needed GPU activation via the Blender Cycles preference API. Production source files stay byte-for-byte unchanged, with hashes checked after the run.
5. Require observable `scene.cycles.device=GPU` and at least one enabled, correctly recognized GPU Cycles device; fail if device enumeration fails or CPU fallback occurs. Record the temporary candidate script hash and the exact device-selection change.
6. Run the same absolute indices (3 diagnostic frames, then 10 contiguous frames if the diagnostic is promising), same cameras, geometry, Blender build, 1080x1920, Cycles32, denoise and color transform. Never compare GPU preview-mode frames with native CPU frames.
7. Execute the existing frame, license/provenance, source-timeline, output-decode and image quality gates for both paths. Record image-difference metrics and visually review meaningful differences. **Do not silently relax existing QA** just because CPU/GPU floating-point RGB may differ.
8. Record cold start, scene transfer, scene load, GPU initialization, per-frame render, PNG/artifact upload, verification, FFmpeg final encode, and resource shutdown. Distinguish useful rendering seconds from chargeable wall time.
9. Compute paired speedups: `same-workload_CPU_render_seconds / GPU_render_seconds` and `same-workload_CPU_end_to_end_seconds / GPU_end_to_end_seconds`. The second is the >=10x go/no-go target for the full pipeline. Do not use 67m52s from a different scene in this fraction.
10. Review human-perceived motion/visibility (wheels engaging grooves, appropriate camera, no long boring car-only interval); publication remains blocked until an actual finished video is separately accepted.

## Cost and shutdown controls

- Test a single RTX 4090-class pod if available; actual cloud prices are dynamic. RunPod's October 2026 published Secure Cloud RTX 4090 rate is ~$0.89 per GPU-hour, excluding possible disk charges and provider billing nuances. Compare offers immediately before spending.
- **Zero new spending by default.** Before any GPU allocation, the owner must separately approve provider, maximum dollars, expiration time, credentials setup, and data transfer/privacy scope.
- The pilot proposal is a **maximum 30-minute GPU lease and maximum $2 GPU compute** (proposed ceilings, *not* permission to purchase); stop and tear down early on budget warning, unavailable GPU or unverified quality. Check provider's own quotas/billing cap independently: a script watchdog alone does not cap provider billing if the worker crashes.
- Terminate and confirm deallocation of paid compute, disks and persistent volumes when done; stopping the rendering process or powering down the machine may not stop all storage billing.
- Never publish/merge or automatically upgrade to a longer GPU lease upon success. Record evidence and request separate owner approval for scaled use.

## Exact acceptance report

| Field | Required evidence |
| --- | --- |
| `source_sha`, `renderer_sha`, `manifest_sha` | hashes recorded and checked on CPU and GPU |
| `blender_build`, `device`, `gpu_devices` | explicit Blender/device verification, no silent CPU fallback |
| `workload_frames` | identical numeric frame IDs; 1080x1920, Cycles32 |
| `render_wall_sec`, `end_to_end_sec` | measured on both devices, no omitted setup/teardown |
| `render_speedup`, `end_to_end_speedup` | denominators from identical paired workload |
| `frame_proof`, `source_proof`, `qa_status` | existing hard gates and image inspection |
| `chargeable_minutes`, `billed_usd`, `resources_deallocated` | actual receipt and cleanup verification |
| `decision` | `PASS_10X`, `REJECT`, or `INCONCLUSIVE` with reason |

**Pilot success:** native/source QA passes with no material visual regression, **same-workload** e2e speedup >=10.0x, cost within approved limits, and no leftover billable resources. Failure or missing evidence is **INCONCLUSIVE/REJECT**, not success. This protocol documents a future test; it is not an executed GPU benchmark or a 24-hour render deployment.
