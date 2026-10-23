# Episode 2 — shoulder rumble strip alerts (EN, 30 seconds)

## Current review checkpoint — 2026-10-22

The episode remains incomplete. This checkpoint is the current state; dated
inspection entries below preserve earlier states and do not imply approval.

- Authorized branch: nightshift/episode2-editorial-20261022.
  HEAD:82647f3a53f084a94c802ca4c186f0ce6b9a9c74; four modified files, no commit.
- QA package: finite motion/camera evidence, all decoded pixels unique within
  each shard, consistent finite positive per-frame render times, and the
  existing pilot black/empty-image gate.
  Last full suite:550passed/1skipped in461.35seconds; code hashes match that run.
- QA SHA256:7b7088dc7e373aa41665177eb812c45c409a41125fa9cf25ccda426de0aac709
  Tests SHA256:e7f217ad301acf321ef4a2f71da47823083e42ff50f574ab1199b0067e445d2d
- Episode2 tests SHA256:b11c0859f7377ef7d8672a46b06303d5ce50b58497fb07f160e4ea5d27737c2b
- Stored speech binaries: six WAV/MP3/timing hash sets and actual PCM format,
  word intervals and tails verified by regression tests; subjective listening remains pending.
- Caption candidate: the copyable SRT below has31cues/88words, unchanged provider
  word boundaries and100ms offset. Real word-boundary coverage and the existing
  62px DejaVuSans/900px line-width rule are regression-tested. It is UNAPPLIED
  and has not been viewed.
- Final-film QA integration is still incomplete: episode2_film.py performs
  technical checks but does not call final_video_qa. Its technical_status PASS
  cannot stand in for the requested strict semantic/video QA. The shared
  verify_title_visible check expects a top title, which conflicts with this
  episode's explicit no-top-title requirement; shared layout checks also use
  fixed picture/gutter coordinates. Preserve applicable original checks and
  thresholds while explicitly mapping them to the approved episode layout.
  Do not disable gates wholesale or count synthetic tests as final-MP4 proof.
  Source review only: assembler SHA256
  b277d04ff413e678b141ea5816f415a16dc89993e0625aae6ea54557d0ccc348;
  final_video_qa SHA256
  a17ff0b589cdd490f530634a6f35315a3b61075f08865b83fc2e75ae4d9c5b0b.
- Core blockers: renderer/assembler edits returned "Path excluded"; commit
  returned "Use a fresh managed branch first"; CI detail access required a
  managed branch. Do not change the owner-authorized branch or bypass guards.
- Last verified PR56 baseline smoke39792010308, tests39792023585/39792010339 and
  six single-frame native proof39792010470 completed SUCCESS; the latest overview confirms these terminal results.
  No replacement run was launched.

Resume only through an approved tool route on this same branch: measure
near-side tyre world coordinates/bounds; correct and visually compare the hook
at1,25,132,150; then inspect the six shots. Native single-frame checks must use
explicit --start N --end N, because --frame-list is preview-only. Recheck free
budget/disk before any render. Pin renderer, timeline, manifest, Blender and
source inputs before accepting reused frames. Integrate the31-cue candidate
with thin lower captions and actual black picture-exterior space, then verify
audio, original semantic/video gates, all900native frames and manual edit approval.

An asynchronous clarification now asks which approved managed tool route can
perform these operations without a new branch or policy change. No answer has
been received yet. The latest independent QA update and full test result are recorded below;
existing scene work and the complete candidate SRT are preserved.

**Launch lane:** Hidden Engineering of American Roads. This is the second of seven initially agreed topics, not a generic new-topic engine.

The source is an authored original CC0 Innerscene sedan packed into the hash-pinned guardrail Blender scene. It must be verified at the exact SHA-256 referenced in the manifest. Animated 3D is an explanatory slow-motion demonstration, **not an engineering tire-contact solver**.

## Fixed 30s shot plan

Each of six segments has 150 authored native frames at 30fps (total exactly **900** at 1080×1920 Cycles32). Distinct visual stages:

1. Hook (0–5s): visible near-side tyre contact with recessed milling pockets from the opening frame; tyre and groove are the focus, with enough nearby body to read the warning response
2. Real shoulder milling, not painted stripes
3. Rotating tyre crossing actual road depression geometry
4. Audible/tactile vibration explained by contact motion, without physically spurious sound waves
5. Wide shoulder location and stripe context
6. Driver still must take corrective action, no self-steering false claim

**Evidence:** FHWA longitudinal rumble strips and stripes, cited in the manifest. **Narration:** the current manifest contains 88 English words across six 5-second segments (16/14/14/13/15/16 words). The stored captures use one voice, en-US-AndrewNeural, across those segments. Binary provenance, PCM format and word-boundary checks pass; naturalness, final assembled audio and synchronized thin lower captions on black outside the actual picture still require listening/viewing approval. No top titles. These are requirements, not evidence of completed footage.

## Rendering and release gates

A production renderer must use **absolute global frame numbers** and the same deterministic car trajectory even when the shots are independently rendered by GitHub Actions shards. No per-shard reset, no loops, no static-frame cloning. Proof records must show the pinned car scene SHA, Cycles 32, 1080×1920 and 30fps.

The manifest itself is a **plan**, not finished footage. Do not increase weekly completed inventory until a real 900-frame 30-second English MP4 passes source/proof/frame QA, audio, captions and human visual assessment. YouTube uploads require user manual action.

Check timing contracts:

```bash
python -m shorts_studio.factory.rumble_episode2 --manifest examples/factory/rumble-episode2-30s.json --start 1 --end 30
```

## Actual isolated full-quality frame gate

The source binary verified by visual review is NOT the different 7MB guardrail scene from an older Actions run. It is preserved as a checksum-verified public GitHub prerelease asset:

https://github.com/mingi201209-star/shorts-studio/releases/tag/rumble-episode2-scene-a82e0582-20261018

