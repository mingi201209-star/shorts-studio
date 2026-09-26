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


# Real production feedback (published Titanic Short): "타이타닉에는 거대한
# 굴뚝이 네 개 있었습니다" is not a banned greeting/topic-announcement
# pattern, yet it is exactly the failure mode the Hook Contract exists to
# reject -- a flat descriptive/background statement with no result,
# contradiction, danger, question, or reversal for the viewer to react to
# in the first second. HOOK_TYPES names the mechanisms a real hook can use;
# TENSION_MARKERS is the textual evidence that at least one of them is
# actually present, so a hook can't just claim a type without earning it.
HOOK_TYPES = ("unexpected_result", "contradiction", "danger", "strong_question",
              "visible_anomaly", "intuition_reversal")

_DANGER_WORDS = ("위험", "죽", "폭발", "무너", "붕괴", "충돌", "재앙", "사망", "실종",
                 "화재", "익사", "추락", "파괴", "폭파", "치명")
# Short Korean stems (not full conjugated forms) so a marker matches
# regardless of tense/ending -- e.g. "무너" alone matches 무너지다/무너졌다/
# 무너지며. Chosen for common reversal/contrast/revelation phrasing in
# Korean narrative hooks specifically (정반대, 숨어, 몰랐, 드러났, 밝혀졌,
# 실은 등), not just literal English-hook-book translations.
_CONTRAST_WORDS = ("하지만", "그런데", "사실은", "실은", "알고 보니", "알고보니",
                    "생각과 달리", "놀랍", "믿기지", "충격", "반전", "가짜", "거짓",
                    "속인", "속였", "숨겨", "숨어", "숨긴", "아니었", "아니라", "뜻밖",
                    "예상과", "예상을", "예상 밖", "무려", "정반대", "반대로", "반대였",
                    "몰랐", "드러났", "밝혀졌", "밝혀진")
_ANOMALY_WORDS = ("이상한", "이상하게", "기이한", "설명할 수 없는", "정체불명", "미스터리",
                   "사라졌", "수수께끼", "저절로", "홀로", "스스로")

def has_tension_marker(text: str) -> bool:
    """True if `text` contains at least one real textual signal of an
    unexpected result / contradiction / danger / anomaly / reversal, or is
    phrased as a genuine question. A flat declarative fact (a plain "X had N
    of Y" sentence) has none of these and must not pass as a hook."""
    t = text or ""
    if t.rstrip().endswith("?") or t.rstrip().endswith("까요") or "까요?" in t:
        return True
    return any(w in t for w in _DANGER_WORDS + _CONTRAST_WORDS + _ANOMALY_WORDS)


def hook_violation(text: str) -> str | None:
    """Return a short reason string if `text` matches a banned hook opener
    OR carries no real tension marker at all (a flat descriptive/background
    sentence -- e.g. "there were four of X" -- which is the exact real
    failure mode a published production surfaced: not a banned greeting, but
    still nothing for the viewer to react to), else None. Only meant to be
    applied to the FIRST spoken phrase of a script/pitch -- these patterns
    are legitimate later in a video."""
    stripped = (text or "").strip()
    if not stripped:
        return "empty hook text"
    for pattern, reason in HOOK_BANNED_PATTERNS:
        if pattern.search(stripped):
            return reason
    if not has_tension_marker(stripped):
        return "no unexpected-result/contradiction/danger/question/anomaly signal (flat descriptive sentence)"
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
