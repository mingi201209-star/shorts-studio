"""Prompt V2: hook generation/judging separation and Story Prompt V2's
curiosity-maintenance check. See shorts_studio/hook_studio.py's module
docstring for the product principle and architecture this tests."""
from types import SimpleNamespace

import pytest

from shorts_studio import entertainment_qa as eqa
from shorts_studio.hook_studio import (
    HOOK_STRATEGIES, MIN_STRATEGY_FACTS, TopicBrief, HookCandidate,
    TemplateHookGenerator, RuleBasedHookJudge, AnthropicHookJudge,
    reject_hook_candidate, is_grounded_claim, generate_and_judge,
    verify_curiosity_maintained, build_story_generation_prompt,
    story_writer_system_prompt,
)
from shorts_studio.retention_rules import (
    is_bare_why_question, has_generic_cta, reveals_payoff_prematurely,
    tension_marker_strength, HOOK_TYPES,
)


def _full_brief(**overrides) -> TopicBrief:
    defaults = dict(
        topic_id="t1",
        familiar_subject="유리컵",
        contradiction_fact="뜨거운 물을 부으면 멀쩡한데 얼음물을 부으면 깨집니다",
        surprising_consequence_fact="급격한 온도차가 유리 표면에 순간적인 장력을 만듭니다",
        counterintuitive_fact="두꺼운 유리컵이 얇은 유리컵보다 더 쉽게 깨지기도 합니다",
        anomaly_fact="깨진 단면을 보면 항상 같은 방향의 균열이 나타납니다",
        mistaken_assumption_fact="사람들은 유리가 두꺼우면 무조건 튼튼하다고 생각합니다",
        cause_effect_fact="유리 안쪽과 바깥쪽이 서로 다른 속도로 수축합니다",
        payoff_text="실은 유리 안팎의 수축 속도 차이가 만드는 장력이 한계를 넘으면 컵이 깨집니다",
        grounded_facts=["열충격에 강한 내열유리는 이 수축 속도 차이를 줄이도록 설계됩니다"],
    )
    defaults.update(overrides)
    return TopicBrief(**defaults)


# --- retention_rules additions ---------------------------------------------

def test_hook_types_extended_additively():
    for strategy in HOOK_STRATEGIES:
        assert strategy in HOOK_TYPES
    # original six untouched
    for original in ("unexpected_result", "contradiction", "danger", "strong_question",
                      "visible_anomaly", "intuition_reversal"):
        assert original in HOOK_TYPES


def test_is_bare_why_question_flags_question_mark_only_tension():
    assert is_bare_why_question("전자레인지 문에는 왜 검은 점들이 있을까?")
    assert is_bare_why_question("기차 바퀴는 왜 원뿔 모양일까?")


def test_is_bare_why_question_allows_real_tension_marker_present():
    assert not is_bare_why_question("멀쩡해 보이는데 왜 갑자기 무너졌을까?")  # 무너 (danger stem)
    assert not is_bare_why_question("믿기지 않게도, 두꺼운 유리가 왜 더 쉽게 깨질까?")  # 믿기지 (contrast word)
    assert not is_bare_why_question("전자레인지 문의 검은 점, 정체는?")  # not even a 왜-question


def test_is_bare_why_question_false_for_non_question():
    assert not is_bare_why_question("검은 점은 장식이 아닙니다")


def test_has_generic_cta_detects_banned_endings():
    assert has_generic_cta("댓글로 알려주세요")
    assert has_generic_cta("여러분 생각은 어떠신가요")
    assert has_generic_cta("구독과 좋아요 부탁드립니다")


def test_has_generic_cta_false_for_normal_ending():
    assert not has_generic_cta("그 균열은 지금도 모든 유리컵 안에 숨어 있습니다")


def test_reveals_payoff_prematurely_true_for_high_overlap():
    payoff = "유리 안팎의 수축 속도 차이가 만드는 장력이 한계를 넘으면 컵이 깨집니다"
    assert reveals_payoff_prematurely(payoff, payoff)