The native render smoke uses the exact hash-pinned Blender 5.0.1 executable, the source asset with SHA-256 a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877, fixed native 1080x1920/Cycles32, and two separately calculated moving frames. No new footage uses preview/upscaling/interpolation. QA checks exact numbered PNGs, image decode, each frame hash, absolute trajectory, original model, camera evidence, and no upload authorization.

The earlier six 450x800/Cycles7 storyboard frames passed creation but FAILED editorial expectations (too much zebra-striping). The final revised narrow shoulder rumble groove geometry keeps the rest of the driving lane level. This is still not a release-ready 30-second film; final TTS, safe subtitles, source evidence review, edit pacing and 900 unique native frames are outstanding.


## Full-film implementation — 2026-10-19

All six native Cycles32 storyboard cameras were rendered in run39210381736 at f307f067a424c9b97cb85f729348155d9c9308d8 and visually inspected. Existing test/smoke checks also passed. This remains editorial review, not approval.

The isolated full-film workflow uses thirty contiguous 30-frame shards with absolute global indices1..900. Existing native/source/camera QA remains intact. FFV1 carries every source RGB pixel losslessly; each shard and final assembly independently compare decoded RGB SHA256 values. The final H264 encode happens once after caption compositing. Missing/duplicate frames, changed shot cameras at shard joins, different source hashes or reduced Cycles/resolution fail the assembly.

English narration uses six real en-US-AndrewNeural +5% captures, raw provider MP3 provenance plus exact PCM tails and genuine word boundaries. The script is88words with32measured caption cues. No speech acceleration, invented alignment or upper overlays. Local AAC preflight maximum detected silence0.710708s,total4.839603s at-35dB,d0.3; original <=0.9s/max and <=5s/total gates retained. Comfort still needs subjective listening.

Custom code is episode-specific integration of existing factory source/timeline/shard QA, timing types/validation, prior audited English-caption layout, FFmpeg FFV1/libx264/ASS and Pillow font measurements; no alternative media engine or provider is introduced. Source reference was repaired from404 to the current official FHWA two-lane-roads page in the manifest. No physical tire solver or upload approval is claimed.

Full workflow writes native frame render times and final encode time. They measure stages, not a proven five-minute total. A managed worker cannot resume this completed campaign or configure a different root through the installed manager API; the authorized operator is working in this isolated PR56 worktree. Manager state/policy/root were not modified.


## Recovery from measured native job timeouts

Original run39211610129 produced real accepted30-frame shards, but eight slow ranges(151,181,391,421,481,511,541,571) reached the45-minute runner limit. Frame151-job logs show roughly102seconds/frame, stopping after176of180. These partial unexported images are not counted as accepted footage. Other original ranges continue independently and are preserved.

Recovery renders ONLY those terminal failed ranges as24ten-frame jobs after a live job/artifact nonoverlap guard. It does not restart source jobs that are still active. After initial recovery, a planning job waits for the original run to become terminal, unions old30/new10 artifact coverage, and schedules any remaining truly missing ten-frame blocks. Independent accepted shards are retained even if a different job fails; no continue-on-error or quality-gate bypass is used.

Assembly still requires exactglobal1..900, unchanged renderer/source hashes, native1080x1920/Cycles32, unique original/decodedRGB frames, all6fixed shot cameras, source mesh/wheel gates, measured English captions and original AAC silence gates. Mixed FFV1 segment timestamps are normalized to the authored global30fps clock with setpts=N/(30*TB), without creating or dropping source frames. Report records reused/new counts and the original cache run.

Regression:31focused tests pass, including missing/overlapping/partial/oversized/mismatched mixed-span rejection; Ruff clean. Workflow YAML and embedded Python parsed; isolated coordinator fixtures verified zero-missing and late-missing paths and rejected overlapping or absent artifacts. Fixtures test scheduling only, not production rendering or user acceptance. Original production and new recovery outcomes must still be checked live.


## Editorial redesign after owner rejected moving-car-only film

Owner reviewed the complete old 30s English film and rejected its visual pacing.
The prior file remains a technically verified artifact, but NOT an editorially
accepted upload candidate. On the existing draft PR branch, the new candidate:

- Speeds up actual global tyre/groove crossings (8.4m vs prior 4.6m over 900
  frames), while keeping all 900 independently computed native frames.
- Begins with a fixed-camera tyre/groove detail and uses distinct contact
  angles before the wide road/driver shots.
- Adds a bounded 8mm uncalibrated illustrative vibration and a partial manual
  lateral lane correction with matching vehicle heading; NO road autosteering.
- Reuses the hash-pinned CC0 vehicle, but paints only its original blue body
  material sapphire; leaves wheel, glass and chrome materials untouched.
- Preserves six real five-second English narration captures, measured lower
  captions, original 1080x1920 Cycles32 production settings and all QA gates.

Evidence: focused test 14 PASS, full existing tests 479 PASS/1 SKIP,
Blender5.0.1 source SHA a82e0582... verified; FIVE 450x800/Cycles7
old-framing sparse images and THREE revised-color sparse preview images rendered
and visually inspected. Preview QA is NOT full native-quality approval.

The prior 900-frame artifact was produced by the OLD renderer/source timeline.
**Never reuse its native frames under the changed renderer SHA** and never claim
this redesign has a new completed 30-second MP4. A new full original-frame
render, audio/video/caption QA and subjective editorial check are still pending.
Keep PR draft; do not merge, upload, spend or downgrade QA.


## Managed inspection — 2026-10-22 (not render approval)

Inspected isolated editorial HEAD 82647f3a53f084a94c802ca4c186f0ce6b9a9c74;
initial diff clean. Root AGENTS.md and CLAUDE.md returned ENOENT.
CI detail access returned "Managed branch required"; do not bypass that guard.

Before the next native render, resolve these source findings:

