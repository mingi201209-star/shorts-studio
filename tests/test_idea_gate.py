"""Idea Gate: a topic pitch must fail closed on any single fatal defect,
never get averaged into a PASS by unrelated strengths."""
import pytest

from shorts_studio.idea_gate import IdeaPitch, evaluate_idea, required_unique_sources
from shorts_studio.final_video_qa import GLOBAL_MAX_SOURCE_FAMILY_RATIO


def _strong_pitch(**overrides) -> IdeaPitch:
    base = dict(
        topic_id="molasses-flood",
        domain="disaster",
        hook_sentence="1919년, 초당 14미터로 밀려온 당밀 파도가 보스턴 도심을 덮쳐 21명이 죽었습니다.",
        first_second_visual="무너진 거대한 당밀 저장탱크와 거리로 쏟아지는 갈색 파도의 실제 사진",
        familiar_subject="달콤한 시럽, 당밀",
        unexpected_fact="시속 56km 파도가 되어 건물을 부수고 사람을 익사시킨 산업 재해",
        conflict_or_problem="탱크는 완공 직후부터 이음새가 새고 삐걱거렸지만 회사는 계속 방치하며 가동했다",
        mid_change="1919년 1월 15일, 기온이 급등한 오후에 탱크가 폭발하듯 붕괴하며 거리 전체가 당밀에 잠겼다",
        ending_payoff="유가족의 소송 승소가 미국 최초로 기술자 도면에 전문 엔지니어의 서명 날인을 의무화하는 규정으로 이어졌다",
        visual_evidence=[
            "붕괴 직후 탱크 잔해 사진",
            "당밀에 잠긴 거리 사진",
            "구조 작업 사진",
            "무너진 고가철도 지지대 사진",
            "당시 신문 1면",
            "재판 관련 법원 문서",
            "탱크 건설 당시 사진",
            "사고 이후 청소 작업 사진",
        ],
        estimated_beats_needed=16,
    )
    base.update(overrides)
    return IdeaPitch(**base)


def test_strong_pitch_passes_with_no_critical_failures():
    result = evaluate_idea(_strong_pitch())
    assert result.status == "PASS", result.critical_failures
    assert result.critical_failures == []


def test_greeting_hook_fails_closed_even_with_everything_else_strong():
    pitch = _strong_pitch(hook_sentence="안녕하세요! 오늘은 당밀 홍수 사건에 대해 알아보겠습니다.")
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"
    assert any("hook" in f for f in result.critical_failures)


def test_bare_topic_name_hook_fails_closed():
    pitch = _strong_pitch(hook_sentence="달콤한 시럽, 당밀")  # identical to familiar_subject
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"


def test_generic_establishing_shot_first_second_fails_closed():
    pitch = _strong_pitch(first_second_visual="보스턴의 일반적인 거리 전경")
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"
    assert any("첫 1초" in f for f in result.critical_failures)


def test_no_familiar_unexpected_contrast_fails_closed():
    pitch = _strong_pitch(unexpected_fact="달콤한 시럽 당밀")  # same content as familiar_subject, just punctuation differs
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"


def test_conflict_restating_hook_fails_closed():
    pitch = _strong_pitch(conflict_or_problem="1919년, 초당 14미터로 밀려온 당밀 파도가 보스턴 도심을 덮쳐 21명이 죽었습니다.")
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"


def test_mid_change_restating_conflict_fails_closed():
    pitch = _strong_pitch(mid_change="탱크는 완공 직후부터 이음새가 새고 삐걱거렸지만 회사는 계속 방치하며 가동했다")
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"
    assert any("중간 상황 변화" in f for f in result.critical_failures)


def test_ending_payoff_that_just_restates_hook_fails_closed():
    """A brilliant hook and rich visual evidence cannot buy back a missing
    payoff -- this is the exact 'sum-scoring lets a weak topic pass' failure
    mode the brief explicitly forbids."""
    pitch = _strong_pitch(ending_payoff="1919년, 초당 14미터로 밀려온 당밀 파도가 보스턴 도심을 덮쳐 21명이 죽었습니다.")
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"
    assert any("결말 payoff" in f for f in result.critical_failures)


def test_insufficient_visual_evidence_fails_closed_even_with_perfect_story():
    """Every narrative dimension can be excellent and it must still fail if
    there isn't enough real, distinct visual material to fill the runtime
    without forced repeats."""
    pitch = _strong_pitch(visual_evidence=["탱크 잔해 사진", "거리 사진"], estimated_beats_needed=20)
    result = evaluate_idea(pitch)
    assert result.status == "FAIL"
    assert any("반복" in f or "visual evidence" in f for f in result.critical_failures)


def test_near_duplicate_visual_evidence_descriptions_are_collapsed_not_double_counted():
    pitch = _strong_pitch(visual_evidence=[
        "붕괴 직후 탱크 잔해 사진", "붕괴 직후의 탱크 잔해 사진",  # near-dup of the first
        "당밀에 잠긴 거리 사진", "구조 작업 사진", "무너진 고가철도 지지대 사진",
    ], estimated_beats_needed=16)
    result = evaluate_idea(pitch)
    assert result.evidence["unique_visual_evidence_count"] < 5
    assert result.status == "FAIL"
    assert any("반복" in f or "visual evidence" in f for f in result.critical_failures)


def test_required_unique_sources_matches_the_real_source_budget_math():
    # 1/max_family_ratio is always a floor regardless of beat count.
    assert required_unique_sources(1, GLOBAL_MAX_SOURCE_FAMILY_RATIO, 0.35) == 5
    # A large beat count raises the requirement above that floor.
    assert required_unique_sources(40, GLOBAL_MAX_SOURCE_FAMILY_RATIO, 0.35) == 14