def test_reveals_payoff_prematurely_false_for_distinct_hook():
    hook = "뜨거운 물엔 멀쩡한 유리컵이 왜 얼음물엔 깨질까?"
    payoff = "유리 안팎의 수축 속도 차이가 만드는 장력이 한계를 넘으면 컵이 깨집니다"
    assert not reveals_payoff_prematurely(hook, payoff)


def test_tension_marker_strength_counts_distinct_markers():
    assert tension_marker_strength("정상 상태입니다") == 0
    assert tension_marker_strength("하지만 사실은 놀랍게도 반전이었습니다") >= 2


# --- TemplateHookGenerator ---------------------------------------------------

def test_template_generator_produces_one_candidate_per_available_strategy():
    brief = _full_brief()
    candidates = TemplateHookGenerator().generate(brief)
    assert len(candidates) == 6
    assert {c.strategy for c in candidates} == set(HOOK_STRATEGIES)
    for c in candidates:
        assert brief.familiar_subject in c.text


def test_template_generator_skips_missing_facts():
    brief = _full_brief(anomaly_fact=None, mistaken_assumption_fact=None, cause_effect_fact=None)
    candidates = TemplateHookGenerator().generate(brief)
    assert {c.strategy for c in candidates} == {"contradiction", "surprising_consequence", "counterintuitive_fact"}


def test_template_generator_candidates_are_not_trivial_paraphrases():
    brief = _full_brief()
    candidates = TemplateHookGenerator().generate(brief)
    texts = [c.text for c in candidates]
    assert len(set(texts)) == len(texts)  # every candidate text is distinct


# --- reject_hook_candidate ---------------------------------------------------

def test_reject_hook_candidate_accepts_good_candidate():
    brief = _full_brief()
    c = HookCandidate(strategy="contradiction", text="생각과 달리, 뜨거운 물엔 멀쩡한 유리컵이 얼음물엔 깨집니다",
                       grounded_in=brief.contradiction_fact)
    assert reject_hook_candidate(c, brief) is None


def test_reject_hook_candidate_rejects_greeting_opener():
    brief = _full_brief()
    c = HookCandidate(strategy="contradiction", text="안녕하세요, 오늘은 유리컵 이야기입니다",
                       grounded_in=brief.contradiction_fact)
    assert reject_hook_candidate(c, brief) is not None


def test_reject_hook_candidate_rejects_bare_why_question():
    brief = _full_brief()
    c = HookCandidate(strategy="unresolved_cause_effect", text="유리컵은 왜 가끔 깨질까?",
                       grounded_in=brief.cause_effect_fact)
    reason = reject_hook_candidate(c, brief)
    assert reason is not None and "information gap" in reason


def test_reject_hook_candidate_rejects_subject_announcement():
    brief = _full_brief()
    c = HookCandidate(strategy="contradiction", text="이것은 유리컵입니다", grounded_in=brief.contradiction_fact)
    assert reject_hook_candidate(c, brief) is not None


def test_reject_hook_candidate_rejects_premature_payoff():
    brief = _full_brief()
    c = HookCandidate(strategy="contradiction", text=brief.payoff_text, grounded_in=brief.contradiction_fact)
    reason = reject_hook_candidate(c, brief)
    assert reason is not None and "payoff" in reason


def test_reject_hook_candidate_rejects_ungrounded_claim():
    brief = _full_brief()
    c = HookCandidate(strategy="contradiction", text="유리컵 안에는 사실 외계 신호가 숨어 있습니다",
                       grounded_in="유리컵은 외계 신호를 수신하는 안테나입니다")
    reason = reject_hook_candidate(c, brief)
    assert reason is not None and "grounded" in reason.lower() or "unsupported" in (reason or "")


def test_is_grounded_claim_true_for_declared_fact_paraphrase():
    brief = _full_brief()
    c = HookCandidate(
        strategy="contradiction",
        text="생각과 달리 뜨거운 물을 부으면 멀쩡한 유리컵도 얼음물에서는 깨질 수 있습니다",
        grounded_in=brief.contradiction_fact,
    )
    assert is_grounded_claim(c, brief)