- Camera fitting selects Front_tire / Rear_tire by name without verifying
  world-space y against the milled band (-1.3499 to -0.7001). Measure the pinned
  scene's tyre centers before choosing the near-side wheel.
- Camera fitting samples a wheel bound box after current-frame wheel rotation.
  Test fixed-camera equality across separately started shards (hook frames
  1, 31, 61, 121). An off-center source bound box could shift the target.
  This is a hypothesis, not a reproduced camera failure.
- Renderer proofs and assembly pin the renderer script hash, but camera layouts
  live in the separately imported shorts_studio/factory/rumble_episode2.py.
  Add timeline and manifest content hashes to new proofs and enforce them in
  native shard QA and assembly before frame reuse. Renderer-only hashes cannot
  establish unchanged camera source when only the timeline changes.
- Native six-shot proof push triggers name only the PR56 production branch.
  Generic tests on this isolated branch do not establish new native proof.

Implementation attempt was blocked: workspace_edit returned "Path excluded"
for both benchmarks/road_safety/render_rumble_episode2.py and
benchmarks/road_safety/episode2_film.py. The temporary QA/test changes were
restored to their original SHA256 values (3f5612f8... and c38fc074...);
only this documentation remains modified. No incomplete production gate was
left behind.

Caption source inspection also found that assembly applies ASS directly to the
full native picture, with no black caption gutter compositing. The current
62px caption style uses a 325px bottom margin. The requested thin captions on
black outside the actual picture therefore still require implementation and
visual QA; this inspection did not play audio or inspect rendered captions.

Next: provenance regression tests before implementation; measured near-side
wheel targeting; genuine hook comparison at frames 1, 25, 150; then six-shot
native visual inspection. Full900 rendering remains a separate resource-checked,
zero-new-spend operation. No new render or visual acceptance is claimed here.


### New full-render operation plan (not dispatched)

Use a single exact editorial commit only after native visual acceptance.
Fingerprint the pinned .blend, renderer, imported timeline, manifest and Blender
binary before generating new frames. Cache keys must include all these inputs;
old proofs lacking an input hash cannot be inferred compatible. Preserve their
artifacts but exclude them from the new candidate.

First measure startup and native frame times per accepted shot using the sparse
proof operation, without starting a full film. Estimate remaining runner time
from missing frames per shot and measured per-shot timing; account for startup,
lossless encoding, artifact transfer and final assembly separately. Historical
102s/frame is timeout evidence, not a fresh cost measurement or spend approval.
Check actual available free CI budget, disk guard and exact-head checks before
dispatch. No new paid compute and no Android900-frame render.

The coverage planner must inventory accepted artifacts without overlaps, reject
mismatched or incomplete provenance, and create only missing contiguous ranges
within the existing30-frame maximum. On the first redesigned film no old
renderer frames are reusable. A terminal failure must preserve accepted ranges;
retry only uncovered ranges after checking live jobs to prevent duplicates.
Assembly still demands exact1..900,900 unique decoded native images, unchanged
per-shot cameras, Cycles32 and original1080x1920, measured narration/captions,
original semantic/video gates, then manual viewing and edit approval.


Managed tests returned exit_code0: 482 passed,1 skipped,483 collected,
430.05seconds (Python3.14.4 / pytest9.1.1). The run began before the temporary
QA patch; collection reported the original11native-shard tests, so it is a
baseline result, not validation of the unshipped provenance changes. Production
QA and test files were restored byte-for-byte to their initial hashes.
No Ruff result, new native images, audio listening or final-film QA was produced
in this managed turn. PR56 smoke run39792010308 was last observed IN_PROGRESS;
terminal status could not be established through the guarded CI detail tool.


## Independent native-proof validation — second managed turn, 2026-10-22

The previous blocked provenance implementation remains unshipped. A separate
QA correction now rejects non-finite or non-numeric absolute_x_m and malformed
camera evidence (three finite location values, three finite rotation values,
and a finite positive orthographic scale). Booleans and numeric strings cannot
stand in for numbers. The original1e-6global-motion tolerance and every existing
resolution/sample/source/image gate remain unchanged. Regression tests were
written before this implementation;19invalid-position/camera cases were added.
This does not establish visual quality or tyre contact, and does not modify the
excluded renderer or film assembler. Managed tests completed with exit_code0:501 passed,1 skipped,502collected
in433.97seconds (Python3.14.4 / pytest9.1.1). All30native-shard QA cases pass,
including the19added regressions. No Ruff run or native render is claimed.

### Textual narration/caption timing audit (not listening approval)

Read all six provider timing JSONs and compared their workspace SHA256 values
with capture.json; all six match. Normalized timed words and stored narration
match the manifest. There are88words and32existing three-word caption cues.
Rates below divide word count by the span from first word start to last word
end, not the full five-second shot. They identify listening targets, not an
objective verdict on vocal warmth or naturalness.

| Shot | Words | Spoken-span words/minute | Final-word end within shot |
| --- | ---: | ---: | ---: |
| Hook | 16 | 222 | 4.416666s |
| Road cut | 14 | 194 | 4.428583s |
| Tire contact | 14 | 190 | 4.511916s |
| Rumble mechanism | 13 | 177 | 4.511916s |
| Shoulder location | 15 | 202 | 4.571416s |
| Driver response | 16 | 229 | 4.285708s |

The existing100ms shot offset puts the shortest caption, "time", at
29.040458..29.385708s (0.345250s). Other short final cues are "car"
(0.392875s) and "shoulder" (0.476208s). Maximum inter-cue blank interval
is0.690459s; this is caption timing, not measured audio silence.
Shot6's fixed three-word grouping produces "for you The", crossing a sentence
boundary. A future permitted assembler edit should split at real punctuation
and recheck cue readability without inventing word alignment, changing spoken
audio speed, or claiming the current caption gutter requirement is satisfied.
No binary audio hash, playback, font-width, rendered-caption or AAC silence
verification was performed in this textual audit.


