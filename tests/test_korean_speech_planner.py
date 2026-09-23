from shorts_studio.prosody import PhraseSpec
from shorts_studio.korean_speech_planner import adjust_rate, analyze_unit


def test_short_unit_keeps_base_rate():
    f = analyze_unit([PhraseSpec(role="SETUP", text="짧은 문장입니다.")])
    assert f.rate_delta_pct == 0
    assert adjust_rate("+6%", f) == "+6%"


def test_long_unit_eases_rate_without_new_boundary():
    text = "비행기 창문 모서리가 둥근 이유는 반복되는 압력 변화가 기체에 집중시키는 힘을 줄이기 위해서입니다."
    f = analyze_unit([PhraseSpec(role="EXPLANATION", text=text)])
    assert f.syllables >= 28
    assert f.rate_delta_pct == -2
    assert adjust_rate("+4%", f) == "+2%"


def test_focus_payload_gets_bounded_local_ease_and_prominence_metadata():
    f = analyze_unit([PhraseSpec(role="REVEAL", text="문제는 네모난 창문 모서리였습니다.", focus=True)])
    assert f.focus
    assert f.rate_delta_pct <= -2
    assert f.phrase_final_lengthening >= 1.10
    assert f.f0_intent == "focus_prominence"


def test_rate_adjustment_is_safely_bounded():
    f = analyze_unit([PhraseSpec(role="HOOK", text="가" * 40, focus=True)])
    assert adjust_rate("+12%", f) == "+8%"
    assert adjust_rate("-5%", f) == "-5%"


def test_non_percent_escape_hatch_is_preserved():
    f = analyze_unit([PhraseSpec(role="SETUP", text="가" * 40)])
    assert adjust_rate("fast", f) == "fast"
