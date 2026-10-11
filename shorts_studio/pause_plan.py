"""Semantic pause plan + silence-only retiming for pre-rendered narration.

Why this exists: GPT-SoVITS (and most TTS) turns every sentence end into a
0.4-0.6 s pause and, when text is cut per punctuation, adds a fixed 0.3 s of
digital silence per segment (official ``inference_webui.get_tts_wav``,
``pause_second``). Human explainer narration instead keeps most joins short
(about 60-160 ms) and spends a longer pause only where the *meaning* turns.

The pause design is written into the script as boundary markers rather than
extra commas, so the synthesis text stays natural Korean:

    빗길에선 [tight] 타이어가 돌고 있어도 [link] 도로에 안 닿을 수 있습니다. [turn]
    원인은 고무가 아닙니다. [contrast] 타이어 밑으로 파고드는 물입니다.

Only silence is edited: speech samples are copied untouched (no pitch shift,
no time-stretch, no global speed-up). Detection uses librosa's maintained
``effects.split`` / ``effects.trim``; the custom part is the small splice
that shortens/lengthens an already-silent gap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import numpy as np

# Target pause (seconds) per semantic boundary kind.
PAUSE_TARGETS = {"tight": 0.04, "link": 0.11, "contrast": 0.20, "turn": 0.34}
# Boundaries whose pause carries meaning; these must be found in the audio.
LONG_KINDS = ("contrast", "turn")
# A join with no marker is ordinary connected speech: never longer than this.
UNMARKED_MAX = 0.16
# Natural decay/onset kept on each side of a shortened pause.
EDGE_KEEP = 0.025
FADE = 0.006

_MARK = re.compile(r"\[(tight|link|contrast|turn)\]")


@dataclass(frozen=True)
class PausePlan:
    text: str                      # synthesis text, markers removed
    tokens: list[str]
    boundaries: dict[int, str]     # token index i -> kind of the join AFTER token i


def parse_pause_markup(marked: str) -> PausePlan:
    tokens: list[str] = []
    boundaries: dict[int, str] = {}
    for part in re.split(r"(\[(?:tight|link|contrast|turn)\])", marked):
        m = _MARK.fullmatch(part.strip()) if part.strip() else None
        if m:
            if not tokens:
                raise ValueError("pause marker before the first word")
            if len(tokens) - 1 in boundaries:
                raise ValueError(f"two pause markers after {tokens[-1]!r}")
            boundaries[len(tokens) - 1] = m.group(1)
        else:
            tokens.extend(part.split())
    if tokens and len(tokens) - 1 in boundaries:
        raise ValueError("pause marker after the last word")
    return PausePlan(" ".join(tokens), tokens, boundaries)


def chunk_texts(plan: PausePlan) -> list[str]:
    """Split the plan at its markers: one synthesis chunk per semantic unit."""
    chunks, cur = [], []
    for i, tok in enumerate(plan.tokens):
        cur.append(tok)
        if i in plan.boundaries:
            chunks.append(" ".join(cur)); cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _frames(sr: int) -> tuple[int, int]:
    """~20 ms analysis frame (power of two) and quarter hop, at any sample rate.

    A fixed 1024-sample frame smears every gap edge by half a frame (~32 ms
    at 16 kHz), which is the same order as the pauses being designed.
    """
    frame = 1 << max(6, round(np.log2(0.02 * sr)))
    return frame, frame // 4


def detect_silences(y: np.ndarray, sr: int, top_db: float = 35.0, min_gap: float = 0.04) -> list[tuple[float, float]]:
    import librosa
    frame, hop = _frames(sr)
    iv = librosa.effects.split(y, top_db=top_db, frame_length=frame, hop_length=hop)
    gaps = [(iv[i][1] / sr, iv[i + 1][0] / sr) for i in range(len(iv) - 1)]
    return [(a, b) for a, b in gaps if b - a >= min_gap]


def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s)


def map_words_to_tokens(tokens: list[str], words: list[tuple[str, float, float]]) -> dict[int, float]:
    """End time of each script token from (approximate) recognised words.

    Character-level alignment of the recogniser's text onto the script, so a
    misrecognised syllable does not shift every later boundary. Only tokens
    whose final character is aligned get a time; others are left unknown.
    """
    script = "".join(_norm(t) for t in tokens)
    tok_end_char = np.cumsum([len(_norm(t)) for t in tokens]) - 1
    hyp, char_end_time = "", []
    for w, _s, e in words:
        n = _norm(w)
        hyp += n; char_end_time += [e] * len(n)
    pos = {}
    for a, b, size in SequenceMatcher(None, script, hyp, autojunk=False).get_matching_blocks():
        for k in range(size):
            pos[a + k] = b + k
    out = {}
    for ti, ce in enumerate(tok_end_char):
        if ce in pos:
            out[ti] = char_end_time[pos[ce]]
    return out


def plan_gap_targets(plan: PausePlan, silences: list[tuple[float, float]],
                     token_end: dict[int, float], tol: float = 0.30) -> list[tuple[float, float, float]]:
    """(start, end, target) for every detected silence.

    Each marked boundary claims the one silence closest to its (recognised)
    token end -- recogniser word ends drift 0.1-0.3 s into or before the
    pause, so distance is measured to the silence interval, not its start.
    Every other silence is ordinary connected speech and is only capped.

    Fails closed for the long kinds ([contrast]/[turn]): such a boundary with
    no silence near it raises instead of being silently capped, because
    capping a semantic turn would flatten the one pause meant to be long.
    A [link]/[tight] join the voice already ran through without a pause is
    left connected -- splicing silence into running speech sounds chopped.
    """
    claimed: dict[int, str] = {}
    for ti, kind in sorted(plan.boundaries.items()):
        required = kind in LONG_KINDS
        t = token_end.get(ti)
        if t is None:
            if required:
                raise ValueError(f"no timing for marked boundary after {plan.tokens[ti]!r}")
            continue
        near = [(max(0.0, a - t, t - b), b - a, i) for i, (a, b) in enumerate(silences)
                if i not in claimed and max(0.0, a - t, t - b) <= tol]
        if not near:
            if required:
                raise ValueError(f"no pause found near marked {kind} boundary after {plan.tokens[ti]!r} (t={t:.2f}s)")
            continue
        # A sentence/turn pause is the longest silence around its boundary,
        # which is robust to recogniser drift; a link takes the nearest one.
        pick = max(near, key=lambda x: x[1]) if required else min(near)
        claimed[pick[2]] = kind
    out = []
    for i, (a, b) in enumerate(silences):
        cur = b - a
        kind = claimed.get(i)
        if kind in LONG_KINDS:
            target = PAUSE_TARGETS[kind]          # set exactly (may lengthen)
        elif kind:
            target = min(cur, PAUSE_TARGETS[kind])  # links only ever shorten
        else:
            target = min(cur, UNMARKED_MAX)
        out.append((a, b, target))
    return out


def retime_silences(y: np.ndarray, sr: int, gaps: list[tuple[float, float, float]]) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Set each silent gap to its target length; speech is copied verbatim.

    Returns the new audio and a piecewise time map [(old_t, shift)] so word
    timings can be moved with :func:`shift_time`.
    """
    y = np.asarray(y, dtype=np.float32)
    pieces, cursor, shift, tmap = [], 0, 0.0, [(0.0, 0.0)]
    keep = int(EDGE_KEEP * sr)
    for a, b, target in sorted(gaps):
        ia, ib = round(a * sr), round(b * sr)
        cur = ib - ia
        want = max(0, round(target * sr))
        if want == cur:
            continue
        if want < cur:
            k = min(keep, want // 2, cur // 2)
            left_end = ia + k
            right_start = ib - (want - k)
            pieces.append(y[cursor:left_end].copy())
            tail = y[right_start:ib].copy()
            f = min(int(FADE * sr), len(pieces[-1]), len(tail))
            if f > 0:
                ramp = np.linspace(1.0, 0.0, f, dtype=np.float32)
                pieces[-1][-f:] *= ramp
                tail[:f] *= ramp[::-1]
            pieces.append(tail)
            cursor = ib
        else:
            mid = ia + cur // 2
            pieces.append(y[cursor:mid])
            pieces.append(np.zeros(want - cur, dtype=np.float32))
            cursor = mid
        shift += (want - cur) / sr
        tmap.append((b, shift))
    pieces.append(y[cursor:])
    return np.concatenate(pieces), tmap


def shift_time(t: float, tmap: list[tuple[float, float]]) -> float:
    s = 0.0
    for old_t, sh in tmap:
        if t >= old_t:
            s = sh
    return t + s


def join_chunks(chunks: list[np.ndarray], sr: int, pauses: list[float], top_db: float = 40.0) -> np.ndarray:
    """Concatenate separately synthesised chunks with designed pauses.

    Each chunk's leading/trailing silence (including GPT-SoVITS' appended
    ``pause_second``) is trimmed with librosa, keeping EDGE_KEEP of natural
    onset/decay, then exactly ``pauses[i]`` of silence joins chunk i and i+1.
    """
    import librosa
    if len(pauses) != len(chunks) - 1:
        raise ValueError("need exactly one pause per join")
    keep = int(EDGE_KEEP * sr)
    out = []
    for i, c in enumerate(chunks):
        c = np.asarray(c, dtype=np.float32)
        frame, hop = _frames(sr)
        _, (s, e) = librosa.effects.trim(c, top_db=top_db, frame_length=frame, hop_length=hop)
        seg = c[max(0, s - keep):min(len(c), e + keep)].copy()
        f = min(int(FADE * sr), len(seg) // 2)
        if f > 0:
            seg[:f] *= np.linspace(0.0, 1.0, f, dtype=np.float32)
            seg[-f:] *= np.linspace(1.0, 0.0, f, dtype=np.float32)
        out.append(seg)
        if i < len(pauses):
            out.append(np.zeros(max(0, round(pauses[i] * sr) - 2 * keep), dtype=np.float32))
    return np.concatenate(out)
