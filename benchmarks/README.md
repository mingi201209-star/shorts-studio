# Isolated Blender CPU rendering benchmark (draft; not production)

Purpose: compare the **same real 3D guardrail scene** on the Samsung Android Termux Ubuntu ARM64 CPU and the GitHub-hosted Ubuntu x86 CPU **before** spending money on GPUs or hardware.

- Source: `benchmarks/guardrail_blender_scene.py`, copied and path-isolated from local `/root/us-roads-shorts-20261017/build_blender_guardrail_cc0_v3.py`.
- Asset: CC0 unbranded Innerscene sedan, [source](https://www.innerscene.com/tools/library/3d-parts/sedan-car-42109739), downloaded on CI only after validating SHA-256 `4cb896f740de4da871c1d87c4af2b734db3d1e8fac852e308f1fca03a63b25d3`.
- No credentials, API calls to paid rendering services, uploads to YouTube, merges, changes to existing CI quality gates or production paths.
- CPU: Ubuntu 24.04 on the GitHub-hosted standard runner, 4 threads. Uses the **official Blender 5.0.1 x64 release**, matching the phone's **Blender 5.0.1 ARM64** version, with SHA-256 verification (`8019580ee1b7262e505f4196a00237ccf743c88d205b38d34201510676e60b09`). Architecture, CPU model and Linux build still differ, so timings are operational rather than strict hardware benchmarks.
- Render: 3 frames (1,35,90) at 38% of 1080×1920, 8 Cycles CPU samples, plus one frame 42 at native 1080×1920 with 16 samples. Measurements in `benchmark.json` with frame hashes and exact time.
- Original phone benchmark for equivalent low-resolution scene: Blender 5.0.1 ARM64, around 10 seconds per frame at 38% and 8 samples. This is an empirical prior, **not** a prediction of x86 performance.
- Rendered images and JSON are retained for 3 days as PR workflow artifacts. A 3-second video/30-second publish-grade video is **not** produced by this benchmark.
- The animations depict **conceptual kinematics, not a validated crash simulation**. Visually convincing rail deflection and truthful motion still fail editorial quality criteria in the initial experiment; a fast render alone does not solve that.
- Workflow timeout 18 minutes to cap resource use; jobs on a public repository's standard GitHub-hosted runner are generally free, but repository/account policies and allowed job execution still apply.

**Pass/fail:** report real measured runtime, visual inspection of sample frames, and document the CPU option's expected scaling. Keep existing engine unchanged. If slow, investigate a quoted/tested GPU plan; don't activate a paid provider.

### First CI attempt and remediation

Initial hosted Ubuntu distro Blender failed before any render because its package was **built without OpenImageDenoiser**. Rather than disabling denoising (a quality change), the benchmark now downloads the **checksum-verified official Blender 5.0.1 Linux x64 build**, retaining Cycles denoising and the same quality settings as the phone. No conclusion about relative speed should be drawn from that failed first run.
