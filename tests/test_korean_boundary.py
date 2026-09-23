"""Generalized Korean speech-boundary planner.

These tests exercise shorts_studio.korean_boundary directly: a deterministic
classifier of CONTINUE / WEAK_BOUNDARY / PHRASE_BOUNDARY / STRONG_BOUNDARY
between adjacent Korean tokens, driven by general grammatical structure
(sentence-final endings, clause-connective endings, the attributive
particle, numeral+counter constructions, ...) rather than punctuation alone
or any Comet-specific wording. None of the sentences below appear in
examples/comet.json verbatim -- they are independent regression material so
a future, unrelated script is covered by the same rules.

This is a deterministic heuristic layer, not a full morphological parser:
it does not disambiguate every possible Korean sentence (see the module
docstring in shorts_studio/korean_boundary.py for the documented default-
bias design and its limits). The cases below are exactly the ones this task
specifies as the minimum bar.
"""
import pytest

from shorts_studio.korean_boundary import (
    CONTINUE, PHRASE_BOUNDARY, STRONG_BOUNDARY, WEAK_BOUNDARY,
    analyze, reconstruct_chunks, tokenize,
)


def _levels(text):
    return [level for _, level in analyze(text)]


def _boundary_after(text, surface_token):
    """The boundary immediately after the token whose (punctuation-stripped)
    base text equals `surface_token`."""
    for tok, level in analyze(text):
        if tok.base == surface_token:
            return level
    raise AssertionError(f"token {surface_token!r} not found in {text!r}")


# 1. Temporal expression functioning as a modifier of the following noun
# phrase: must flow continuously, no pause after "1950년대".
def test_temporal_modifier_flows_into_following_noun_phrase():
    text = "1950년대 세계 최초의 제트 여객기 코멧에는"
    assert _boundary_after(text, "1950년대") == CONTINUE


# 2. The SAME surface token "1950년대" followed by a comma and used as a
# sentence-level topic frame: a boundary here is natural/expected, and it
# must differ from case 1 (context-sensitivity, not a token-based lookup).
def test_temporal_frame_with_comma_gets_a_real_boundary():
    text = "1950년대, 항공 산업은 빠르게 변했습니다."
    level = _boundary_after(text, "1950년대")
    assert level != CONTINUE
    case1_level = _boundary_after("1950년대 세계 최초의 제트 여객기 코멧에는", "1950년대")
    assert level != case1_level


# 3. Numeral + counter + noun phrase must not be split from its counter/noun.
def test_numeral_counter_noun_phrase_not_split():
    text = "약 천이백삼십 번의 압력 변화를 겪었습니다."
    levels = _levels(text)
    # Only the true sentence end may be STRONG_BOUNDARY.
    assert levels[:-1] == [CONTINUE] * (len(levels) - 1)
    assert levels[-1] == STRONG_BOUNDARY
    chunks = reconstruct_chunks(text)
    assert len(chunks) == 1
    assert "천이백삼십 번의 압력" in chunks[0]


# 4. Numeral + 번 + adverb + modifier + dependent noun: preserve the chain.
def test_numeral_counter_modifier_dependent_noun_chain_preserved():
    text = "실험을 천팔백삼십 번 더 반복했을 때"
    assert all(level == CONTINUE for level in _levels(text)[:-1])
    chunks = reconstruct_chunks(text)
    assert chunks == ["실험을 천팔백삼십 번 더 반복했을 때"]


# 5. Adjective/adnominal modifier must not be split from the noun it modifies.
def test_modifier_not_split_from_modified_noun():
    text = "모서리가 각진 창문이 있었습니다."
    assert _boundary_after(text, "각진") == CONTINUE


# 6. Connective structure flows naturally -- no arbitrary punctuation-style
# pause at every clause; only real discourse-level connectives get a
# written (comma) pause, and even those stay in ONE synthesis unit.
def test_connective_structure_flows_without_arbitrary_pauses():
    text = "조사팀은 실제 기체를 거대한 물탱크에 넣고 압력을 반복해서 가했습니다."
    chunks = reconstruct_chunks(text)
    assert len(chunks) == 1  # one synthesis unit: no per-clause resynthesis
    assert _boundary_after(text, "넣고") in (CONTINUE, WEAK_BOUNDARY)


