# Scene execution spec and Narration-Visual Alignment ("말하는 그대로 보여줘라")

Reusable module: `shorts_studio/scene_spec/` (no Blender, independent of the render engine; nothing in `main` or the existing departments was changed).

| Part | File | What it does |
|---|---|---|
| Planning | `spec.py`, `examples/episodes/<episode>-scene-spec.json` | Every narration sentence/clause becomes a Scene: exact words, spoken cue, subjects (objects/parts), the physical phenomenon with the telemetry metric that proves it, camera, effects, success conditions. `validate` rejects a scene with narration only, and checks that the scenes cover the speech plan word for word. `production_blockers` lists capabilities the renderer does not have yet. |
| Editing | `alignment.resolve_windows` | Scene windows come from the real TTS caption cues, never from guessed times. |
| Rendering | `benchmarks/<episode>/render_*.py` + `capabilities.py` | The renderer writes per-frame evidence (metrics, which subjects are in the camera view, whether the action overlaps the caption band). A phenomenon is only counted if a metric moved. |
| Evaluation | `alignment.evaluate_episode` | Six criteria per scene: subject present, action performed, timing against the spoken cue, sound-off comprehension, physical consistency, not obscured. Software never gives PASS to what only a person can judge: those stay `NOT_VERIFIED`, a scene is then `AUTO_PASS_HUMAN_REVIEW_PENDING`. Windows beyond the previewed seconds are `PENDING_MORE_FRAMES`, never PASS. |
| Management | `pipeline.full_render_allowed`, `scene-registry.json` | One question for the full-render workflow: spec valid, every capability implemented, every scene has preview evidence that is not FAIL/PENDING. Otherwise the answer is no, with reasons. |

Order of work (no full render to explore quality): spec -> low-resolution contiguous preview with the real TTS -> alignment + physics + camera + caption gates -> fix only the failing scenes -> `full_render_allowed` -> full render -> selective re-render of failing shards only.

Extending to a new episode: write the spec JSON, add a `capabilities.py` listing what the renderer implements, make the renderer write the metrics/in_view/caption-overlap evidence, and call `evaluate_episode` from the preview assembly (see `benchmarks/crumple_zone/assemble_crumple_preview.py`).