def test_grounding_cannot_be_laundered_through_truthful_grounded_in():
    brief = _full_brief()
    c = HookCandidate(
        strategy="contradiction",
        text="유리컵 안에는 사실 외계 신호가 숨어 있습니다",
        grounded_in=brief.contradiction_fact,
    )
    assert not is_grounded_claim(c, brief)
    reason = reject_hook_candidate(c, brief)
    assert reason is not None and ("grounded" in reason.lower() or "unsupported" in reason.lower())


def test_grounding_must_match_candidates_own_strategy_fact():
    brief = _full_brief()
    c = HookCandidate(
        strategy="contradiction",
        text="놀랍게도 두꺼운 유리컵이 얇은 유리컵보다 더 쉽게 깨지기도 합니다",
        grounded_in=brief.counterintuitive_fact,
    )
    assert not is_grounded_claim(c, brief)


# --- RuleBasedHookJudge ------------------------------------------------------

def test_rule_based_judge_filters_and_never_defaults_to_first_candidate():
    brief = _full_brief()
    bad = HookCandidate(strategy="contradiction", text="안녕하세요 유리컵 이야기입니다", grounded_in=brief.contradiction_fact)
    good = HookCandidate(strategy="surprising_consequence", text="놀랍게도, 유리컵에 급격한 온도차를 주면 저절로 깨집니다",
                          grounded_in=brief.surprising_consequence_fact)
    result = RuleBasedHookJudge().judge([bad, good], brief)
    assert result.winner is not None
    assert result.winner.text == good.text
    statuses = {v.candidate.text: v.status for v in result.verdicts}
    assert statuses[bad.text] == "REJECTED"
    assert statuses[good.text] == "SURVIVED"


def test_rule_based_judge_no_survivors_gives_no_winner():
    brief = _full_brief()
    bad1 = HookCandidate(strategy="contradiction", text="안녕하세요", grounded_in=brief.contradiction_fact)
    bad2 = HookCandidate(strategy="surprising_consequence", text="오늘은 살펴보겠습니다", grounded_in=brief.surprising_consequence_fact)
    result = RuleBasedHookJudge().judge([bad1, bad2], brief)
    assert result.winner is None


def test_rule_based_judge_is_deterministic():
    brief = _full_brief()
    candidates = TemplateHookGenerator().generate(brief)
    r1 = RuleBasedHookJudge().judge(candidates, brief)
    r2 = RuleBasedHookJudge().judge(list(reversed(candidates)), brief)
    assert r1.winner is not None
    assert r1.winner.strategy == r2.winner.strategy


# --- generate_and_judge -------------------------------------------------------

def test_generate_and_judge_requires_min_strategy_facts():
    brief = _full_brief(anomaly_fact=None, mistaken_assumption_fact=None, cause_effect_fact=None,
                         surprising_consequence_fact=None)
    assert len(brief.available_strategies()) < MIN_STRATEGY_FACTS
    with pytest.raises(ValueError):
        generate_and_judge(brief)


def test_generate_and_judge_full_run_returns_a_winner():
    brief = _full_brief()
    result = generate_and_judge(brief)
    assert result.winner is not None
    assert len(result.survivors) >= MIN_STRATEGY_FACTS
    assert len({v.candidate.strategy for v in result.verdicts}) >= MIN_STRATEGY_FACTS


# --- AnthropicHookJudge (mirrors entertainment_qa's own test pattern) -------

def test_anthropic_hook_judge_falls_back_when_no_client(monkeypatch):
    monkeypatch.setattr(eqa, "_load_anthropic_client", lambda: None)
    brief = _full_brief()
    candidates = TemplateHookGenerator().generate(brief)
    base = RuleBasedHookJudge().judge(candidates, brief)
    result = AnthropicHookJudge().judge(candidates, brief)
    assert result.judge_name == "anthropic_unavailable_fallback_rule_based"
    assert result.winner == base.winner


def test_anthropic_hook_judge_uses_model_choice_when_available(monkeypatch):
    brief = _full_brief()
    candidates = TemplateHookGenerator().generate(brief)
    survivors = RuleBasedHookJudge().judge(candidates, brief).survivors
    assert len(survivors) >= 2
    target = survivors[-1].candidate
    monkeypatch.setattr(eqa, "_call_anthropic_messages",
                         lambda client, system, user, timeout=None: f'{{"winner_index": {len(survivors) - 1}, "reason": "x"}}')
    result = AnthropicHookJudge(client=object()).judge(candidates, brief)
    assert result.judge_name == "anthropic"
    assert result.winner.text == target.text


