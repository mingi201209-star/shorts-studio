from shorts_studio.korean_speech_corpus import (
    LENGTH_METADATA_POLICY,
    PRONUNCIATION_CASES,
    PROSODIC_COHESION_CASES,
    PROSODIC_FEATURES,
)


def test_v3_pronunciation_corpus_has_unique_surface_rule_pairs():
    keys = [(case.surface, case.article, case.rule) for case in PRONUNCIATION_CASES]
    assert len(keys) == len(set(keys))
    assert all(case.surface and case.readings and case.rule for case in PRONUNCIATION_CASES)
    assert all(all(reading for reading in case.readings) for case in PRONUNCIATION_CASES)


def test_v3_corpus_covers_context_sensitive_rule_families():
    rules = {case.rule for case in PRONUNCIATION_CASES}
    assert {
        "coda_neutralization",
        "complex_coda_exception",
        "h_aspiration",
        "h_deletion_before_vowel",
        "liaison",
        "complex_coda_liaison",
        "palatalization",
        "nasalization",
        "liquid_assimilation",
        "tensification",
        "n_insertion",
        "saisiot_n_insertion",
    } <= rules


def test_v3_preserves_rule_provenance_and_allowed_variants():
    articles = {case.article for case in PRONUNCIATION_CASES}
    assert {9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 23, 24, 25, 26, 27, 28, 29, 30} <= articles
    variants = {case.surface: case.readings for case in PRONUNCIATION_CASES if len(case.readings) > 1}
    assert variants["맛있다"] == ("마딛따", "마싣따")
    assert variants["금융"] == ("금늉", "그뮹")
    assert variants["냇가"] == ("내까", "낻까")


def test_v3_does_not_treat_h_as_one_blanket_deletion_rule():
    h_rules = {case.rule for case in PRONUNCIATION_CASES if case.article == 12}
    assert {"h_aspiration", "h_nasal_assimilation", "h_deletion_before_vowel"} <= h_rules


def test_v3_requires_morphology_for_context_sensitive_tensification():
    case = next(c for c in PRONUNCIATION_CASES if c.surface == "신고")
    assert case.article == 24
    assert "morphology" in case.note


def test_v3_keeps_normative_length_metadata_separate_from_tts_control():
    assert LENGTH_METADATA_POLICY == "preserve_normative_metadata_do_not_force_tts"


def test_v3_keeps_pronunciation_separate_from_prosody():
    assert "pause" in PROSODIC_FEATURES
    assert "f0_contour" in PROSODIC_FEATURES
    assert "phrase_final_lengthening" in PROSODIC_FEATURES
    assert len(PROSODIC_COHESION_CASES) >= 3
