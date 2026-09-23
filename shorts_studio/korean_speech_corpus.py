"""Normative regression corpus for Korean Speech Planner V3.

The source material is organized by Standard Pronunciation Rule article so
production code can explain *why* a reading is expected.  This module remains
data-only: orthography is never rewritten before TTS merely because a
pronunciation spelling appears here.

Multiple allowed readings are represented as tuples.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PronunciationCase:
    surface: str
    readings: tuple[str, ...]
    article: int
    rule: str
    note: str = ""


PRONUNCIATION_CASES = (
    # Articles 8-11: coda neutralization and complex codas.
    PronunciationCase("옷", ("옫",), 9, "coda_neutralization"),
    PronunciationCase("낮", ("낟",), 9, "coda_neutralization"),
    PronunciationCase("닭", ("닥",), 11, "complex_coda"),
    PronunciationCase("맑게", ("말께",), 11, "complex_coda_exception"),
    PronunciationCase("밟다", ("밥따",), 10, "complex_coda_exception"),
    PronunciationCase("넓죽하다", ("넙쭈카다",), 10, "complex_coda_exception"),

    # Article 12: /h/ is context-sensitive; do not collapse it into deletion.
    PronunciationCase("좋다", ("조타",), 12, "h_aspiration"),
    PronunciationCase("축하", ("추카",), 12, "h_aspiration"),
    PronunciationCase("놓는", ("논는",), 12, "h_nasal_assimilation"),
    PronunciationCase("낳은", ("나은",), 12, "h_deletion_before_vowel"),

    # Articles 13-15: liaison differs by morphological boundary.
    PronunciationCase("옷이", ("오시",), 13, "liaison"),
    PronunciationCase("값이", ("갑씨",), 14, "complex_coda_liaison"),
    PronunciationCase("닭을", ("달글",), 14, "complex_coda_liaison"),
    PronunciationCase("밭 아래", ("바다래",), 15, "lexical_morpheme_liaison"),
    PronunciationCase("맛있다", ("마딛따", "마싣따"), 15, "allowed_variant"),

    # Articles 17-20: palatalization, nasalization and liquid interactions.
    PronunciationCase("같이", ("가치",), 17, "palatalization"),
    PronunciationCase("국물", ("궁물",), 18, "nasalization"),
    PronunciationCase("밥물", ("밤물",), 18, "nasalization"),
    PronunciationCase("막론", ("망논",), 19, "l_to_n_then_nasalization"),
    PronunciationCase("협력", ("혐녁",), 19, "l_to_n_then_nasalization"),
    PronunciationCase("신라", ("실라",), 20, "liquid_assimilation"),
    PronunciationCase("칼날", ("칼랄",), 20, "liquid_assimilation"),
    PronunciationCase("공권력", ("공꿘녁",), 20, "lexicalized_liquid_exception"),

    # Articles 23-28: tensification needs grammatical/morphological context.
    PronunciationCase("국밥", ("국빱",), 23, "tensification"),
    PronunciationCase("학교", ("학꾜",), 23, "tensification"),
    PronunciationCase("신고", ("신꼬",), 24, "verb_stem_tensification",
                      "Verb stem + ending reading; morphology is required."),
    PronunciationCase("안기다", ("안기다",), 24, "causative_passive_exception"),
    PronunciationCase("넓게", ("널께",), 25, "complex_coda_tensification"),
    PronunciationCase("갈등", ("갈뜽",), 26, "sino_korean_tensification"),
    PronunciationCase("할 수는", ("할쑤는",), 27, "adnominal_l_tensification"),
    PronunciationCase("문고리", ("문꼬리",), 28, "compound_tensification"),

    # Articles 29-30: insertion and 사이시옷.
    PronunciationCase("꽃잎", ("꼰닙",), 29, "n_insertion"),
    PronunciationCase("서울역", ("서울력",), 29, "n_insertion_liquid_assimilation"),
    PronunciationCase("금융", ("금늉", "그뮹"), 29, "allowed_variant"),
    PronunciationCase("냇가", ("내까", "낻까"), 30, "saisiot_tensification"),
    PronunciationCase("깻잎", ("깬닙",), 30, "saisiot_n_insertion"),
)

# Standard length is normative metadata, not a blanket modern narration
# control. V3 may use it only after reference-audio/A-B evidence supports it.
LENGTH_METADATA_POLICY = "preserve_normative_metadata_do_not_force_tts"

# Spans that should normally remain fluent unless stronger syntactic/discourse
# evidence establishes a boundary.
PROSODIC_COHESION_CASES = (
    "1950년대 세계 최초의 제트 여객기 코멧에는",
    "약 천이백삼십 번의 실제 비행에 해당하는 시험을",
    "비행기 창문 모서리가 둥근 이유는",
)

PROSODIC_FEATURES = (
    "accentual_phrase",
    "intonational_phrase",
    "phrase_final_lengthening",
    "focus_prominence",
    "local_rate",
    "f0_contour",
    "pause",
)
