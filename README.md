# shorts-studio

Independent 9:16 Shorts production engine. TTS speech timing is the source of truth for captions; rendering and QA are kept separate from `shorts-bot`.

## Quick start

```bash
pip install -e '.[dev]'
python -m shorts_studio validate examples/comet.json
python -m shorts_studio render examples/comet.json --dry-run
pytest
```

A full render requires FFmpeg and TTS/network access. CI smoke mode uses deterministic local timing so it does not depend on paid APIs.

### Full production render (with real semantic visual QA)

```bash
# torch and torchvision must come from the SAME index so their compiled ABIs match --
# installing them separately (e.g. torch from the CPU index, torchvision from plain
# PyPI via open-clip-torch) can otherwise fail with "operator torchvision::nms does
# not exist".
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -e '.[dev,vision]'
SHORTS_REQUIRE_SEMANTIC_QA=1 python -m shorts_studio render examples/comet.json
```

`SHORTS_REQUIRE_SEMANTIC_QA=1` is the production fail-closed switch (see below). Without the `vision`
extra installed, semantic checks that need it report `NOT_EVALUATED`, which this switch treats as a
failure rather than a silent pass.

## Visual QA architecture

Each scene's representative (mid-point) frame is extracted and checked by a
`CompositeVisionProvider` made of independent, real checks — nothing here fabricates a PASS:

| Provider | What it really measures | Runs without extra deps? |
|---|---|---|
| `ClarityVisionProvider` | Sharpness (Laplacian variance), contrast, exposure — the mobile-clarity/subject-visibility floor | Yes |
| `CornerGeometryVisionProvider` | Contour/curvature geometry: sharp 90° corners vs. large rounded corners, and whether both are simultaneously distinguishable | Yes |
| `ClipSemanticVisionProvider` | Local zero-shot image↔text similarity (open_clip/CLIP, no API key, no payment, runs on-device) against scene-declared `visual_qa_labels` / `visual_qa_negative_labels`, to catch wrong-subject or wrong-domain assets | Only with the `vision` extra |
| `SidecarVisionProvider` | Lets an external reviewer (human or another vision API you wire up) drop a `<frame>.qa.json` verdict next to the frame | Yes (opt-in) |

A scene is `PASS` only if at least one provider actually evaluated it and none reported `FAIL`.
If every provider abstains, the scene is `NOT_EVALUATED` — it is **never** defaulted to PASS.
An unrecognized/malformed provider status is also treated as `NOT_EVALUATED`, never as a pass signal.

**Fail-closed production policy** (`production_semantic_ok` in `visual_qa.py`):
- `SHORTS_REQUIRE_SEMANTIC_QA=1` (production): only an executed `PASS` is acceptable. `NOT_EVALUATED` fails.
- Otherwise (local/dev): `NOT_EVALUATED` is tolerated, but a real `FAIL` always fails the render, in either mode.

**Known limitation:** `ClipSemanticVisionProvider` does coarse zero-shot subject/domain
classification well (e.g. "water-tank test rig" vs. "airplane in flight", "wreckage" vs. "intact
aircraft"). It cannot reliably distinguish one specific historical aircraft model from another
similar-looking jet by zero-shot alone — that would need a fine-tuned classifier or a paid
vision-LLM API, which this project does not call. This is reported here rather than silently
overclaimed.

### Automated visual-QA recovery loop

When a scene's semantic QA reports `FAIL`, the render pipeline does **not** restart the whole
production. It:

1. Structures the failure (which provider, which reason).
2. Swaps in the scene's next `recovery_candidates` asset entry (if declared in the manifest).
3. Re-renders **only that scene's clip**.
4. Re-runs semantic QA on just that scene.
5. Repeats up to `max_visual_recovery_attempts` (per-project, default 2) before giving up.

Exceeding the recovery budget fails the whole production (fail-closed) — it never loops forever
and never silently ships a scene that never passed. See `_render_scene_with_recovery` in
`render.py` and `tests/test_recovery_loop.py`.

### Korean TTS timing

`edge_tts_with_boundaries` anchors every caption to real TTS provider boundary events
(word/sentence boundaries from Microsoft Edge TTS); it raises rather than falling back to a
character-count guess if no boundary events come back. `subtitles.segment()` groups those real
timestamps into short (~1–2s) Shorts-style captions, leads the voice slightly so captions never
feel like they lag, and (as of this change) starts a new caption group across any real pause
longer than `max_gap` so a long inter-sentence silence can no longer get merged into one caption
and then silently clipped out of coverage. `tests/test_tts_timing.py` and
`tests/test_subtitle_regression.py` cover these regressions directly.

## Render pipeline

`shorts_studio render` produces `dist/final.mp4` (1080x1920, ≥30fps, H.264/AAC) and
`dist/qa_report.json`, which records per scene: the subtitle QA result, asset provenance
(including which recovery candidate index was used), the semantic visual QA result and the
requirements it was checked against, and the recovery attempt count — plus the overall PASS/FAIL.

## Safety boundary

This repository does not upload to YouTube and does not modify `shorts-bot`. It does not call any
paid vision/LLM API; `ClipSemanticVisionProvider` runs a local open-source model.

## Status

V1 production hardening. See the feature PR for verified tests, full-render CI status
(`render-smoke.yml`), and known limitations.
