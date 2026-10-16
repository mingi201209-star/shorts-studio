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


# --- One take for a whole Short ------------------------------------------
#
# Edge synthesizes every sentence end with about the same 0.7-0.9 s pause, and
# a Short rendered one scene per call starts each scene from a fresh contour
# with only the scene's own edge trim between them. Measured on the three
# passing pipeline Shorts of 2026-10-14 (ffmpeg silencedetect, -40 dB), the
# scene joins -- the largest turns of the story -- got 0.35-0.51 s while the
# sentence ends inside a scene got 0.72-0.89 s. One call for the whole script
# keeps one contour; the pauses are then set by meaning: a scene turn is the
# longest, a sentence end shorter, and a clause pause is only ever capped.
TAKE_PAUSES = {"sentence": 0.50, "scene": 0.65}
TAKE_CLAUSE_MAX = 0.30
# Edge's WordBoundary end of a sentence-final word runs ~0.3 s into the pause
# that follows it, so a boundary's silence is searched from the word's start.
_SENTENCE_END = re.compile(r"[.?!…][\"'”’)\]]*$")


def is_sentence_end(token: str) -> bool:
    return bool(_SENTENCE_END.search(token))


@dataclass(frozen=True)
class TakeScene:
    words: list[tuple[str, float, float]]   # scene-relative (text, start, end)
    start: float                            # sample-accurate cut in the retimed take
    end: float


def plan_take_gaps(silences: list[tuple[float, float]], words: list[tuple[str, float, float]],
                   scene_ends: list[int], targets: dict[str, float] = TAKE_PAUSES,
                   clause_max: float = TAKE_CLAUSE_MAX) -> list[tuple[float, float, float]]:
    """(start, end, target) for every detected silence of a one-call take.

    A sentence or scene end claims the longest silence that begins between its
    last word's start and the next word's start (Edge places a word's start
    ~0.1 s before its audible onset, so the silence may end after it); every other silence is a clause pause
    and is only shortened, never lengthened. A scene end with no silence fails
    closed: the scene cut would land in running speech. A sentence end the
    voice ran through stays connected.
    """
    if any(i < 0 or i >= len(words) - 1 for i in scene_ends):
        raise ValueError(f"scene end indexes {scene_ends} must fall before the last of {len(words)} words")
    scene_set = set(scene_ends)
    claimed: dict[int, str] = {}
    for i in range(len(words) - 1):
        kind = "scene" if i in scene_set else "sentence" if is_sentence_end(words[i][0]) else None
        if kind is None:
            continue
        lo, hi = words[i][1], words[i + 1][1]
        inside = [(b - a, k) for k, (a, b) in enumerate(silences)
                  if k not in claimed and lo <= a < hi]
        if not inside:
            if kind == "scene":
                raise ValueError(f"no pause found at the scene turn after {words[i][0]!r} "
                                 f"({lo:.2f}-{hi:.2f}s); refusing to cut a scene in running speech")
            continue
        claimed[max(inside)[1]] = kind
    out = []
    for k, (a, b) in enumerate(silences):
        kind = claimed.get(k)
        out.append((a, b, targets[kind] if kind else min(b - a, clause_max)))
    return out


def retime_map(sr: int, gaps: list[tuple[float, float, float]]):
    """Exact old->new time map of :func:`retime_silences` for the same gaps.

    shift_time() moves a time by whole gaps, which is right for a recogniser's
    word times that sit on speech. A provider's word times can sit inside a
    pause (Edge starts a word ~0.1 s before its onset and ends a sentence
    ~0.3 s into the pause), so this follows the splice itself: the kept onset
    and decay move with their speech, and the removed middle of a shortened
    pause collapses to the splice point.
    """
    keep = int(EDGE_KEEP * sr)
    spans, shift = [], 0
    for a, b, target in sorted(gaps):
        ia, ib = round(a * sr), round(b * sr)
        cur, want = ib - ia, max(0, round(target * sr))
        if want == cur:
            continue
        if want < cur:
            k = min(keep, want // 2, cur // 2)
            left_end, right_start = ia + k, ib - (want - k)
        else:
            left_end = right_start = ia + cur // 2
        after = shift + (want - cur)
        spans.append((left_end, right_start, shift, after))
        shift = after

    def to_new(t: float) -> float:
        n, moved = t * sr, 0
        for left_end, right_start, before, after in spans:
            if n <= left_end:
                return (n + before) / sr
            if n < right_start:
                return (left_end + before) / sr
            moved = after
        return (n + moved) / sr

    return to_new


def split_take(y: np.ndarray, sr: int, words: list[tuple[str, float, float]], scene_ends: list[int],
               gaps: list[tuple[float, float, float]], tail: float = 0.08) -> tuple[np.ndarray, list[TakeScene]]:
    """Retime the take's silences and cut it into scenes.

    Word times are the provider's own, moved only by the silence edits
    (:func:`retime_map`); an end that ran into a shortened pause is clamped to
    the next word's start. Each
    scene ends ``tail`` after its last word end -- the same rule render uses for
    a scene's length -- and the rest of the turn pause opens the next scene, so
    the picture changes just before the next sentence is spoken.
    """
    out, _ = retime_silences(y, sr, gaps)
    to_new = retime_map(sr, gaps)
    starts = [to_new(s) for _, s, _ in words]
    moved = []
    for i, (text, _s, e) in enumerate(words):
        end = to_new(e)
        if i + 1 < len(words):
            end = min(end, starts[i + 1])
        end = min(max(end, starts[i] + 0.01), len(out) / sr)
        moved.append((text, starts[i], end))
    cuts = [0]
    for i in scene_ends:
        cut = min(moved[i][2] + tail, moved[i + 1][1])
        cuts.append(round(cut * sr))
    cuts.append(len(out))
    scenes, first = [], 0
    bounds = list(scene_ends) + [len(words) - 1]
    for k, last in enumerate(bounds):
        a, b = cuts[k], cuts[k + 1]
        if b <= a:
            raise ValueError(f"scene {k} has no audio after retiming")
        offset = a / sr
        scene_words = [(t, max(0.0, s - offset), max(0.0, e - offset)) for t, s, e in moved[first:last + 1]]
        scenes.append(TakeScene(scene_words, offset, b / sr))
        first = last + 1
    return out, scenes
