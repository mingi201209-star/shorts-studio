"""Regression corpus for Korean Speech Planner V3 research.

This corpus separates normative pronunciation evidence from prosodic planning.
It is intentionally data-only in the first V3 slice: main synthesis behavior
must not change until the corpus and planner tests prove the change is safe.
"""

PRONUNCIATION_CASES = [
    # coda neutralization / liaison
    ("옷", "옫", "coda_neutralization"),
    ("낮", "낟", "coda_neutralization"),
    ("값이", "갑씨", "complex_coda_liaison"),
    ("닭을", "달글", "complex_coda_liaison"),
    # nasalization / liquid assimilation
    ("국물", "궁물", "nasalization"),
    ("밥물", "밤물", "nasalization"),
    ("신라", "실라", "liquid_assimilation"),
    # palatalization / aspiration / tensification
    ("같이", "가치", "palatalization"),
    ("좋다", "조타", "aspiration"),
    ("축하", "추카", "aspiration"),
    ("국밥", "국빱", "tensification"),
    ("학교", "학꾜", "tensification"),
]

# These spans should normally remain within one fluent prosodic phrase unless
# stronger syntactic/discourse evidence says otherwise. They are regression
# guards against the old "pause after a convenient token" failure mode.
PROSODIC_COHESION_CASES = [
    "1950년대 세계 최초의 제트 여객기 코멧에는",
    "약 천이백삼십 번의 실제 비행에 해당하는 시험을",
    "비행기 창문 모서리가 둥근 이유는",
]

# A boundary is not just silence. V3 will model these independently and only
# expose controls the selected TTS backend can actually realize.
PROSODIC_FEATURES = (
    "accentual_phrase",
    "intonational_phrase",
    "phrase_final_lengthening",
    "focus_prominence",
    "local_rate",
    "f0_contour",
    "pause",
)
