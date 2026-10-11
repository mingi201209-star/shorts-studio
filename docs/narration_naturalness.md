# GPT-SoVITS p38 narration naturalness (2026-10-08)

Test script: “빗길에선 타이어가 돌고 있어도 도로에 안 닿을 수 있습니다. 원인은 고무가 아닙니다.
타이어 밑으로 파고드는 물입니다.” Timbre fixed to the screened p38 speaker
(Throat and Acoustic Pairing Speech Dataset, CC BY 4.0).

Metrics below are diagnostics, not a pass verdict. The adoption decision is made by
listening.

## Root causes in the previous C_shorts_explainer setup

All three come from `how_to_cut="按标点符号切"` in the official
`GPT_SoVITS/inference_webui.py`, `get_tts_wav`:

1. Every comma and period starts a new segment, and each segment is followed by
   `pause_second=0.3` s of digital silence. With the model's own tail silence this
   produced 0.45–0.51 s pauses at every punctuation mark.
2. Each segment is a separate autoregressive pass, so coarticulation and prosody
   reset at every comma. Whisper-small transcribed C with CER 0.375 (“도로에 안 닿을”
   → “돌어야 안 될”, “원인은 고무가” → “워리는 보험가”). The whole-text synthesis
   under the same ASR measured CER 0.02–0.08.
3. The p38 corpus is entirely news reading, so the reference carries newsreader
   prosody.

## A/B results (u36 = a p38 focus-construction utterance used as the prosody prompt)

| Strategy | CER | UTMOS22 | p38 sim (GE2E) | F0 span p10–p90 | Pauses |
|---|---|---|---|---|---|
| C (punctuation cut) | 0.375 | 1.76 | 0.827 | 4.1 st | 0.45 / 0.48 / 0.51 s |
| Semantic chunks, 4 passes + designed pauses | 0.10–0.17 | 1.94–2.25 | 0.82–0.84 | 5.0–5.5 st | as designed |
| Two chunks split at the semantic turn | 0.10–0.19 | 2.13–2.27 | 0.82–0.86 | 5.1–6.0 st | as designed |
| Whole text, one pass (`不切`) | 0.02–0.08 | 2.29–2.57 | 0.85–0.87 | 5.6–6.9 st | one or two 0.44–0.80 s |
| Whole text + semantic pause retime | same | 2.26–2.54 | 0.85–0.87 | same | link ≤0.11, turn 0.34, contrast 0.20 s |

For reference, a real p38 recording scores UTMOS 2.56, and another p38 utterance has
GE2E similarity 0.921. Other male speakers score 0.65–0.76.

The chunked syntheses lose to the whole-text pass on every measure, so they were
rejected. The whole-text pass with silence-only pause retiming
(`shorts_studio/pause_plan.py`, `scripts/gpt_sovits_narration.py`) is the candidate
for adoption.

## Pause design

Boundaries are marked in the script, not forced with commas:

```text
빗길에선 타이어가 돌고 있어도 [link] 도로에 안 닿을 수 있습니다. [turn]
원인은 고무가 아닙니다. [contrast] 타이어 밑으로 파고드는 물입니다.
```

| Marker | Target |
|---|---|
| `[tight]` | 40 ms |
| `[link]` | 110 ms; only ever shortened, never stretched |
| `[contrast]` | 200 ms |
| `[turn]` | 340 ms |
| unmarked join | capped at 160 ms |

A turn or contrast pause that cannot be found fails closed. A link the voice already
ran through stays connected, and short stop closures are never lengthened. Speech
samples are copied untouched: no pitch shift, time-stretch or global speed-up.

## Remaining limits

- **Focus.** “안” and “물” are not prominent in any take: −0.3 to −4.0 st against
  their neighbours, while “원인은/고무가” rise +2 to +4.7 st. Script restructuring
  (“아예 안 닿을”, “고무가 아니라 …”) did not change this. The model only reproduces
  the focus prosody that its reference carries, and p38 has only news reading. The
  next step is a short p38-timbre reference spoken in explainer style with
  contrastive focus, or a fine-tune. Artificial gain or pitch boosts were not used.
- **“파고드는”.** ASR hears “파고 되는/파고들은” in most takes, which suggests the
  ㅡ after 고 gets rounded. Check this by ear.
- **Sentence-final contours.** With the u53 prompt, “-습니다” often rises. With u36
  the finals fall reliably, so u36 is the recommended prompt.
- **Not yet in the render path.** GPT-SoVITS is not wired into render. Using it needs
  the `prerendered` provider with exact per-token word timings from a maintained
  forced aligner (e.g. WhisperX or ctc-forced-aligner). The Whisper word times used
  here only anchor pauses and are never caption timing.
