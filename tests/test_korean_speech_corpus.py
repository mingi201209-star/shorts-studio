from shorts_studio.korean_speech_corpus import (
    PRONUNCIATION_CASES,
    PROSODIC_COHESION_CASES,
    PROSODIC_FEATURES,
)


def test_v3_pronunciation_corpus_has_unique_inputs_and_expected_forms():
    inputs = [surface for surface, _, _ in PRONUNCIATION_CASES]
    assert len(inputs) == len(set(inputs))
    assert all(surface and spoken and rule for surface, spoken, rule in PRONUNCIATION_CASES)


def test_v3_corpus_covers_core_context_sensitive_rules():
    rules = {rule for _, _, rule in PRONUNCIATION_CASES}
    assert {
        "coda_neutralization",
        "complex_coda_liaison",
        "nasalization",
        "liquid_assimilation",
        "palatalization",
        "aspiration",
        "tensification",
    } <= rules


def test_v3_keeps_pronunciation_separate_from_prosody():
    # Correct phonology alone cannot define where a narrator should breathe.
    assert "pause" in PROSODIC_FEATURES
    assert "f0_contour" in PROSODIC_FEATURES
    assert "phrase_final_lengthening" in PROSODIC_FEATURES
    assert len(PROSODIC_COHESION_CASES) >= 3