Verified input hashes for this QA change:
- shorts_studio/factory/rumble_native_shard_qa.py:
  a5adaf07fbc39db88cc0dca960f73c187a6edd294079d3743665b60767432c79
- tests/test_factory_rumble_native_shard_qa.py:
  ba67a06cc24eee917ebc5f4181a620f283cd99dd84794398eb6b64ffeff3c323

Changes remain uncommitted on the authorized isolated branch at82647f3a53f084a94c802ca4c186f0ce6b9a9c74.
Current overview returned "Open PR/CI lookup failed". No guarded CI detail
retry, branch rename, excluded-file edit retry, push, merge, render dispatch
or new spend occurred in this second turn. Next useful visual action remains
measured near-side hook targeting and real1/25/150comparison when the required
renderer access and native proof operation are available.


## Decoded frame uniqueness — third managed turn, 2026-10-22

Native shard QA now hashes the decoded RGB pixels of every image and rejects
any repeated image within that shard, including nonadjacent A/B/A and
re-encoded PNGs with different file hashes but identical pixels. The existing
adjacent-frame comparison, source/file hashes, all original quality gates,
and final assembly's900-frame uniqueness requirement are retained.

Added three regression cases: nonadjacent byte-identical reuse, nonadjacent
pixel-identical reuse with altered PNG metadata, and three distinct valid
frames with no upload authorization. These are synthetic QA fixtures, not
rendered scene evidence. Tests were written before the implementation.
Managed workspace_check tests completed exit_code0:504passed,1skipped,
505collected in433.55seconds (Python3.14.4 / pytest9.1.1).
All33native-shard cases passed. No additional native render or Ruff run occurred.

Verified SHA256:
- shorts_studio/factory/rumble_native_shard_qa.py:
  9c838563a64d280ce25582b50d62743dfc258631e6fdcaaf3cbb2b950840e955
- tests/test_factory_rumble_native_shard_qa.py:
  5be54d0dfe0bb3b5046b5ae891fe777d5b0e4d884dc9697d091d5ab57d5c3c11

PR56 exact-head82647f3a53f084a94c802ca4c186f0ce6b9a9c74 overview now
reports smoke run39792010308 COMPLETED/SUCCESS at2026-10-22T14:22:58Z.
Test runs39792023585 and39792010339 and all six native proof jobs in
39792010470 also report SUCCESS. This supersedes the earlier unknown smoke
status. Those remote checks cover the committed baseline, not these uncommitted
QA changes, and six single-frame shots do not certify a30-second film.

Only the existing three changed files remain uncommitted on the isolated
editorial branch. No excluded-file edit retry, branch change, push, merge,
background worker, spend, or film render was launched. Renderer access and
genuine hook1/25/150comparison remain required before camera acceptance.


## Hook sweep diagnostic — fourth managed turn, 2026-10-22

This is a conditional orthographic projection calculation, NOT Blender footage
or a measured tyre-boundary result. Assume square pixels, the new camera's
default AUTO sensor fit in portrait, an upright look-at camera, and a rigid
wheel hub with no local drift. Real source bounds, sensor fit and pixel aspect
must still be checked in Blender. No source coordinates were measured here.

Inputs remain unchanged: hook anchor25, offset(1.2,-2.5,1.6), scale3.2;
1080x1920 output; x(f)=-4.2+8.4*(f-1)/899. For these assumptions:
horizontal span=3.2*1080/1920=1.8m;
camera right-axis x component=2.5/sqrt(1.2^2+2.5^2)=0.9015230575;
normalized horizontal hub position
u(f)=0.5+(x(f)-x(25))*0.9015230575/1.8.

| Frame | Relative world x (m) | Projected horizontal position u |
| --- | ---: | ---: |
| 1 | -0.224249 | 0.387686 |
| 25 | 0 | 0.500000 |
| 131 | 0.990434 | 0.996055 |
| 132 | 0.999778 | 1.000735 |
| 150 | 1.167964 | 1.084970 |

Under these assumptions the hub first exits at132; at150 it exceeds the
right edge by0.152947m in camera space. Tyre radius/width are not included,
so a hub-only pass would still be insufficient. The analytic formula was
independently checked against a normalized forward/right cross-product basis;
frame150projection agreed within1e-12. This does not confirm an observed
frame150crop or resolve the renderer's potentially rotation-dependent bound-box
target described above.

With the same orientation and scale, integer anchors44..107 keep only the
center inside across1..150. Anchor75, as an UNAPPLIED diagnostic, gives
u(1)=0.153697 and u(150)=0.850982, minimum center-to-edge distance0.268232m.
This does NOT establish room for the entire real tyre or groove context.
Retaining anchor25 would need at least scale3.743811 just for the hub,
which would widen the view; no scale or anchor change was applied blindly.

Next camera acceptance tests should measure the actual near-side tyre/contact
bounds and visible milled depression at1,25,150 (plus the critical exit region),
and compare fixed camera transforms across independently started shards.
Current anchor<=30/scale<=3.4 parameter tests do not prove full-hook coverage.
Native visual review must choose framing that meets BOTH immediate contact
and end-of-hook visibility while reducing body-panel dominance. Preserve fixed
shot cameras and all original resolution, sample and semantic gates.

Inputs inspected: renderer SHA256
1f6ceb692051d715a49a12627ba082ada01796aee066f2d89d185c9d7ec7866d;
timeline SHA256
1409ebdb339177d22bdfd38d9e262f3031070bd36fa19dfb9188ec0da8edd5b2.
No executable code changed this turn; the last full result remains504passed,
1skipped. No test rerun, excluded-file edit retry, native render, upload,
spend or permission change was used for this calculation.


## Render-time evidence consistency — fifth managed turn, 2026-10-22

Native shard QA now requires one finite positive render_seconds value per
frame, and an identical finite numeric value in that frame's original record.
Missing, incomplete, oversized, non-numeric, boolean, non-finite, zero/negative,
or inconsistent timing evidence is rejected. Tests were written first;
14timing regression cases were added. Existing successful fixtures now include
the timing fields already emitted by the unchanged pinned renderer.

