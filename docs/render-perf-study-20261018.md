# Native render speed test — 2026-10-18

Scope: the agreed seven-topic **Hidden Engineering of American Roads** series. This experiment uses the rumble-strip scene and makes no edits to the shipping renderer, production defaults or quality gates.

## Method

- A/B/A comparison: baseline, Cycles persistent-data flag, baseline again.
- Each run renders the **same** four changing frames, fixed camera, same geometry and 360×640/Cycles 6 preview quality.
- Decode and compare every RGB pixel; different frames, missing frame or any color-channel difference is a failure.
- Three separate Blender process launches; steady-state render time excludes the first-frame scene warm-up.
- Experimental flag is off by default. No cached output is declared production ready.

## Results

| Mode | Wall clock | Steady frame median |
| --- | ---: | ---: |
| Baseline 1 | 25.908 s | 5.152 s |
| Persistent data | 25.544 s | 5.097 s |
| Baseline 2 | 25.816 s | 5.141 s |

A/B/A steady-frame speedup = **1.010×** (about 1%). RGB frames were **pixel-exact** in both comparisons. This does not justify enabling persistent data: outcome **REJECTED / INCONCLUSIVE**. No native 1080×1920 or 32-sample speedup is claimed from this preview.

## Separately verified existing production workflows

- Guardrail full native rendering, workflow run [39111993576](https://github.com/mingi201209-star/shorts-studio/actions/runs/39111993576): 2026-10-18 08:34:51 to 09:42:43 UTC, ~67m52s.
- Expanded English narration over existing 900 frames, workflow run [39118313523](https://github.com/mingi201209-star/shorts-studio/actions/runs/39118313523): 10:12:08 to 10:14:27 UTC, ~2m19s.
- **Do not treat these as controlled A/B renderer timings:** the second job replaces speech and captions and reuses previous visual footage instead of rendering a new 3D mechanism. They do prove that clip reuse can bypass the main render cost.

## Decision and next focus

- Retain original Cycles32/native-resolution delivery conditions, 30fps and original independent motion. Keep experimental persistent-data flag off.
- Prioritize provenance-verified reuse of valid native shots, shared 3D car/road asset construction, and separate speech/subtitle assembly across the planned seven road-safety episodes.
- Validate **another topic's actual moving 3D footage** before claiming the Factory can produce another video in minutes.
- Pilot rumble strip geometry is visually BELOW the existing floor and remains held; it is not to be surfaced as ready or uploaded.
