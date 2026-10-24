# Episode 2 Macro-Mechanism 3D Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a reviewable, mechanism-first 30-second episode 2 that uses detailed native 3D tyre/road groove macro and truthful section views rather than monotonous whole-car travel.

**Architecture:** Extend the existing six-beat pure-Python timeline and Blender scene renderer in tightly scoped slices. Keep the pinned CC0 vehicle, global frame-accurate trajectory, manual original-film workflow and all current QA gates; judge actual sparse rendered images before any original 900-frame run.

**Tech Stack:** Python 3.11, pytest, Ruff, Blender 5.0.1 Cycles, image inspection/Pillow, ffmpeg, existing GitHub Actions. No new network/model dependencies.

**Spec:** `docs/superpowers/specs/2026-10-24-episode2-macro-mechanism-redesign.md`

## Global Constraints

- Review base: PR #69 head `421862cb35456b0c60500f1cce0a18e0ada060a7`; parent PR #56 current head `82af1a3103325229f524f392637bd8d82d902fa4`. Never replace base with older PR #62 camera settings.
- Exactly six IDs and frames `1..150,151..300,301..450,451..600,601..750,751..900`; source `a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877`, 1080×1920, Cycles32, 30fps, 900 **fresh** original frames only at separately approved final gate.
- Existing geometry has 16 mm recessed shoulder grooves, 8 mm stylized bounded body bob; do not invent calibrated suspension physics or auto-steering.
- Fixed camera during each beat, no top overlay, thin fixed captions in black lower gutter, source/TTS/semantic/final-video/native QA unweakened. Actual black void = fail.
- Preserve `HOLD_UNTIL_FINAL_QA`. No merge, publishing, YouTube/R2 upload, GPU purchase, or dispatch of the fresh 900-frame workflow without separate owner approval; no filling the Android phone.
- Every implementation task is test-first; compare exact-head CI after PR; no "success" claim without actual output evidence. Do not rewrite unrelated R2 branches.

## File Map

- **Modify** `shorts_studio/factory/rumble_episode2.py`: pure shot treatment selector and existing camera layout. Stable six-shot schema and absolute motion APIs remain.
- **Modify** `benchmarks/road_safety/render_rumble_episode2.py`: fixed shot visual staging, cropped native wheel macro and native groove-section presentation; retain existing CC0 mesh and 16mm recess.
- **Modify** `examples/factory/rumble-episode2-30s.json` only if verified captions/narration genuinely need a matching editorial edit; original schema unchanged.
- **Modify** `tests/test_factory_rumble_episode2.py`: treatment mapping, framing, camera safety, explanation continuity tests.
- **Modify** `tests/test_factory_rumble_native_shard_qa.py`: actual image/geometry validity checks if visual treatment adds new proof fields; never replace existing checks.
- **Modify** `docs/rumble-episode2-production.md`: exact renders, comparison screenshots, evidence, remaining blockers and editorial verdict.
- **Modify** `.github/workflows/rumble-episode2-native-film.yml` only when renderer source changes, to update its exact `RENDERER_SOURCE_SHA256` independently; preserve manual dispatch.
- **No** new simulator module unless the existing renderer cannot express the required visual treatment cleanly.

## Review Focus

1. **First frame genuine contact:** shot 1 shows recessed pocket, tyre tread and rotating assembly at native 9:16; fails if macro shot loses either tyre or depression.
2. **Road-section honesty:** shot 2 shows substrate and the milled surface below grade rather than dark painted stripes; fails if cut looks like a void.
3. **Boundary camera stability:** first/middle/last absolute frame for each beat must remain in native frustum with ground coverage; no leading/trailing zoom, out-of-frame tyre or black band (previous frame 301 failure).
4. **Nonphysical insert:** scene 4 cannot present fabricated suspension geometry as though sourced from the pinned CC0; explicitly mark any illustrative schematic in review, or use only verified wheel/body geometry.
5. **True original 900-film gate:** fake/cached/preview/synthetic frames or TTS mocks cannot establish full native film readiness, even if tests are green.

