#!/usr/bin/env python3
"""Force-align an authored Korean narration and emit prerendered words JSON.

WhisperX runs only as an offline production tool. The render engine never
imports it; render consumes the strict JSON contract and fails closed if the
words do not match the scene script exactly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shorts_studio.forced_alignment import strict_aligned_words

DEFAULT_KO_ALIGN_MODEL = "kresnik/wav2vec2-large-xlsr-korean"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--text", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--align-model", default=DEFAULT_KO_ALIGN_MODEL)
    args = ap.parse_args()

    if sys.version_info >= (3, 14):
        raise RuntimeError(
            "WhisperX 3.8.6 requires Python <3.14. Run this alignment tool "
            "in Python 3.10-3.13 (CI uses 3.11); render can stay on Python 3.14."
        )

    try:
        import whisperx
    except ImportError as exc:
        raise RuntimeError(
            "WhisperX is not installed. Use the narration-align optional dependency."
        ) from exc

    text = args.text.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("alignment text is empty")

    audio = whisperx.load_audio(str(args.audio))
    duration = len(audio) / 16000.0
    if duration <= 0:
        raise ValueError("alignment audio is empty")

    model, metadata = whisperx.load_align_model(
        language_code="ko",
        device=args.device,
        model_name=args.align_model,
    )
    aligned = whisperx.align(
        [{"text": text, "start": 0.0, "end": duration}],
        model,
        metadata,
        audio,
        args.device,
        interpolate_method="ignore",  # never fill missing word times from neighbours
        return_char_alignments=False,
        print_progress=False,
    )
    words = strict_aligned_words(text, aligned.get("word_segments", []))
    if not words:
        raise ValueError("forced alignment returned no usable words")
    last_end = float(words[-1]["end"])
    if last_end > duration + 0.05:
        raise ValueError(
            f"forced alignment ends after audio: {last_end:.3f}s > {duration:.3f}s"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "audio": str(args.audio),
                "out": str(args.out),
                "tokens": len(words),
                "duration": round(duration, 3),
                "first": round(float(words[0]["start"]), 3),
                "last": round(float(words[-1]["end"]), 3),
                "align_model": args.align_model,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
