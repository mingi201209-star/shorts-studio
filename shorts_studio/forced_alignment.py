"""Strict conversion of forced-aligner word output into Shorts Studio timings.

This module deliberately has no WhisperX dependency. Production alignment can
run in a Python 3.10-3.13 tool environment, while render only consumes the
validated JSON. Any token mismatch or missing timestamp fails closed.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping


def _norm(token: str) -> str:
    return re.sub(r"[^\w]", "", token).lower()


def script_tokens(text: str) -> list[str]:
    return re.findall(r"[^\s]+", text.strip())


def strict_aligned_words(
    text: str, raw_words: Iterable[Mapping[str, object]]
) -> list[dict[str, float | str]]:
    """Convert aligner word output to exact authored script-token timings."""
    expected = script_tokens(text)
    observed = []
    for raw in raw_words:
        word = str(raw.get("word", raw.get("text", ""))).strip()
        if not _norm(word):
            continue
        observed.append(raw)

    if len(observed) != len(expected):
        raise ValueError(
            f"forced alignment returned {len(observed)} lexical words, "
            f"script has {len(expected)}"
        )

    out: list[dict[str, float | str]] = []
    previous_start = 0.0
    for i, (token, raw) in enumerate(zip(expected, observed, strict=True)):
        word = str(raw.get("word", raw.get("text", ""))).strip()
        if _norm(word) != _norm(token):
            raise ValueError(
                f"forced alignment word {i} {word!r} does not match script token {token!r}"
            )
        start_obj, end_obj = raw.get("start"), raw.get("end")
        if start_obj is None or end_obj is None:
            raise ValueError(f"forced alignment word {i} {word!r} has no timestamp")
        start, end = float(start_obj), float(end_obj)
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start or start < previous_start:
            raise ValueError(
                f"forced alignment word {i} {word!r} has invalid timing {start}-{end}"
            )
        out.append({"text": token, "start": start, "end": end})
        previous_start = start
    return out
