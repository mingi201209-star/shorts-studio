# Episode 2 macro-mechanism 3D redesign — design (2026-10-24)

**Status:** proposed editorial/engineering design, not implementation or publication approval.
**Owner direction (Korean):** show the phenomenon and its components in much more detail than a car driving around; make one excellent finished film, manually upload it, inspect real audience reaction, reuse successful structure or pivot if reaction is poor.
**Code baseline:** draft PR #69 head `421862cb35456b0c60500f1cce0a18e0ada060a7` stacked onto PR #56 `82af1a3`. Proof #14 succeeded at this head after prior black-void failure; this is native sparse-frame proof only, not a completed film.

## Problem and intent

Prior 30-second English rumble-strip footage was rejected as boring: extended views of a moving sedan and road did not make the hidden mechanical explanation visible. Viewers should comprehend **what is milled, how a tyre touches the grooves, how repeated contact creates vibration, and why a driver should respond** without mistaking visual illustration for calibrated suspension physics. The first two seconds must already show tyre/actual recessed-milling contact rather than establishing-road filler.

**Launch lane remains:** Hidden Engineering of American Roads. This episode stays on shoulder rumble strips, one candidate film first, then market feedback. No new content factory or topic expansion in this design.

## Approaches considered

- **A. Existing audited car+road, native 3D macro/cutaway shots (selected).** Keep pinned CC0 sedan and existing geometry/renderer/QA, use fixed close-up cameras, selectively expose real milled surface profile and detailed wheel components. Least disruption, reproducible, and avoids unverified physics claims.
- **B. Full vehicle/suspension physical simulator.** More explanatory degrees of freedom but not affordable or validated for the current film; risks false contact claims and long rendering/debug.
- **C. Predominantly 2D diagrams or stock footage.** Fast but repeats the audience-rejected lack of convincing detailed native 3D. Can be used as temporary editorial references, not final visuals.

The user's latest '그래 @Superpowers' approves the direction to use detailed 3D explanations; exact engineering edits remain gated by proof and editorial acceptance.

## Existing contracts and exact scope

- Keep the six existing identifiers and 150-frames-per-shot ranges at 30fps:
  `hook_warning` 1–150, `road_cut` 151–300, `tire_contact` 301–450, `rumble_mechanism` 451–600, `shoulder_location` 601–750, `driver_response` 751–900.
- Retain project manifest structure (no extra required keys), `en-US`, `1080×1920`, 30fps, Cycles32, 900 distinct absolute-frame renders for final-original acceptance, exact pinned Blender/source checks and source provenance. This is **an episode-specific 30-second acceptance target**, not a new global content-length restriction.
- Keep original source SHA-256 `a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877`; Blender 5.0.1; never swap in unverified models or merge source frames from different renderer SHAs.
- No camera motion *within* a shot. Cuts may change the fixed camera to close-up or section view. The visual phenomenon itself moves.
- Do not alter existing black-void, framing, semantic CLIP, subtitle, audio, timing, final video, or original-motion thresholds downward; hard failures remain blockers, not xfail masks for confirmed frame defects.
- Keep lower black caption gutter with thin, stationary lower captions (not overlaying scene contact), no upper labels/titles; preserve actual TTS word times and recorded asset hash checks.
- Preserve manual review & manual YouTube upload. Never autonomously merge, publish, upload to R2, dispatch 900-frame workflow, purchase GPU, change billing, or enable background deployment.
- The local Android disk is not the location for new render artifacts; use pre-existing GitHub Actions artifacts for visual checks. No fresh full native render without scoped run/resource and cost approval.

## Six-shot visual story (concrete edit target)

| Frames | Visible change | Mandatory visual evidence | What to avoid |
| --- | --- | --- | --- |
| 1–150 `hook_warning` | Near-side **rotating tyre fills composition**; physically recessed groove passes directly beneath tread within 0–2s; by 2–5s show rhythmic repeated contact | Tyre/tread AND depressed pocket and some wheel assembly simultaneously visible from first frame; more than one meaningful contact beat over 5s; no black band, critical subject inside safety margin | Whole-car hero/wide road for first seconds; long static hold; logo/headline overlay |
| 151–300 `road_cut` | Fixed elevated angled view/cutaway of **actual asphalt surface cross-section**; smooth lane to one side, milled recesses on shoulder | Road profile geometry has cut depth beneath road datum and continuous solid substrate (not painted stripes or free-floating diagram); wheel in nearby context where feasible | Dark painted bars pretending to be cuts; empty void under camera |
| 301–450 `tire_contact` | Low fixed wheel-level **macro contact shot**, real rotating tread over successive milled pockets | Tight shot keeps contact and recessed groove visible at start/middle/end, as motion changes; native black-void gate fully passes | 118px black floor previously seen on 301, wheel occluding all contact, chopped tire |
| 451–600 `rumble_mechanism` | Explain vibration path from road contact into wheel/body with *visible* actual moving CC0 wheel assembly and bounded body motion | Repeated contact matches disclosed kinematic, non-calibrated bob; show mechanical wheel-to-body relation at real scale. If the CC0 source cannot substantiate internal suspension geometry, a separately reviewed schematic insert must be explicitly identified as illustrative, not passed off as source vehicle mechanics | Inventing plausible-looking-but-false detailed struts/energy wave propagation; simulated physics claims |
| 601–750 `shoulder_location` | Brief spatial wide shot to prove lane edge + milled shoulder placement | Smooth traffic lane, narrow milled strip, vehicle position all visible; **not** 5 sec of generic car motion | Wide road with no close-up evidence |
| 751–900 `driver_response` | Visual payoff: driver-initiated directional correction, not self-steering | Road groove warning and subsequent human correction are distinguishable; bounded heading follows lateral motion | Automated steering claim or magically autonomous turn |