---

### Task 1: Pin the current checkpoint and six detailed shot treatments

**Files:** `shorts_studio/factory/rumble_episode2.py`, `tests/test_factory_rumble_episode2.py`, `docs/rumble-episode2-production.md`

**Interfaces:**
- Consumes: current `SHOT_IDS`, `load_episode(Path)`, `shot_for_frame(episode, frame)`, `camera_layout(shot)`.
- Produces: `detail_stage(shot_id: str) -> str`, mapping IDs to `"macro_warning"`, `"road_section"`, `"rolling_contact"`, `"wheel_body_vibration"`, `"shoulder_context"`, `"human_response"`.

- [ ] Step 1: Add a failing parametrized test named `test_episode2_detail_treatment_is_exhaustive_and_ordered`, asserting exact six mappings, unknown ID raises `ValueError`, existing 150-frame ranges and manifest fields unchanged.
- [ ] Step 2: Run `pytest tests/test_factory_rumble_episode2.py -k detail_treatment -q`. Expected: FAIL from missing `detail_stage`.
- [ ] Step 3: Implement the pure mapping without touching `travel_x`, `rumble_displacement` or `validate_episode`.
- [ ] Step 4: Run `pytest tests/test_factory_rumble_episode2.py -q` and `ruff check shorts_studio/factory/rumble_episode2.py tests/test_factory_rumble_episode2.py`. Expected: PASS; no newly skipped/xfail tests.
- [ ] Step 5: Commit `feat(episode2): pin detailed six-beat visual treatments`. Document this is a shot plan, not a rendered image.

### Task 2: First 0–5s native tyre/groove macro camera (no unrelated engine rewrite)

**Files:** `shorts_studio/factory/rumble_episode2.py`, `benchmarks/road_safety/render_rumble_episode2.py`, `tests/test_factory_rumble_episode2.py`

**Interfaces:**
- Consumes: `detail_stage("hook_warning") == "macro_warning"`, `camera_layout(shot)`, existing `Front_tire`, existing milled-shoulder Blender mesh.
- Produces: camera parameters for a fixed hook shot preserving physical tyre groove visibility in frames 1, 75, 150.

- [ ] Step 1: Add `test_hook_macro_camera_contains_wheel_and_milling_at_1_75_150` and `test_hook_has_no_per_frame_camera_translation` in pure analytic camera bounds. Do not loosen the existing 90% safety margin / minimum road-plane clearance; retain any existing strict xfail as a separately documented unresolved numerical warning until evidence resolves it.
- [ ] Step 2: Run these tests; Expected: RED if hook lacks requested safe macro composition.
- [ ] Step 3: Make minimal camera-layout/render-only adjustment using existing fixed per-beat camera branch. Keep original detailed CC0 mesh; no source frame duplication or cutout cheat.
- [ ] Step 4: Run `pytest tests/test_factory_rumble_episode2.py -q` + `ruff check shorts_studio/factory/rumble_episode2.py benchmarks/road_safety/render_rumble_episode2.py`. Expected: PASS; no wider exclusions.
- [ ] Step 5: Produce small sparse **preview-only** frame 1, 75, 150 under approved existing preview route if available; human compare to old same-frame reference. A preview failing visual review returns to RED; it does not authorize native film.
- [ ] Step 6: Commit `feat(episode2): stage an immediate readable contact macro`.

### Task 3: Truthful 3D road cross-section and shot 3 tyre rolling contact

**Files:** `benchmarks/road_safety/render_rumble_episode2.py`, `shorts_studio/factory/rumble_episode2.py`, `tests/test_factory_rumble_episode2.py`, `tests/test_factory_rumble_native_shard_qa.py`

**Interfaces:**
- Consumes: Task 1 `detail_stage`; `railbed_road(asphalt, groove, depth=0.016, ...)` and existing `scene.frame_set(absolute_frame)`.
- Produces: visibly milled **below grade** groove section in `road_cut`, visible moving actual wheel+grooves in `tire_contact`, with unchanged absolute-frame continuity.