Managed tests: exit_code0;518passed,1skipped,519collected in440.07seconds
(Python3.14.4 / pytest9.1.1), including all47native-shard cases.
Existing native/source/pixel/camera gates and motion tolerance remain intact.
QA SHA256:d5bccca705e962bbe2f5bc1a4b9e9cf272e97f9d416bf66302fe828ec25cc415
Tests SHA256:4b5695e98d37e72b945a06bbc4b2589b67b1f1606ebeca101799adfda5c6d727

Renderer elapsed time wraps bpy.ops.render.render(write_still=True), including
PNG output, but excludes setup, encoding, transfer and assembly. Validating
metadata consistency does not independently prove elapsed time or establish a
new measured full-render budget. No new benchmark, speedup, native render,
audio listening, final MP4 QA or Ruff result is claimed.

Only the same three files remain modified and uncommitted on the isolated
branch at82647f3a53f084a94c802ca4c186f0ce6b9a9c74.
This turn's overview lookup failed while parsing its JSON; the last verified
PR56 smoke status remains COMPLETED/SUCCESS for39792010308 at the baseline
head. No denied operation was retried and no branch/policy/spend changes or
render dispatch occurred. Next core action remains real hook1/25/150inspection
and camera repair through an authorized native proof operation.


## Commit guard outcome — sixth managed turn, 2026-10-22

Reviewed the complete pending diff and verified QA/test hashes still match the
518passed/1skipped run above. No code change or test rerun was necessary.
PR56 baseline tests, six native single-frame jobs and smoke39792010308 remain
COMPLETED/SUCCESS in the current overview; remote main remains
fcd20fd78851b18c550b1e433bee46ee34313c1d.

workspace_commit for the three pending files, with message
"fix(qa): reject invalid rumble native frame evidence", was rejected:
"Use a fresh managed branch first". No commit was created. Status afterward
still showed the authorized nightshift/episode2-editorial-20261022 branch at
82647f3a53f084a94c802ca4c186f0ce6b9a9c74 and the same three modified files.
The owner's current-branch-only instruction takes precedence over following
that suggested branch change. No fresh branch, rename, guard bypass, draft PR
or push was attempted. Root AGENTS.md and CLAUDE.md still return ENOENT.

The concrete pending package is the native-evidence QA correction plus tests
and inspection record. Core scene work still requires the permitted renderer
edit/native inspection path; preserving this package as a commit additionally
requires resolving the managed-branch guard conflict without changing policy
or leaving the owner-authorized branch. This is an external tool restriction,
not an indication that the episode or24-hour campaign is complete.


## Caption cue candidate — seventh managed turn, 2026-10-22

This is an UNAPPLIED text/timing candidate for manual review. It does not change
the excluded assembler, original voice captures, production ASS, or current
video. It must not be counted as rendered caption QA or release approval.

Regrouping uses exact existing provider word boundaries plus the unchanged
100ms shot offset. Shots2,3,5 keep the original three-word groups. Word counts
per cue in shots1,4,6 become respectively [3,3,3,3,4], [3,3,3,1,3],
[2,2,4,3,3,2]. All88words remain in order and occur once.
The final-shot sentence break after "you" is preserved: no "for you The".
There are31cues instead of32. The shortest raw cue increases from0.345250s
to0.428583s; maximum text length is26characters, below the existing31character
cap. Peak characters/second remains25.394791 (unchanged shot5), so this is not
a claim that all reading rates are approved.

Validation performed in this managed turn: all six timing-file SHA256 values
match capture.json; normalized timing words match stored narration; exact
per-shot index coverage; positive ordered nonoverlapping0..30s intervals;
sentence boundary preservation in shot6; serialized SRT independently parsed
back to31ordered cues and88words with no overlaps. SRT times round to nearest
millisecond; original sub-millisecond source timing is retained in the inputs.

No font-width measurement, AAC analysis, audio playback, thin-caption style,
black-gutter compositing, native image or human visual approval is established.
The hook's four-word final phrase may wrap into two lines under the current
assembler rule and needs actual visual inspection. Executable code is unchanged;
the last full suite remains518passed/1skipped. No denied operation was retried,
no new speech generated, and no commit, branch change or render dispatch occurred.

Copyable candidate (not wired into production):

```srt
1
00:00:00,195 --> 00:00:01,124
Those shallow grooves

2
00:00:01,136 --> 00:00:02,005
beside the lane

3
00:00:02,017 --> 00:00:02,731
warn you early

4
00:00:02,743 --> 00:00:03,279
when your car

5
00:00:03,290 --> 00:00:04,517
drifts toward the shoulder

6
00:00:05,207 --> 00:00:05,969
These are shallow

7
00:00:05,981 --> 00:00:06,933
cuts milled into

8
00:00:06,945 --> 00:00:08,124
the shoulder rather

9
00:00:08,136 --> 00:00:08,981
than lines painted

10
00:00:08,993 --> 00:00:09,529
on top

11
00:00:10,195 --> 00:00:10,719
As a tire

12
00:00:10,731 --> 00:00:11,779
rolls across each

13
00:00:11,790 --> 00:00:13,112
groove its contact

14
00:00:13,124 --> 00:00:13,743
with the road

15
00:00:13,826 --> 00:00:14,612
keeps changing

16
00:00:15,207 --> 00:00:16,279
That repeated contact

17
00:00:16,290 --> 00:00:17,195
creates a rumbling

18
00:00:17,207 --> 00:00:18,338
sound and sends

19
00:00:18,350 --> 00:00:18,957
vibration

20
00:00:18,969 --> 00:00:19,612
through the car

21
00:00:20,207 --> 00:00:20,719
The noise and

22
00:00:20,731 --> 00:00:21,767
shaking can quickly

23
00:00:21,779 --> 00:00:22,814
alert a distracted

24
00:00:22,826 --> 00:00:23,826
or drowsy driver

25
00:00:23,981 --> 00:00:24,671
leaving the lane

26
00:00:25,195 --> 00:00:25,743
These grooves

27
00:00:25,755 --> 00:00:26,374
cannot steer

28
00:00:26,386 --> 00:00:27,112
your car for you

29
00:00:27,517 --> 00:00:28,195
The driver still

30
00:00:28,207 --> 00:00:28,945
needs to react

31
00:00:28,957 --> 00:00:29,386
in time
```