- **ZeroGPU quota.** The public Space's anonymous quota runs out after about 25
  calls. An HF token (from the environment only) or a self-hosted GPT-SoVITS is
  needed for production volume.


## 2026-10-11 continuation verification

- Actual workspace: phone Ubuntu `/root/shorts-studio`; Termux `/data/data/com.termux/files/home/shorts-studio` is a separate clean main checkout.
- Baseline full regression: 542 passed, 1 skipped. Final full regression: 548 passed, 1 skipped. After disabling alignment interpolation, the focused narration/alignment/pause checks passed 24 tests.
- Generated two whole-sentence `밀려드는` takes. Whisper-small heard the target as `미웨드는`/`미워드는`; neither is adopted.
- Generated one `타이어 아래로 들어오는 물입니다` take. The last clause transcribed correctly; earlier `빗길에선` and `닿을` errors remain. ASR is diagnostic, not a listening verdict.
- Next synthesis exhausted the public ZeroGPU quota. Supply HF_TOKEN through the environment or a self-hosted backend for further synthesis; never commit a token.
- The synthesis script now writes reports after each completed take, preserves those reports when a later synthesis fails, and stops retrying quota errors.
- Forced-alignment validation rejects NaN and infinity timestamps.
- Isolated Python 3.13 alignment environment: `/root/.venvs/shorts-align`. Python 3.14 render environment is unchanged. Installation/import verification is required before claiming WhisperX works.
- New WAV copies: `/sdcard/Download/claude_narration_test/20261011/05_millyeodeuneun_take1.wav`, `06_millyeodeuneun_take2.wav`, `07_deureooneun_take1.wav`.
- No candidate is wired into production, no fabricated caption timings, no merge, no YouTube upload.

Alignment environment verified with `pip check`: Python 3.13.16, WhisperX 3.8.6, torch 2.8.0+cpu, pandas 2.2.3. Under this phone proot environment, uv installation omitted some package files; reinstalling the affected official wheels with pip and no cache repaired them.

The alignment CLI now passes `interpolate_method="ignore"` to WhisperX. Missing word timestamps remain missing and strict_aligned_words rejects them. Never rename an interpolated earlier output to represent this stricter run.


### Real render verification (2026-10-11)

The anonymous quota later allowed one more synthesis. The accepted-for-render experiment retains the original hook wording and substitutes only the final `파고드는` construction with `아래로 들어오는`. The first generated test script failed the existing hook contract and was rejected without changing that contract.

- New hook take: `build/narration_hook_contract_20261011/take1.wav`.
- Real non-interpolated WhisperX alignment: 17 authored tokens, 8.506 s.
- Comparison manifest: `build/narration_preview_20261011/manifest.json`; only the opening voice is new. Reveal/twist reuse the original recorded Edge audio and its existing native word timing.
- Actual render: 1080x1920, 32.166893 s; semantic_required=true; semantic visual QA PASS; final video QA PASS; captions and safe areas PASS.
- First 5 s: 2 meaningful changes at 2.001 and 4.943 s; the second is only just inside the window. Automated visual activity count is 5 and must not be confused with semantic changes.
- Review: no black opening; captions stay below the picture. The later mechanism still looks like a flat engineering graphic. No human naturalness approval was made. This comparison is not an upload-ready adoption.
- Phone copy: `/sdcard/Download/claude_narration_test/20261011/opening-voice-comparison-20261011.mp4`; SHA256 `20a9511ffa13a4d332f7e29d8ab74cb24fdfd2a10231717f2a265b88a593e02b`.
- Production defaults unchanged; no commit/push/merge or YouTube upload.

### Final ASR cross-check (2026-10-11)

- large-v3-turbo completed with PCM ndarray input (the installed PyAV decoder rejects metadata_errors).
- Original N1 was recognized as: 뒷길에선 타이어가 돌고 있어도 도로에 안 닿을 수 있습니다. 원인은 고무가 아닙니다. 타이어 밑으로 파고드는 물입니다.
- New hook was recognized as: 빅딜에선 타이어가 돌고 있어도 실은 도로에 닿지 않을 수 있습니다. 문제는 고무가 아니라 타이어 아래로 들어오는 물입니다.
- The larger model resolves the small-model 고무 error and recognizes 들어오는 correctly. Both models misrecognize the new first word 빗길 as 빅딜, so pronunciation is suspect and adoption remains pending actual listening. ASR alone cannot establish perceived voice naturalness.
- Full regression after finite-timing/quota/report fixes: 548 passed, 1 skipped. Subsequent focused checks including the final noninterpolating WhisperX CLI test: 24 passed.
- PR #41 existing remote head 327ab707: all five check runs completed successfully at final recheck. These checks do not cover the uncommitted phone changes.