def test_anthropic_hook_judge_falls_back_on_malformed_response(monkeypatch):
    brief = _full_brief()
    candidates = TemplateHookGenerator().generate(brief)
    base = RuleBasedHookJudge().judge(candidates, brief)
    monkeypatch.setattr(eqa, "_call_anthropic_messages",
                         lambda client, system, user, timeout=None: "not json at all")
    result = AnthropicHookJudge(client=object()).judge(candidates, brief)
    assert result.judge_name == "anthropic_call_failed_fallback_rule_based"
    assert result.winner == base.winner


def test_anthropic_hook_judge_never_overrides_a_rejection(monkeypatch):
    brief = _full_brief()
    bad = HookCandidate(strategy="contradiction", text="안녕하세요", grounded_in=brief.contradiction_fact)
    good1 = HookCandidate(strategy="surprising_consequence", text="놀랍게도, 유리컵에 급격한 온도차를 주면 저절로 깨집니다",
                           grounded_in=brief.surprising_consequence_fact)
    good2 = HookCandidate(strategy="counterintuitive_fact", text="두꺼운 유리컵이 얇은 유리컵보다 사실은 더 쉽게 깨지기도 합니다",
                           grounded_in=brief.counterintuitive_fact)
    monkeypatch.setattr(eqa, "_call_anthropic_messages",
                         lambda client, system, user, timeout=None: '{"winner_index": 0, "reason": "x"}')
    result = AnthropicHookJudge(client=object()).judge([bad, good1, good2], brief)
    assert result.winner is not None
    assert result.winner.text != bad.text  # index 0 among survivors, never the rejected `bad`


# --- Story Prompt V2: verify_curiosity_maintained ---------------------------

def _phrase(role, text):
    return SimpleNamespace(role=role, text=text, focus=False, pace=None, hook_type=None)


def _scene(sid, plan):
    return SimpleNamespace(id=sid, narration_plan=plan)


def _project(scenes):
    return SimpleNamespace(scenes=scenes)


def test_curiosity_maintained_passes_for_good_progression():
    p = _project([
        _scene("s1", [_phrase("HOOK", "왜 이런 일이 벌어졌을까?")]),
        _scene("s2", [_phrase("INVESTIGATION", "단서를 찾아봤습니다")]),
        _scene("s3", [_phrase("EXPLANATION", "부분적인 설명이 나왔습니다")]),
        _scene("s4", [_phrase("CRISIS", "그런데 새로운 의문이 생겼습니다")]),
        _scene("s5", [_phrase("REVEAL", "진짜 이유가 밝혀졌습니다")]),
        _scene("s6", [_phrase("PAYOFF", "그렇게 모든 것이 설명됩니다")]),
    ])
    result = verify_curiosity_maintained(p)
    assert result["status"] == "PASS"


def test_curiosity_maintained_fails_when_explanation_dumped_immediately():
    p = _project([
        _scene("s1", [_phrase("HOOK", "왜 이런 일이 벌어졌을까?")]),
        _scene("s2", [_phrase("EXPLANATION", "사실 이유는 이렇습니다")]),
        _scene("s3", [_phrase("CRISIS", "또 다른 문제도 있었습니다")]),
        _scene("s4", [_phrase("PAYOFF", "결론입니다")]),
    ])
    result = verify_curiosity_maintained(p)
    assert result["status"] == "FAIL"
    assert "second role" in result["reason"]


def test_curiosity_maintained_fails_without_any_explanation():
    p = _project([
        _scene("s1", [_phrase("HOOK", "왜 이런 일이 벌어졌을까?")]),
        _scene("s2", [_phrase("INVESTIGATION", "단서를 찾아봤습니다")]),
        _scene("s3", [_phrase("CRISIS", "문제가 커졌습니다")]),
    ])
    result = verify_curiosity_maintained(p)
    assert result["status"] == "FAIL"
    assert "never actually explains" in result["reason"]