- [ ] Step 1: Add failing tests `test_road_cut_uses_below_grade_solid_geometry`, `test_tire_contact_contains_wheel_and_real_groove_at_301_375_450`, and `test_sections_never_enable_blank_background_bands`. Use real world coords/mesh assertions, not weak object-name-only checks.
- [ ] Step 2: Run focused tests; Expected: at least the new missing-behavior assertions FAIL.
- [ ] Step 3: Implement a restrained road profile reveal within existing source road geometry and safe substrate, with fixed camera layouts. Do not draw faux dark bars; do not globally hide source vehicle/geometry or invent a physics engine.
- [ ] Step 4: Run focused suite `pytest tests/test_factory_rumble_episode2.py tests/test_factory_rumble_native_shard_qa.py -q` and Ruff; Expected: PASS; existing image QA and frame uniqueness intact.
- [ ] Step 5: Compare preview-only first/middle/last images for shots 2 and 3; if road section is ambiguous or frame 301 has black void, mark BLOCKED and revise shot geometry.
- [ ] Step 6: Commit `feat(episode2): reveal real recessed road section and tyre passage`.

### Task 4: Honest vibration path and manual response without fake suspension simulation

**Files:** `benchmarks/road_safety/render_rumble_episode2.py`, `tests/test_factory_rumble_episode2.py`, `docs/rumble-episode2-production.md`

**Interfaces:**
- Consumes: `rumble_displacement(frame)`, actual four wheel pivots, original detailed CC0 hierarchy, `lane_return_offset`/`lane_return_heading`.
- Produces: shot 4 visibly shows wheel-to-body relationship using real source meshes; shots 5–6 preserve road shoulder context and human response.

- [ ] Step 1: Write RED tests `test_mechanism_motion_bounded_to_original_disclosure`, `test_driver_correction_begins_only_after_frame_750`, `test_no_invented_suspension_source_claim`, and `test_shoulder_context_identifies_edge_and_milled_band`.
- [ ] Step 2: Run new tests; Expected: verify RED for newly required visualization/provenance, not merely force an existing passing test to fail.
- [ ] Step 3: Stage the real wheel/body movement for shot 4 and separate the context/payoff shots from generic whole-car driving. If source suspension internals are missing, DO NOT invent an unlabeled source-accurate cutaway; record illustrative alternative as deferred user editorial choice.
- [ ] Step 4: Run `pytest tests/test_factory_rumble_episode2.py -q` and Ruff; Expected: PASS, unchanged finite movement and steering truth.
- [ ] Step 5: Check six-beat sparse previews for unique mechanism changes; reject repeated static road footage.
- [ ] Step 6: Commit `feat(episode2): expose bounded vibration and human correction`.

### Task 5: Word-aligned English audio, captions and final QA parity

**Files:** `examples/factory/rumble-episode2-30s.json` (only if approved editorial changes), `benchmarks/road_safety/episode2_film.py`, `tests/test_factory_rumble_episode2.py`, `tests/test_factory_rumble_film_shards.py`, `docs/rumble-episode2-production.md`

**Interfaces:**
- Consumes: verified six native story beats; existing stored English voice, word timings, `caption_groups(text)`, original semantic + final video QA.
- Produces: a narration/caption edit proposal with exact source IDs and timings or evidence that existing copy matches visuals.

- [ ] Step 1: Write/extend failing tests if narration no longer matches first 0–2s or sentence-grouped captions cover the tyre or split sentences; assert picture/gutter separation.
- [ ] Step 2: Run focused tests; Expected: RED only for a demonstrated mismatch, otherwise retain unchanged audio/manifest.
- [ ] Step 3: Make the smallest copy/audio/caption adjustment, if needed. No TTS mock can be claimed as a production voice; verify stored capture provenance.
- [ ] Step 4: Run `pytest tests/test_factory_rumble_episode2.py tests/test_factory_rumble_film_shards.py -q` and Ruff; Expected: PASS with zero downgraded final QA gates.
- [ ] Step 5: Record subjective listening issues separately (robotic delivery, silence, pacing) and block release until editor hears actual sound.
- [ ] Step 6: Commit only if changed; otherwise record no-change decision with evidence.

