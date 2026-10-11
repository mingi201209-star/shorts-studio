#!/usr/bin/env python3
"""Generate GPT-SoVITS narration takes with semantic pause design.

Reproduces the 2026-10-08 narration A/B (see docs/narration_naturalness.md):

* Synthesis goes through the official GPT-SoVITS ProPlus Space
  (RVC-Boss/GPT-SoVITS, MIT) with how_to_cut="不切": the WHOLE script is one
  autoregressive pass. Cutting per punctuation (the old C_shorts_explainer
  setup) restarts the model at every comma/period, appends a fixed 0.3 s
  ``pause_second`` per segment and measurably slurs articulation.
* ``--ref`` sets prosody (any p38 utterance); ``--timbre-ref`` is passed as
  ``inp_refs`` so the voice stays the screened p38 timbre.
* Pauses are then set per semantic boundary marker in the script
  ([tight]/[link]/[contrast]/[turn], see shorts_studio.pause_plan); only
  silence is edited -- no pitch shift, no time-stretch, no global speed-up.

Takes vary (sampling); pick by listening. Each take is written raw and
retimed, plus a JSON report of every pause before/after.

Requires: pip install gradio_client librosa soundfile faster-whisper
(faster-whisper only locates words to anchor the marked boundaries; its
transcript is never used as caption text).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shorts_studio import pause_plan as pp

SPACE = "lj1995/GPT-SoVITS-ProPlus"


def synthesize(text: str, ref: Path, ref_text: str, timbre_refs: list[Path], out: Path,
               top_k: int = 10, top_p: float = 0.88, temperature: float = 0.76, speed: float = 1.0) -> Path:
    from gradio_client import Client, handle_file
    last = None
    for attempt in range(3):
        try:
            client = Client(SPACE, verbose=False, hf_token=os.environ.get("HF_TOKEN"))
            # top_k must be an int: a float reaches torch.topk and the Space
            # answers with a bare RuntimeError.
            res = client.predict(handle_file(str(ref)), ref_text, "韩文", text, "韩文", "不切",
                                 int(top_k), float(top_p), float(temperature), False, float(speed), False,
                                 [handle_file(str(p)) for p in timbre_refs], api_name="/get_tts_wav")
            src = Path(res if isinstance(res, str) else res[0] if isinstance(res, (list, tuple)) else res["path"])
            shutil.copyfile(src, out)
            return out
        except Exception as e:  # noqa: BLE001 - external Space failures vary; retry then fail loudly
            last = e
            if "quota" in str(e).lower():
                raise RuntimeError("GPT-SoVITS quota exhausted; completed takes are preserved. Provide HF_TOKEN or use a self-hosted provider.") from e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"GPT-SoVITS synthesis failed: {last!r}")


def retime(raw: Path, out: Path, plan: pp.PausePlan, asr) -> dict:
    import librosa
    import soundfile as sf
    y, sr = sf.read(raw, dtype="float32")
    y = y.mean(axis=1) if y.ndim > 1 else y
    y16 = librosa.resample(y, orig_sr=sr, target_sr=16000)
    segs, _ = asr.transcribe(y16.astype(np.float32), language="ko", word_timestamps=True,
                             beam_size=5, condition_on_previous_text=False)
    words = [(w.word, w.start, w.end) for s in segs for w in s.words]
    gaps = pp.plan_gap_targets(plan, pp.detect_silences(y, sr), pp.map_words_to_tokens(plan.tokens, words))
    new, _ = pp.retime_silences(y, sr, gaps)
    sf.write(out, new, sr)
    return {"pauses_before": [round(b - a, 3) for a, b, _ in gaps],
            "pauses_after": [round(t, 3) for *_, t in gaps],
            "recognised": "".join(w for w, *_ in words).strip()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--marked", required=True, help="script with [tight]/[link]/[contrast]/[turn] markers")
    ap.add_argument("--ref", type=Path, required=True, help="prosody reference WAV (3-10 s)")
    ap.add_argument("--ref-text", type=Path, required=True, help="exact transcript of --ref")
    ap.add_argument("--timbre-ref", type=Path, action="append", default=[], help="timbre anchor WAV(s)")
    ap.add_argument("--takes", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    plan = pp.parse_pause_markup(a.marked)
    a.out.mkdir(parents=True, exist_ok=True)
    from faster_whisper import WhisperModel
    asr = WhisperModel("small", device="cpu", compute_type="int8")
    ref_text = a.ref_text.read_text(encoding="utf-8").strip()
    report = {"text": plan.text, "boundaries": {plan.tokens[i]: k for i, k in plan.boundaries.items()}, "takes": []}
    for n in range(1, a.takes + 1):
        try:
            raw = synthesize(plan.text, a.ref, ref_text, a.timbre_ref, a.out / f"take{n}_raw.wav")
        except RuntimeError:
            report["status"] = "incomplete"
            report["failed_take"] = n
            (a.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            raise
        try:
            info = retime(raw, a.out / f"take{n}.wav", plan, asr)
        except ValueError as e:  # a marked semantic pause could not be located: keep raw, say so
            info = {"error": str(e)}
        report["takes"].append({"take": n, **info})
        (a.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["takes"][-1], ensure_ascii=False))
    (a.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