## Native black/empty-frame gate — 2026-10-22

Propagated the existing rumble_pilot_qa black/empty-image check into native
episode2 shard QA: sum of channel means after30x50resize must not fall below25.
This is the exact existing pilot rule, with no lowered threshold. It applies
to raw native PNGs before caption compositing, not the requested black caption
gutter. Source/hash/format/uniqueness/motion/camera/timing gates remain intact.

Three regressions cover black, near-black and a tiny bright patch on black,
using uncompressed RGB1080x1920PNGs with valid metadata and file SHA256 values.
Each fixture explicitly exceeds the existing10000-byte minimum so rejection
must come from decoded-image inspection, not file size. Tests were written
before the implementation. These fixtures are not genuine rendered footage.

Managed full tests: exit_code0;521passed,1skipped,522collected in446.39seconds
(Python3.14.4 / pytest9.1.1), including all50native-shard cases.
QA SHA256:adb5d376823a2494729219fdefe1efc3e59f3ada6184e5b163a2f3df426fb573
Tests SHA256:ae0d80ed46c7695fcd808933ec795bf5ef244507f90008e9e8225e2099d97a56

No new native proof, MP4, Ruff run or visual approval was produced. This
whole-frame brightness check does not certify partial-void ratios, framing,
meaningful3Dmotion, realistic contact or caption layout. The same three files
remain modified on the owner-authorized branch; no guard retry, branch change,
commit, push, render dispatch, spend or permission change occurred.


## Stored speech and caption regression evidence — 2026-10-22

Added six capture tests and one caption-candidate test to
 tests/test_factory_rumble_episode2.py. The six stored English speech records
are checked against manifest text, en-US-AndrewNeural/+5% settings and SHA256
of WAV, raw MP3 and timing JSON. Decoded WAV headers and samples confirm
48000Hz mono16-bit PCM, nonzero payload, recorded duration within one sample,
segments at most4.75seconds and at least100ms tail after the final word.
Timing entries must be finite, positive, ordered and match all spoken words.

The exact31-cue SRT candidate above covers all88words once, using real provider
word boundaries plus100ms, within0.501ms timestamp rounding tolerance. Cues
are ordered, nonoverlapping and within30seconds. The last-shot sentence
boundary cannot be crossed. Each cue stays within31characters; text is measured
with the existing DejaVuSans62px font and assembler wrapping rule against900px.
This checks the stored proposal, without modifying the excluded assembler.

Final managed full suite: exit_code0;528passed,1skipped,529collected in451.54s
(Python3.14.4 / pytest9.1.1), including24episode2 and50native-shard test cases.
Episode2 test SHA256:b11c0859f7377ef7d8672a46b06303d5ce50b58497fb07f160e4ea5d27737c2b

No new TTS, native render, MP4, AAC silence measurement, listening assessment,
caption raster/gutter approval or Ruff run was produced. Four files remain
uncommitted on the authorized branch at82647f3a53f084a94c802ca4c186f0ce6b9a9c74.
Renderer/assembler and branch-commit restrictions remain; no guard bypass or
branch change was attempted. Next core step remains actual tyre bounds and
native hook comparison at1,25,132,150 through an approved managed route.


## Exact integer frame evidence — 2026-10-22

Native shard QA now requires JSON integers for every frame number, each record's
frame field, and the frames/first_frame/last_frame summary. Frame numbers must
also stay within the manifest's1..900 range before contiguity and file checks.
Python treats true as equal to1 and2.0 as equal to2; equality-only checks could
therefore accept malformed identity evidence. Added five regression cases for
these aliases, written before the implementation. Existing valid integer proofs
and all previous geometry/hash/motion/camera/timing/image gates remain intact.

Final managed suite: exit_code0;533passed,1skipped,534collected in447.26seconds,
including55native-shard cases. This is local uncommitted verification.
QA SHA256:68c9533bc0489769d3cd6ada4b871fb34c572e462377bd7059ebd5fdee55f86b
Native test SHA256:73d5a98d9c774a16bde962d27ae7d197358cb97299ac95610efa92a00d462ec5

Rechecked remote main:fcd20fd78851b18c550b1e433bee46ee34313c1d and PR56
head82647f3a53f084a94c802ca4c186f0ce6b9a9c74. Tests39792023585/39792010339,
smoke39792010308 and all six proof jobs39792010470 are terminal SUCCESS.
They certify the committed baseline only. Root AGENTS.md and CLAUDE.md remain
absent (ENOENT). Four existing modified files remain on the authorized branch.

No new render, MP4, commit, push, branch change or guard bypass. Native tyre
bounds and hook1/25/132/150 comparison still require the approved managed
renderer route; the caption candidate remains unapplied and final QA pending.


## Final-beat lane-return review — 2026-10-22

Read-only source review of timeline1409ebdb339177d22bdfd38d9e262f3031070bd36fa19dfb9188ec0da8edd5b2
and renderer1f6ceb692051d715a49a12627ba082ada01796aee066f2d89d185c9d7ec7866d:
the renderer applies lane_return_offset to root y and lane_return_heading to
root yaw. The trajectory is partial correction, not full lane re-entry proof.
Recomputed from the source equations (not Blender measurements):