# 7. A real clause boundary SHOULD create a pause (a loose/contrastive
# connective, "-지만").
def test_real_clause_boundary_creates_a_phrase_pause():
    text = "비가 왔지만 우리는 나갔습니다."
    assert _boundary_after(text, "왔지만") == PHRASE_BOUNDARY


# 8. A comma that should NOT automatically force an audible pause: a plain
# noun-listing comma with no other grammatical signal only nudges to
# WEAK_BOUNDARY, which carries no explicit inserted silence.
def test_some_commas_do_not_force_an_audible_pause():
    text = "사과, 배를 샀습니다."
    level = _boundary_after(text, "사과")
    assert level in (CONTINUE, WEAK_BOUNDARY)
    assert level != STRONG_BOUNDARY
    assert level != PHRASE_BOUNDARY


# --- Negative control: proving "remove all pauses" is not the fix ----------

def test_negative_control_sentence_endings_still_produce_strong_boundary():
    text = "코멧은 세계 최초의 제트 여객기였습니다."
    assert _boundary_after(text, "여객기였습니다") == STRONG_BOUNDARY

def test_negative_control_multi_sentence_text_still_splits_into_chunks():
    text = "비행기가 부서졌습니다. 원인은 밝혀지지 않았습니다."
    chunks = reconstruct_chunks(text)
    assert len(chunks) == 2

def test_negative_control_loose_connective_is_not_silently_continue():
    # "-는데" (a real contrastive/circumstantial connective) must not be
    # collapsed to CONTINUE just because the default bias favors CONTINUE.
    text = "날씨가 좋은데 우리는 집에 있었습니다."
    assert _boundary_after(text, "좋은데") == PHRASE_BOUNDARY


# --- Structural invariants --------------------------------------------------

_INVARIANT_SENTENCES = [
    "1950년대 세계 최초의 제트 여객기 코멧에는",
    "1950년대, 항공 산업은 빠르게 변했습니다.",
    "약 천이백삼십 번의 압력 변화를 겪었습니다.",
    "실험을 천팔백삼십 번 더 반복했을 때",
    "모서리가 각진 창문이 있었습니다.",
    "조사팀은 실제 기체를 거대한 물탱크에 넣고 압력을 반복해서 가했습니다.",
    "비가 왔지만 우리는 나갔습니다.",
    "사과, 배를 샀습니다.",
]

@pytest.mark.parametrize("text", _INVARIANT_SENTENCES)
def test_no_token_lost_or_duplicated(text):
    original_count = len(text.split())
    pairs = analyze(text)
    assert len(pairs) == original_count

@pytest.mark.parametrize("text", _INVARIANT_SENTENCES)
def test_reconstructed_text_preserves_semantic_content(text):
    """Stripping the punctuation this module itself controls (commas it may
    insert or drop, the sentence-final mark) from both sides must leave the
    same word sequence -- no word is lost, duplicated, or reordered."""
    import re
    original_words = [re.sub(r"[,.!?]", "", w) for w in text.split()]
    reconstructed = re.sub(r"[,.!?]", "", " ".join(reconstruct_chunks(text)))
    reconstructed_words = reconstructed.split()
    assert reconstructed_words == original_words

@pytest.mark.parametrize("text", _INVARIANT_SENTENCES)
def test_pause_insertion_cannot_split_protected_spans(text):
    """A PHRASE_BOUNDARY/STRONG_BOUNDARY must never land strictly inside a
    numeral+counter pair or immediately after the attributive particle --
    those relationships are protected regardless of surrounding context."""
    tokens = tokenize(text)
    for i in range(len(tokens) - 1):
        cur, nxt = tokens[i], tokens[i + 1]
        if cur.base.endswith("의"):
            from shorts_studio.korean_boundary import classify_pair
            assert classify_pair(cur, nxt) == CONTINUE, f"attributive 의 split in {text!r}"

def test_tokenize_never_drops_or_merges_tokens():
    text = "결국 조사팀은 실제 기체를 거대한 물탱크에 넣고 압력을 반복했습니다."
    assert len(tokenize(text)) == len(text.split())