### Task 6: Exact-SHA native sparse QA and editorial acceptance

**Files:** `.github/workflows/rumble-episode2-native-proof.yml` (only if a new targeted check is required), `.github/workflows/rumble-episode2-native-film.yml`, `docs/rumble-episode2-production.md`, `tests/test_factory_rumble_episode2.py`.

**Interfaces:**
- Consumes: current renderer exact byte SHA-256, six beat IDs, original Cycles32 proof and strict black-void/semantic/tyre framing QA.
- Produces: SHAs, original native frame evidence, 6-shot contact sheet, blocker list, editorial accept/reject.

- [ ] Step 1: Add/update tests asserting the *manual* film workflow's `RENDERER_SOURCE_SHA256` matches the new render file after any edit, no auto dispatch, true 900/30/1080×1920/Cycles32; sample proof runs cannot satisfy full-movie proof.
- [ ] Step 2: Run tests expecting FAIL for stale renderer SHA pin; update exactly the hash computed from this commit's reviewed renderer bytes, not a guessed/stale value.
- [ ] Step 3: Run targeted local pure tests and full suite `pytest -q`, `ruff check ...`; Expected: all pass except already documented/justified skips/xfails; **do not convert newly failing real-image checks to xfail**.
- [ ] Step 4: Push isolated Draft PR stacked on exact #69 head, observe GitHub CI and native 6-shot proof; inspect native 1080×1920 Cycles32 image artifacts including frames 1 and 301, plus last/mid positions where cost and workflow permit. Strict failure blocks here.
- [ ] Step 5: Compare actual 6-shot filmboard versus owner's desired mechanism detail. No claim "ready" until visible frame evidence, clear macro + real cutaway, no black void, and human creative review are recorded.
- [ ] Step 6: Commit review report with exact renderer/manifest/input SHAs and blockers. Leave Draft until further approval.

### Task 7: Separate 900-frame production decision and market feedback contract

**Files:** `docs/rumble-episode2-production.md` only until explicit production authorization; later `.github/workflows/rumble-episode2-native-film.yml` run artifact metadata and review report as approved.

**Interfaces:**
- Consumes: Task 6 green exact-head native sparse proof, editor accept decision, actual resource/time/cost estimates.
- Produces: explicit final-render go/no-go and post-manual-upload evidence rubric; **no automatic action**.

- [ ] Step 1: Record independent 900-frame cost/resource estimate, SHA pin, retained native QA gates, available artifact space and user approval status. Expected: no run if any proof/cost approval missing.
- [ ] Step 2: After separate approval only, use existing manual workflow's `workflow_dispatch` exact head; NEVER substitute cached frames or preview proofs; verify all 900 original frame records, final MP4, H.264/AAC, English TTS, captions, CLIP and final-video QA.
- [ ] Step 3: Obtain actual human visual/listening approval; leave automatic YouTube upload off.
- [ ] Step 4: After owner manually posts, log 24h/72h/7d impressions, shown-vs-swiped, engaged views, retention, average view duration and feedback; compare to channel baseline. Recommend reuse, hook edit, mid-story edit or new topic. No claims without the observed analytics.

## Self-review of plan boundaries

Each task changes one independently reviewable concept; Tasks 2–4 depend on Task 1's `detail_stage` only, Task 5 uses completed storyboard visual proof, and Task 6 consumes the exact renderer hashes from Tasks 2–4. Task 7 is manually gated and is not an instruction to run a 900-frame workflow now. The five Review Focus risks have tests or explicit human review in their owning task. Existing PR #69's live changes must be rechecked before any implementation branch is created; this plan references its exact captured baseline and must not silently override later fixes.