| Frame | Lateral offset m | Heading relative to road deg |
| --- | ---: | ---: |
| 750 | 0 | 0 |
| 751 | 0.000042477 | 0.519762 |
| 780 | 0.03328 | 12.362858 |
| 825 | 0.16 | 18.905111 |
| 870 | 0.28672 | 12.362858 |
| 900 | 0.32 | 0 |

Central finite differences cross-check the offset derivative against the
heading equation within1e-10 over751..899. This is static arithmetic only.
The renderer's vertical rumble remains a function of global x throughout
the return; it is not gated by individual tyre overlap with the milled band.
Native review must therefore include825/870/900 and actual tyre world bounds:
check whether each tyre is still over the grooves when vibration is shown,
whether heading is visually convincing, and whether the return reads as the
driver's response. Do not infer full clearance or calibrated suspension from
root y or a passing timeline test. Apply any contact-dependent correction only
after measuring the original vehicle and visually comparing native frames.

No production code, SRT, thresholds or tests changed in this review. Latest
suite remains533passed/1skipped; no rerun or new render. Existing guard denials
remain in force; no alternate provider, branch change or commit retry occurred.


## Native image-container gate — 2026-10-22

Native frame QA now inspects Pillow's detected format and frame count before
decoding: each frame_NNNN.png must be one PNG image. A renamed JPEG or a
multi-frame APNG is rejected even with valid RGB1080x1920pixels, file size and
matching proof SHA256. Added two regression fixtures before implementation;
each explicitly clears the10000-byte minimum and has an updated checksum.
Existing single-PNG proofs and all source/quality/motion/uniqueness gates remain.

Managed full suite: exit_code0;535passed,1skipped in447.92seconds
(Python3.14.4 / pytest9.1.1), including57native-shard cases.
QA SHA256:a585fdce784370bd19a1d305d3d17ab29406e5b187467c555ccd8e04a47ccbf3
Native tests SHA256:876e3e218cc4b5e307c50961ae2f20fb62cd234b4a2f30f00c7ff3ab7d869759

The overview call in this turn returned a JSON parsing error at72960, so it
does not establish fresh remote state. Previously terminal PR56 runs are
historical baseline evidence only. AGENTS.md and CLAUDE.md were again ENOENT.
No new render, MP4, branch change, commit attempt, guard bypass or spend.
Four files remain modified on the authorized branch at82647f3a53f084a94c802ca4c186f0ce6b9a9c74.
Core next step remains measured tyre bounds and native hook/return comparison.

## Pending tyre measurement receipt — 2026-10-22

Implementation and runtime measurements remain blocked; this is a measurement
contract, not a render receipt or a new acceptance threshold. Renderer reviewed:
SHA256 1f6ceb692051d715a49a12627ba082ada01796aee066f2d89d185c9d7ec7866d.
Its local tyre centres/radii are calculated, but episode-proof.json does not
retain world tyre bounds or their camera projections.

For the next authorized comparison, retain each tyre's original object name,
evaluated world-space centre and eight bounding-box corners after the frame
pose is restored (not the temporary camera-anchor pose). Record the camera
matrix, orthographic scale, resolution and pixel aspect; project the corners
to normalized image coordinates with depth. Bounds are geometric evidence:
they do not prove that the body panel does not occlude the contact patch.
Retain the actual rendered image and manual visibility judgement alongside them.

At frames 1,25,132,150 compare the same near-side tyre, identified by measured
world y rather than assuming the unsuffixed Front_tire is the near-side object.
Record its lateral overlap with the milling band [-1.3499,-0.7001] metres,
minimum world z, and road height beneath the tyre footprint. A bounding-box
minimum over a recessed pocket is not a calibrated contact solution.
Reject visible floating, penetration, missing contact or dominant body-panel
composition on viewing; keep physically_calibrated=false until justified.

Include frames 825,870,900 for the return shot to check the changing yaw and
lateral overlap. Six-shot sparse images remain required separately. Neither
this receipt contract nor sparse success authorizes the 900-frame operation.
For any future full render, bind measurements and original frame hashes to
the exact renderer, imported timeline, manifest and pinned asset hashes.

Remote overview succeeded during this documentation update: main
fcd20fd78851b18c550b1e433bee46ee34313c1d; PR56 head
82647f3a53f084a94c802ca4c186f0ce6b9a9c74. Runs 39792010470
(native proof),39792010308 (smoke),39792023585 and39792010339 (tests)
are COMPLETED/SUCCESS. These baseline checks do not cover the uncommitted
QA changes. No workflow was dispatched.


## Native proof JSON type gate — 2026-10-22

Native shard contract fields now require the expected JSON type as well as
the expected value. Numeric zero cannot stand in for false for preview,
physical-calibration or upload flags. Samples, fps, pivot count and resolution
dimensions require integers. The detailed-car mesh count requires an integer
of at least65; NaN and infinity previously escaped its less-than comparison.
No original quality threshold was reduced.

Added15regression cases before implementation (no separate failing test run).
Managed full suite: exit_code0;550passed,1skipped,551collected in461.35seconds,
Python3.14.4 / pytest9.1.1; all72native-shard cases passed. These are synthetic
evidence-validation cases, not rendered tyre-contact or editorial proof.
QA SHA256:7b7088dc7e373aa41665177eb812c45c409a41125fa9cf25ccda426de0aac709
Native tests SHA256:e7f217ad301acf321ef4a2f71da47823083e42ff50f574ab1199b0067e445d2d

Pre-edit status/diff, remote main and PR56 exact-head checks were inspected;
main remains fcd20fd78851b18c550b1e433bee46ee34313c1d. PR56 baseline proof
39792010470, smoke39792010308 and tests39792023585/39792010339 remain terminal
SUCCESS. They do not cover these uncommitted changes. AGENTS.md and CLAUDE.md
returned ENOENT. Same authorized branch and four modified files are preserved.
No denied operation retry, branch change, commit, push, new render, spend or
permission change occurred. Caption SRT remains unchanged and unapplied.
Next core action remains actual tyre measurements and native hook comparison
through an approved renderer edit/render route; the900-frame film is incomplete.

