"""Retention-engine contract: First-Second Hook, Information Change, Story
Progression, Ending Payoff, and Runtime Discipline. All script-level (no
rendered video needed), all opt-in via Project.strict_retention_contract so
manifests that predate this contract are never retroactively affected.
"""
from types import SimpleNamespace

import pytest

from shorts_studio.final_video_qa import (
    verify_hook_opener, verify_first_beat_visual_grounding,
    verify_first_beat_narration_visual_sync,
    compute_information_progression, verify_information_progression,
    verify_story_progression, verify_ending_payoff_role,
    verify_no_redundant_narration, verify_retention_contract,
)


def _phrase(role, text, hook_type=None):
    return SimpleNamespace(role=role, text=text, focus=False, pace=None, hook_type=hook_type)


def _beat(start, req=None, info_role=None, url="https://x/a.jpg"):
    return SimpleNamespace(start=start, asset=None, asset_url=url, attribution=None,
                            visual_qa_requirements=req or [], visual_qa_labels=[], info_role=info_role)


def _scene(sid, narration, narration_plan=None, visual_beats=None, visual_description="d", visual_qa_requirements=None):
    return SimpleNamespace(id=sid, narration=narration, visual_description=visual_description,
                            narration_plan=narration_plan or [], visual_beats=visual_beats or [],
                            visual_qa_requirements=visual_qa_requirements or [])


def _project(scenes):
    return SimpleNamespace(scenes=scenes)


