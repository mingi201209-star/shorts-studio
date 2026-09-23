"""Generalized Korean speech-boundary planner.

The previous prosody planner (see prosody.py) required each scene's script
to be manually pre-split into phrases with a hand-authored boundary
("continuation"/"weak"/"medium"/"terminal") per phrase. That does not scale:
every future script would need the same manual tuning, and manual tuning is
exactly what produced the real, reported failure -- an unnatural pause
inserted after "1950년대" in "1950년대 세계 최초의 제트 여객기 코멧에는",
where a native speaker expects continuous flow because "1950년대" is
functioning as a temporal MODIFIER of the following noun phrase, not a
sentence-level topic frame.

This module classifies the boundary between every adjacent pair of Korean
어절 (whitespace-separated tokens) using deterministic lexical/morphological
pattern matching -- no heavyweight external dependency (no KoNLPy/Mecab,
which need a JVM or a compiled system dictionary that is fragile to install
in CI). It only recognizes SUFFIX PATTERNS that are general to Korean
grammar (sentence-final endings, clause-connective endings, the attributive
particle 의, numeral+counter constructions, etc.) -- nothing here is specific
to the Comet script's wording.

Design principle: DEFAULT TO CONTINUE. Over-segmentation (a pause after
every written clause) was the root complaint; under-segmentation (occasionally
missing a pause a native speaker would insert) is a much smaller problem for
a Shorts narration than the mechanical, uniformly-paused delivery this
replaces. A boundary is only escalated above CONTINUE when a specific,
general grammatical signal justifies it. Punctuation (a comma) is treated as
SUPPORTING evidence that nudges the boundary UP BY ONE LEVEL from whatever
the lexical signal alone would produce -- never as the sole rule, and it can
never manufacture a boundary stronger than STRONG_BOUNDARY.

Four boundary strengths (the vocabulary this task specifies):
  CONTINUE         - no inserted pause; effectively the same phrase.
  WEAK_BOUNDARY    - a very small, often inaudible natural break.
  PHRASE_BOUNDARY  - a normal semantic phrase break (written as a comma in
                     the reconstructed text; Edge's own natural handling of
                     a comma provides the pause -- no separate TTS call).
  STRONG_BOUNDARY  - a sentence / major discourse transition. This is the
                     ONLY boundary that ends a synthesis unit (a new Edge
                     TTS call with a real inserted silence before it) --
                     see prosody.group_into_units. Keeping CONTINUE/WEAK/
                     PHRASE all inside one synthesis unit is what avoids the
                     per-clause pitch/energy reset ("robotic stitching") a
                     separate call per written sentence caused.

This is a deterministic, explainable heuristic layer, not a full
morphological parser -- it does not disambiguate every case a real Korean
NLP toolkit would (see module docstring in tests/test_korean_boundary.py
for the specific cases it is verified against). It is written to be a
GENERAL Korean grammar layer: any future script's text runs through the
exact same rules with no per-script configuration.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

CONTINUE = "continue"
WEAK_BOUNDARY = "weak_boundary"
PHRASE_BOUNDARY = "phrase_boundary"
STRONG_BOUNDARY = "strong_boundary"

_LEVELS = [CONTINUE, WEAK_BOUNDARY, PHRASE_BOUNDARY, STRONG_BOUNDARY]

def _bump(level: str) -> str:
    i = _LEVELS.index(level)
    return _LEVELS[min(i + 1, len(_LEVELS) - 1)]

def boundary_max(a: str, b: str) -> str:
    """The stronger of two boundary levels."""
    return a if _LEVELS.index(a) >= _LEVELS.index(b) else b

# Sentence-final predicate endings (declarative/interrogative/exclamatory).
# General Korean conjugation patterns, not tied to any specific verb/script.
_SENTENCE_FINAL_SUFFIXES = (
    "습니다", "ㅂ니다", "였습니다", "했습니다", "합니다", "합니까", "습니까",
    "까요", "네요", "군요", "죠", "어요", "아요", "여요", "예요", "이에요",
    "은가요", "는가요", "을까요", "ㄴ다", "는다", "했다", "였다", "이다",
)

# Clause-connective endings that link two clauses. "Tight" connectives
# (simple sequencing/listing/simultaneity) get only a WEAK boundary; "loose"
# connectives (contrast, cause, condition) get a full PHRASE boundary.
_TIGHT_CONNECTIVE_SUFFIXES = ("고", "며", "면서")
_LOOSE_CONNECTIVE_SUFFIXES = (
    "는데", "은데", "지만", "니까", "으니까", "면", "으면", "라서", "아서",
    "어서", "해서", "다가", "거나", "든지", "도록", "기에", "자",
)

# The attributive/genitive particle -- always modifies the following noun,
# so a boundary here would split a modifier from what it modifies.
_ATTRIBUTIVE_SUFFIX = "의"

# General noun counters. A numeral immediately followed by one of these (or
# a token ending in one of these) forms a single numeral+counter phrase
# that must never be split -- independent of which specific number appears.
_COUNTER_WORDS = (
    "회", "번", "개", "명", "차례", "건", "년대", "년", "살", "개월", "일",
    "시", "분", "초", "페이지", "권", "장", "대", "척", "마리", "가지", "차",
    "세기", "킬로그램", "그램", "미터", "센티미터", "퍼센트", "달러", "원",
)

_NUMERAL_RE = re.compile(r"^[0-9][0-9,]*$")
_SINO_KOREAN_DIGIT = "일이삼사오육칠팔구천백십영"

def _is_bare_numeral(base: str) -> bool:
    if _NUMERAL_RE.match(base):
        return True
    return bool(base) and all(c in _SINO_KOREAN_DIGIT for c in base)

@dataclass(frozen=True)
class Token:
    raw: str          # as it appeared in the source text
    base: str         # with trailing comma/terminal punctuation stripped
    has_comma: bool
    has_terminal_punct: bool  # ., !, ?

def tokenize(text: str) -> list[Token]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    tokens = []
    for raw in text.split(" "):
        m = re.match(r"^(.*?)([,，]?)([.!?。！？]?)$", raw)
        base, comma, term = m.group(1), m.group(2), m.group(3)
        tokens.append(Token(raw=raw, base=base, has_comma=bool(comma), has_terminal_punct=bool(term)))
    return tokens

def _ends_with_any(base: str, suffixes: tuple[str, ...]) -> bool:
    return any(base.endswith(s) for s in suffixes)

def is_sentence_final(tok: Token) -> bool:
    """True when `tok` is grammatically a genuine sentence ending (not just
    a boundary that was floored to STRONG_BOUNDARY for some other reason,
    e.g. the focus-segment floor in prosody.plan_narration). Used to decide
    whether re-attaching a period to the reconstructed text is warranted --
    a chunk ending mid-sentence (like a REVEAL's anticipatory lead-in) must
    never get a period, or the reconstructed text becomes ungrammatical."""
    return tok.has_terminal_punct or _ends_with_any(tok.base, _SENTENCE_FINAL_SUFFIXES)

def classify_pair(prev: Token, nxt: Token | None) -> str:
    """The boundary strength immediately AFTER `prev` (and before `nxt`,
    which may be None at the end of the text). Driven primarily by `prev`'s
    own trailing morphology -- Korean prosodic phrasing is largely
    suffix-driven from the word that was just uttered."""
    if prev.has_terminal_punct:
        return STRONG_BOUNDARY
    if _ends_with_any(prev.base, _SENTENCE_FINAL_SUFFIXES):
        level = STRONG_BOUNDARY
    elif _ends_with_any(prev.base, _LOOSE_CONNECTIVE_SUFFIXES):
        level = PHRASE_BOUNDARY
    elif _ends_with_any(prev.base, _TIGHT_CONNECTIVE_SUFFIXES):
        level = WEAK_BOUNDARY
    elif prev.base.endswith(_ATTRIBUTIVE_SUFFIX):
        level = CONTINUE
    elif _ends_with_any(prev.base, _COUNTER_WORDS):
        level = CONTINUE
    elif _is_bare_numeral(prev.base):
        level = CONTINUE
    else:
        # Default bias: bare nouns, case/topic particles, adverbs, and
        # adnominal-conjugated modifiers all fall through here. This is
        # deliberate -- see module docstring. It is what keeps a temporal
        # modifier ("1950년대") flowing into the noun phrase it modifies,
        # and what keeps an adjective ("각진") attached to the noun it
        # modifies, without needing a hardcoded lexicon of adjectives.
        level = CONTINUE
    if prev.has_comma:
        level = _bump(level)
    return level

def analyze(text: str) -> list[tuple[Token, str]]:
    """Returns [(token, boundary_after_token), ...] for every token in
    `text`. The final token's boundary is always STRONG_BOUNDARY (the end
    of the given text is always a real stop)."""
    tokens = tokenize(text)
    out = []
    for i, tok in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        level = STRONG_BOUNDARY if nxt is None else classify_pair(tok, nxt)
        out.append((tok, level))
    return out

def reconstruct_chunks(text: str) -> list[str]:
    """Splits `text` into chunks at STRONG_BOUNDARY points, joining tokens
    within a chunk with a comma at PHRASE_BOUNDARY points and a plain space
    otherwise (CONTINUE/WEAK_BOUNDARY carry no explicit written marker --
    they stay in the same synthesis unit with no artificial pause). A chunk
    that ends on a genuine sentence-final token gets its period back."""
    pairs = analyze(text)
    chunks: list[str] = []
    cur: list[str] = []
    for tok, level in pairs:
        cur.append(tok.base)
        if level == PHRASE_BOUNDARY:
            cur[-1] = cur[-1] + ","
        if level == STRONG_BOUNDARY:
            if is_sentence_final(tok):
                cur[-1] = cur[-1] + "."
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks
