"""Shared, deterministic text rules for the retention-engine contracts
(Idea Gate, First-Second Hook Contract, Information Change Contract, Story
Progression, Runtime Discipline). Kept in one place so a topic-pitch
evaluated before any manifest exists and the actual rendered manifest are
judged by the exact same rules -- an idea that would fail the Hook Contract
after rendering must also fail the Idea Gate before anyone writes a script
for it.

Deliberately regex/keyword-based, not ML-based: this matches the rest of
the engine's QA style (e.g. final_video_qa._NARRATION_SEMANTIC_CATEGORIES),
stays dependency-free, and keeps every rule inspectable and testable rather
than a similarity score nobody can audit.
"""
from __future__ import annotations
import re

# A Short that opens with a greeting, a topic announcement, or "today we'll
# look at X" has already spent its first second on nothing -- the viewer
# hasn't been shown anything to be curious about yet. Matched against the
# very first narration phrase only (see idea_gate.py / final_video_qa.py).
HOOK_BANNED_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"안녕하세요|반갑습니다"), "greeting"),
    (re.compile(r"오늘은|이번\s*영상에서는|이번\s*시간에는"), "today-we-will-look-at framing"),
    (re.compile(r"알아보겠습니다|살펴보겠습니다|소개해\s*드리겠습니다|얘기해\s*보겠습니다|함께\s*보겠습니다"), "we-will-explore closing framing"),
    (re.compile(r"^(.{0,2}는|.{0,2}은)\s*(무엇일까요|뭘까요)\??$"), "bare topic-name question with no result shown"),
    (re.compile(r"들어가겠습니다|시작하겠습니다"), "let's-begin framing"),
]

# A first-beat visual requirement written this generically doesn't commit to
# showing an actual event or result -- it could be satisfied by almost any
# photo of the general subject, which is exactly the "meaningless
# establishing shot" the Hook Contract exists to reject.
GENERIC_ESTABLISHING_KEYWORDS = [
    "일반적인", "전형적인", "대표적인", "generic", "establishing shot", "개요", "전경",
]


def hook_violation(text: str) -> str | None:
    """Return a short reason string if `text` matches a banned hook opener,
    else None. Only meant to be applied to the FIRST spoken phrase of a
    script/pitch -- these patterns are legitimate later in a video."""
    stripped = (text or "").strip()
    if not stripped:
        return "empty hook text"
    for pattern, reason in HOOK_BANNED_PATTERNS:
        if pattern.search(stripped):
            return reason
    return None


def is_generic_establishing_text(text: str) -> bool:
    lowered = (text or "").lower()
    return any(kw.lower() in lowered for kw in GENERIC_ESTABLISHING_KEYWORDS)


_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[.,!?~…\"'()\[\]{}·:;-]")


def normalize_text(text: str) -> str:
    """Collapse whitespace/punctuation so near-identical sentences compare
    equal regardless of trivial formatting differences."""
    t = _PUNCT_RE.sub("", text or "")
    t = _WS_RE.sub(" ", t).strip().lower()
    return t


def token_overlap_ratio(a: str, b: str) -> float:
    """Symmetric token-overlap ratio in [0,1] -- a simple, deterministic
    near-duplicate proxy (no ML dependency). 1.0 means one is a token subset
    of the other or they share every token; 0.0 means no shared tokens."""
    ta = set(normalize_text(a).split())
    tb = set(normalize_text(b).split())
    if not ta or not tb:
        return 0.0
    shared = len(ta & tb)
    return shared / min(len(ta), len(tb))


def is_near_duplicate_text(a: str, b: str, threshold: float = 0.8) -> bool:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return token_overlap_ratio(na, nb) >= threshold