def test_curiosity_maintained_fails_on_empty_narration():
    p = _project([_scene("s1", [])])
    result = verify_curiosity_maintained(p)
    assert result["status"] == "FAIL"


def test_curiosity_maintained_fails_if_first_role_not_hook():
    p = _project([_scene("s1", [_phrase("SETUP", "배경 설명")])])
    result = verify_curiosity_maintained(p)
    assert result["status"] == "FAIL"
    assert "must be HOOK" in result["reason"]


def test_curiosity_maintained_rejects_shallow_hook_setup_payoff():
    p = _project([
        _scene("s1", [_phrase("HOOK", "놀랍게도 결과가 뒤집혔습니다")]),
        _scene("s2", [_phrase("SETUP", "먼저 상황을 보겠습니다")]),
        _scene("s3", [_phrase("PAYOFF", "정답은 이것입니다")]),
    ])
    result = verify_curiosity_maintained(p)
    assert result["status"] == "FAIL"


def test_curiosity_maintained_requires_rehook_between_answers():
    p = _project([
        _scene("s1", [_phrase("HOOK", "놀랍게도 결과가 뒤집혔습니다")]),
        _scene("s2", [_phrase("INVESTIGATION", "첫 단서를 찾았습니다")]),
        _scene("s3", [_phrase("EXPLANATION", "부분 설명입니다")]),
        _scene("s4", [_phrase("REVEAL", "더 강한 설명입니다")]),
        _scene("s5", [_phrase("PAYOFF", "최종 결론입니다")]),
    ])
    result = verify_curiosity_maintained(p)
    assert result["status"] == "FAIL"
    assert "re-hook" in result["reason"]


# --- Story Prompt V3: generation prompt -------------------------------------

def test_story_prompt_v3_encodes_retention_and_truth_contract():
    system = story_writer_system_prompt()
    required = [
        "first sentence must immediately deliver",
        "One sentence should carry one new semantic move",
        "Do not manufacture a rhetorical question after every sentence",
        "Never upgrade a possibility",
        "No generic CTA",
        "Do not repeat the same fact",
        "Between 3 and 8 seconds, start a real tension/state-change beat",
        "Start the first REVEAL or PAYOFF after 8 seconds and no later than 12 seconds",
        "first 10 seconds must contain at least three distinct narrative roles",
    ]
    for phrase in required:
        assert phrase in system


def test_story_generation_prompt_preserves_facts_uncertainty_and_selected_hook():
    brief = _full_brief()
    selected = HookCandidate(
        strategy="contradiction",
        text="생각과 달리 뜨거운 물을 부으면 멀쩡한 유리컵도 얼음물에서는 깨질 수 있습니다",
        grounded_in=brief.contradiction_fact,
    )
    prompt = build_story_generation_prompt(
        brief,
        selected,
        uncertainty_notes=["유리 파손 정도는 유리 종류와 기존 흠집에 따라 달라질 수 있음"],
    )
    assert selected.text in prompt
    assert brief.payoff_text in prompt
    assert "F1:" in prompt
    assert "U1:" in prompt
    assert "No fixed duration" in prompt
    assert "never pad or stretch" in prompt


def test_story_generation_prompt_rejects_hook_strategy_without_fact():
    brief = _full_brief(anomaly_fact=None)
    selected = HookCandidate(
        strategy="visible_anomaly",
        text="유리컵을 자세히 보면 이상하게도 균열이 보입니다",
        grounded_in="균열이 보입니다",
    )
    with pytest.raises(ValueError):
        build_story_generation_prompt(brief, selected)


def test_story_generation_prompt_supports_optional_soft_window_without_padding():
    brief = _full_brief()
    selected = HookCandidate(
        strategy="contradiction",
        text="생각과 달리 뜨거운 물을 부으면 멀쩡한 유리컵도 얼음물에서는 깨질 수 있습니다",
        grounded_in=brief.contradiction_fact,
    )
    prompt = build_story_generation_prompt(brief, selected, target_seconds=(30, 60))
    assert "30–60 seconds is a soft production window, not a quota" in prompt
    assert "Do not pad or repeat information" in prompt