## Hook tyre framing and camera-plane void fix — 2026-10-23

Measured in local Blender 5.0.1 on the pinned asset (no render): Front_tire and
Rear_tire are the near-side tyres, world y -1.009 inside the milling band
[-1.3499,-0.7001] for frames 1..750 (825: front -0.437/rear -1.186; 900: -0.689).
Tyre bbox minimum z is 0.022..0.038 m above grade because the renderer lifts the
car by +0.03 m; at car z=0 the tyre minimum is ~0.0004 m. This floating gap is
**still open** (renderer change, not made here).

Defects found on real preview renders (450x800, 7 samples, frames 1,25,150,375):
1. Hook camera was anchored at frame 25 with a 1.8 m wide frame while the tyre
   travels ~1.4 m: by frame 150 the tyre has left the frame (body panel only).
2. The ortho camera plane of tire_contact started 0.22 m below grade, leaving a
   full-width black band in the bottom ~5.6% of frames 301..450. Committed
   PR56 proof QA did not catch it (frame mean still bright).

Fix (camera_layout only; renderer SHA 1f6ceb69... unchanged):
- hook_warning: low chase view (-5.2,-3.2,2.4), anchored mid-shot, scale 3.2
  unchanged, elevation 21.5 deg (was 30). Tyre stays in frame for all 150 frames.
- tire_contact, rumble_mechanism: same direction and scale, offset doubled.
  Ortho framing is identical; frame 375 differs by mean 0.0 above the old band.
- Native shard QA now rejects a full-width black band at the top/bottom edge.
- New tests: tyre-in-frame per frame for every wheel shot, camera plane >=0.25 m
  above the road for every shot, black edge band rejection (and half-width pass).

Preview metrics (blue body pixel ratio; lower = less body panel):
baseline hook 1/25/150: 0.298/0.319/0.364 (tyre gone at 150);
fixed hook 1/75/150: 0.104/0.172/0.245, tyre visible in all; bottom rows
min mean 104..130 (baseline 375: rows at 0). Black ratio 0.018..0.029.
Previews: /tmp/rumble-measure/fixed (local, non-durable). Preview-only; this is
not a Cycles32 1080x1920 proof and does not authorize the 900-frame render.

## Tyre road contact fix — 2026-10-23

Closes the floating-tyre item above. The renderer no longer lifts the car by
+0.03 m: the body carries the uncalibrated groove-synchronous bounce, and all
four wheel hubs are counter-offset so tyres stay on the road land (a sprung
body over unsprung wheels, still not a suspension solver). At each shot's
camera anchor the hubs are reset to rest, so the fixed camera does not depend
on which frame a shard starts at.

Every frame record now carries `near_tyre_min_z_m` (world z of the lowest
evaluated vertex of Front_tire and Rear_tire). Native shard QA rejects a
missing, non-finite, floating (>4 mm) or penetrating (<-1 mm) value.
physically_calibrated stays false.

Preview evidence (450x800, 7 samples; local, non-durable):
/tmp/rumble-measure/contact frames 1,75,150,375,525,825, proof SHA256
dac14159be540e6a180ec7af5139f80db0bbb1d1be52dafd0d81cb556aaeed4f.
Recorded near-tyre minimum z: 0.0 / 0.00002 / 0.00027 / 0.00001 / 0.00006 /
0.00023 m (before: 0.022..0.038 m). Viewing: contact shadow now attached; no
black bands or other regressions; hook tyre visible at 1/75/150.
Renderer SHA256 8ae5d131ba39868b013e3f7e69bde1175e7c81ff390dfaa41170fde7a1fff132,
QA SHA256 458a354dada0e7e76f4c9394b44e22fda9cc22a1916a7835df411feed52e231e.
Full suite: 560 passed, 1 skipped. Not a Cycles32 1080x1920 proof; does not
authorize the 900-frame render.

## Production caption grouping and caption/tyre clearance — 2026-10-23

Running the real assembler speech stage locally (`episode2_film.py speech`,
PASS, 32 cues, max silence 0.711 s) showed the production captions differed
from the reviewed candidate above: fixed 3-word chunks produced the cue
"for you The" across the shot-6 sentence end and an orphan cue "time".

Change: `rumble_episode2.caption_groups` splits each sentence (narration
punctuation) into balanced groups of at most three words; the assembler uses
it and asserts narration tokens match provider word timings 1:1. Shot 6 now
reads "These grooves cannot / steer your car / for you / The driver still /
needs to react / in time". Every cue is 2-3 words within one sentence; timing
still comes from provider word boundaries. The doc candidate (31 cues) remains
a separate hand-grouped alternative; neither is human-approved.

New regression test: projected near-tyre contact rows (930..1190 px of 1920)
stay at least 100 px above the top of a two-line caption parsed from the real
ASS style (MarginV 325, 62 px), for every frame of every wheel shot.

Evidence (local, non-durable, /tmp/rumble-measure/speech2): captions.srt
a8a1b272..., film.ass b9544ae4..., narration.wav 01dc1fd8...; composite check
/tmp/rumble-measure/cap_pair.png (upscaled previews, layout only).
Assembler SHA256 98f37c800386982c0aa88131d68f4cdcc45fb1637a36f5d2d476907a1681e4e9.
Full suite: 562 passed, 1 skipped.

Pending owner decisions (not changed):
- Captions overlay the full-bleed native picture (outline style). The main
  pipeline's convention is captions in a black gutter outside the picture;
  meeting that here needs either an opaque black caption box or letterboxing
  the native frames. White-on-asphalt contrast is only moderate on viewing.
- driver_response peaks at ~19 deg yaw because the time-slowed car moves
  0.32 m sideways over 1.4 m of travel; the manifest asks it to visibly point
  toward the lane. Realistic yaw (~1 deg) would make the correction invisible.