def _strong_project():
    s1 = _scene("s1", "hook", narration_plan=[_phrase("HOOK", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다", hook_type="danger")],
                visual_beats=[_beat(0.0, req=["무너진 거대한 당밀 탱크와 거리로 쏟아지는 당밀 파도 사진"], info_role="tank_scale")])
    s2 = _scene("s2", "setup", narration_plan=[_phrase("SETUP", "탱크는 완공 직후부터 새고 있었습니다")],
                visual_beats=[_beat(0.0, req=["초기 누수 흔적 사진"], info_role="leak_evidence")])
    s3 = _scene("s3", "crisis", narration_plan=[_phrase("CRISIS", "결국 탱크가 붕괴하며 연쇄적으로 무너졌습니다")],
                visual_beats=[_beat(0.0, req=["연쇄 붕괴 사진"], info_role="chain_collapse")])
    s4 = _scene("s4", "reveal", narration_plan=[_phrase("REVEAL", "소송 결과 안전 규정이 바뀌었습니다")],
                visual_beats=[_beat(0.0, req=["재판 관련 문서 사진"], info_role="trial_outcome")])
    s5 = _scene("s5", "payoff", narration_plan=[_phrase("PAYOFF", "그 규정은 지금도 쓰이고 있습니다")],
                visual_beats=[_beat(0.0, req=["현재 기준 도면 사진"], info_role="modern_legacy")])
    return _project([s1, s2, s3, s4, s5])


# --- hook opener -----------------------------------------------------------

def test_hook_opener_passes_for_a_real_result_sentence():
    result = verify_hook_opener(_strong_project())
    assert result["status"] == "PASS"


def test_hook_opener_fails_on_greeting():
    p = _strong_project()
    p.scenes[0].narration_plan = [_phrase("HOOK", "안녕하세요! 오늘은 당밀 홍수에 대해 알아보겠습니다.")]
    result = verify_hook_opener(p)
    assert result["status"] == "FAIL"


def test_hook_opener_fails_on_flat_background_description_even_without_a_banned_pattern():
    """The real published-video bug: not a greeting or topic announcement,
    just pure background exposition with no result/danger/question/anomaly
    for the viewer to react to in the first second."""
    p = _strong_project()
    p.scenes[0].narration_plan = [_phrase("HOOK", "타이타닉에는 거대한 굴뚝이 네 개 있었습니다", hook_type="visible_anomaly")]
    result = verify_hook_opener(p)
    assert result["status"] == "FAIL"
    assert "tension" in result["reason"] or "signal" in result["reason"] or "flat" in result["reason"]


def test_hook_opener_fails_when_hook_type_is_not_declared():
    p = _strong_project()
    p.scenes[0].narration_plan = [_phrase("HOOK", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다", hook_type=None)]
    result = verify_hook_opener(p)
    assert result["status"] == "FAIL"
    assert "hook_type" in result["reason"]


def test_hook_opener_fails_when_first_role_is_not_hook():
    p = _strong_project()
    p.scenes[0].narration_plan = [_phrase("SETUP", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다")]
    result = verify_hook_opener(p)
    assert result["status"] == "FAIL"
    assert "HOOK" in result["reason"]


# --- first beat visual grounding -------------------------------------------

def test_first_beat_visual_grounding_passes_with_concrete_requirement():
    result = verify_first_beat_visual_grounding(_strong_project())
    assert result["status"] == "PASS"


def test_first_beat_visual_grounding_fails_on_generic_establishing_text():
    p = _strong_project()
    p.scenes[0].visual_beats = [_beat(0.0, req=["보스턴의 일반적인 거리 전경"])]
    result = verify_first_beat_visual_grounding(p)
    assert result["status"] == "FAIL"


def test_first_beat_visual_grounding_fails_when_empty():
    p = _strong_project()
    p.scenes[0].visual_beats = [_beat(0.0, req=[])]
    p.scenes[0].visual_description = ""
    result = verify_first_beat_visual_grounding(p)
    assert result["status"] == "FAIL"


# --- narration/visual sync ---------------------------------------------------

def test_narration_visual_sync_passes_when_words_overlap():
    result = verify_first_beat_narration_visual_sync(_strong_project())
    assert result["status"] == "PASS"


def test_narration_visual_sync_fails_when_unrelated():
    p = _strong_project()
    p.scenes[0].visual_beats = [_beat(0.0, req=["전혀 다른 주제의 고양이 사진입니다"])]
    result = verify_first_beat_narration_visual_sync(p)
    assert result["status"] == "FAIL"


def test_narration_visual_sync_not_evaluated_when_no_requirement_declared():
    p = _strong_project()
    p.scenes[0].visual_beats = [_beat(0.0, req=[])]
    result = verify_first_beat_narration_visual_sync(p)
    assert result["status"] == "NOT_EVALUATED"


# --- information progression -------------------------------------------------

def test_information_progression_passes_with_all_distinct_roles():
    metrics = compute_information_progression(_strong_project())
    result = verify_information_progression(metrics)
    assert result["status"] == "PASS"
    assert metrics["duplicate_info_roles"] == []


def test_information_progression_fails_on_duplicate_info_role():
    p = _strong_project()
    p.scenes[4].visual_beats[0].info_role = "tank_scale"  # duplicates scene s1's info_role
    metrics = compute_information_progression(p)
    result = verify_information_progression(metrics)
    assert result["status"] == "FAIL"
    assert len(metrics["duplicate_info_roles"]) == 1


def test_information_progression_fails_when_too_few_beats_declare_a_role():
    p = _strong_project()
    for scene in p.scenes[1:]:
        scene.visual_beats[0].info_role = None
    metrics = compute_information_progression(p)
    result = verify_information_progression(metrics)
    assert result["status"] == "FAIL"
    assert "declare an info_role" in result["reason"]


# --- story progression --------------------------------------------------------

def test_story_progression_passes_for_a_real_hook_to_payoff_arc():
    result = verify_story_progression(_strong_project())
    assert result["status"] == "PASS"


def test_story_progression_fails_with_no_narration_plan_at_all():
    p = _project([_scene("s1", "그냥 평문 나레이션")])
    result = verify_story_progression(p)
    assert result["status"] == "FAIL"


def test_story_progression_fails_when_first_role_is_not_hook():
    p = _strong_project()
    p.scenes[0].narration_plan = [_phrase("SETUP", "탱크는 완공 직후부터 새고 있었습니다")]
    result = verify_story_progression(p)
    assert result["status"] == "FAIL"


def test_story_progression_fails_on_flat_script_with_too_few_distinct_roles():
    """The literal 'A and B and C' failure mode: every scene uses the same
    two roles, never really moving the story forward."""
    scenes = [
        _scene("s1", "a", narration_plan=[_phrase("HOOK", "탱크가 무너졌습니다")]),
        _scene("s2", "b", narration_plan=[_phrase("SETUP", "탱크는 크고 오래되었습니다")]),
        _scene("s3", "c", narration_plan=[_phrase("SETUP", "탱크는 보스턴에 있었습니다")]),
    ]
    result = verify_story_progression(_project(scenes))
    assert result["status"] == "FAIL"
    assert "distinct narrative role" in result["reason"]


def test_story_progression_fails_when_a_scene_introduces_no_new_role():
    p = _strong_project()
    # Insert a scene between s2 and s3 that only repeats SETUP, already covered.
    extra = _scene("s2b", "filler", narration_plan=[_phrase("SETUP", "탱크는 여전히 새고 있었습니다")])
    p.scenes.insert(2, extra)
    result = verify_story_progression(p)
    assert result["status"] == "FAIL"
    assert "s2b" in result["reason"]


# --- ending payoff role --------------------------------------------------------

def test_ending_payoff_role_passes_when_last_phrase_is_payoff():
    result = verify_ending_payoff_role(_strong_project())
    assert result["status"] == "PASS"


def test_ending_payoff_role_fails_when_last_phrase_is_explanation():
    p = _strong_project()
    p.scenes[-1].narration_plan = [_phrase("EXPLANATION", "정리하자면 이런 사건이었습니다")]
    result = verify_ending_payoff_role(p)
    assert result["status"] == "FAIL"


def test_ending_payoff_role_fails_with_no_narration_plan():
    p = _strong_project()
    p.scenes[-1].narration_plan = []
    result = verify_ending_payoff_role(p)
    assert result["status"] == "FAIL"


# --- runtime discipline: redundant narration -----------------------------------

def test_no_redundant_narration_passes_for_distinct_sentences():
    result = verify_no_redundant_narration(_strong_project())
    assert result["status"] == "PASS"


def test_no_redundant_narration_fails_on_near_duplicate_sentences():
    p = _strong_project()
    p.scenes[-1].narration_plan = [_phrase("PAYOFF", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다")]  # near-dup of s1's HOOK line
    result = verify_no_redundant_narration(p)
    assert result["status"] == "FAIL"


# --- aggregate ------------------------------------------------------------------

def test_verify_retention_contract_passes_for_a_fully_authored_strong_project():
    result = verify_retention_contract(_strong_project())
    assert result["status"] == "PASS", result["checks"]


def test_verify_retention_contract_fails_closed_if_any_single_sub_check_fails():
    p = _strong_project()
    p.scenes[0].narration_plan = [_phrase("HOOK", "안녕하세요! 오늘은 당밀 홍수에 대해 알아보겠습니다.")]
    result = verify_retention_contract(p)
    assert result["status"] == "FAIL"
    assert result["checks"]["hook_opener"]["status"] == "FAIL"