**Narration scope:** keep six English beats and already stored TTS as starting point. After visuals pass, evaluate whether original words accurately describe revised geometry; only then propose copy/timing changes with sentence-complete lower captions, bounded silence and listening QA. This is NOT permission to reuse stale audio timing blindly.

## Stage/renderer architecture

Existing authoritative timeline and camera layout: `shorts_studio/factory/rumble_episode2.py` — pure Python exact-frame shot mapping and `camera_layout(shot)`. Existing renderer: `benchmarks/road_safety/render_rumble_episode2.py` — Blender imports timeline module, constructs actual recessed road mesh with 16mm groove depth, reuses original sedan and wheel pivots, animates global absolute-frame trajectory; sets camera only upon beat boundary. Visual QA: `shorts_studio/factory/rumble_native_shard_qa.py`, and movie QA: `benchmarks/road_safety/episode2_film.py`.

Design choice: add a small **pure-Python** `detail_stage(shot_id: str) -> str` in the timeline, mapping six current shot IDs to named shot treatment; keep existing ID/range/signature stable. Renderer uses the treatment for camera/visibility/road-section *without substituting the source mesh*. Do not add fake graphics inside the actual asphalt groove; make the real geometry visible via camera/light/cutaway substrate. If an actual suspension is absent from pinned CC0 mesh, stay with honest wheel-body motion until a separate source/provenance and new scope is approved.

The current `rumble-episode2-native-film.yml` hashes the renderer. Any changes invalidate its `RENDERER_SOURCE_SHA256` pin: update in a reviewed code PR after asserting the exact file SHA, keep `workflow_dispatch` only and unchanged exact-head check. Never automatically start it.

## Quality gates & staged proof

1. **Cheap logic/camera preflight:** tests for six treatments, fixed shot IDs/frames, first frame target, native geometry positions, tyre containment/safety margin at shot start/middle/end, road frustum/substrate coverage, no fabricated auto-steering, caption picture separation.
2. **Sparse inexpensive images:** local/GitHub existing preview route (450×800 / Cycles7) for editorial comparison only, never production certification. Review first 5s and contact/cutaway as a visual storyboard.
3. **Real independent native proof:** run existing isolated 1080×1920/Cycles32 sparse-frame workflow at exact commit for 6 shots (then targeted edge frames 1,150,301,450,451,600 if geometry warrants); retain per-image frame SHA, screenshot/contact sheet and automated black-void, tyre-contact, semantic and source checks. Any true black band is FAIL.
4. **Human editorial gate:** inspect representative first/middle/last positions. Criteria: 0–2s subject already legible, 2–5s meaningful new clue, visible groove depth, correctly bounded tyre, no static filler, plausible kinematics, narration matches the visual. Do not declare success from pytest alone.
5. **Only after separate render/cost authorization:** new **all 900** absolute native frames from one pinned SHA, independent proofs, assembly and actual final MP4+audio+caption QA, user hears/sees film and approves manual upload. Incomplete sparse proof is never a full original movie.
6. **After manual public release:** record 24h/72h/7d metrics (shown vs swiped, engaged views, average percentage/seconds viewed, retention curve, likes per engaged view, subscription actions and comments where available). Compare to the channel's own historical performance and comparable topics; do not treat a single small-sample spike as proof. If hook weak, replace opening visuals/voice; if midway weak, shorten repetitive explanation; if strong, reuse rendering assets and mechanism-focused shot language. Test 2–3 more neighboring road mechanisms before pivoting the whole series.

## Non-goals

No new generic Shorts platform; no engine rewrite, no R2/OVH changes; no external web services/paid models, auto-posting or ads; no false calibrated physics; no dropping 900-frame native acceptance or video QA; no reducing video quality to hit the five-minute cached-assembly number.

## Acceptance state at design time

Current PR #69 pinned SHA `421862c`; proof run #14 PASS and prior #13 FAIL at 301 proved the black-void guard is useful. The current sparse proof has **not** verified this new macro/cutaway treatment. Film status: **EDITORIAL HOLD / NOT READY TO PUBLISH**. Requirements in this design are future acceptance criteria, not completed work.
