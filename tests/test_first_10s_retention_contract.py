"""First-10s Retention Contract -- added directly in response to real
post-publish channel data (not a QA-report number): both shipped videos
passed every existing QA gate yet showed their steepest real drop-off in
the first ~5-10 seconds. This checks the REAL structure the data implies is
missing: a claim in second 1, visual proof shortly after, a new tension by
mid-opening, and an early payoff before 12s -- using real per-role timing
recovered from actual TTS synthesis (not a character-count guess).
"""
from shorts_studio.final_video_qa import (
    compute_first_10s_narration_timeline, verify_first_10s_retention,
    verify_high_retention_profile,
)


def _unit(role, text, start, end):
    return {"role": role, "text": text, "start": start, "end": end}


def _windows(scenes):
    """scenes: list of (scene_id, cumulative_start, [units])"""
    return [{"scene": sid, "start": start, "narration_units": units} for sid, start, units in scenes]


def _strong_timeline():
    scenes = [
        ("s1", 0.0, [_unit("HOOK", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다", 0.0, 3.0)]),
        ("s2", 3.0, [
            _unit("CRISIS", "구조대는 손 쓸 새도 없이 현장을 덮친 파도를 보고만 있었습니다", 0.5, 3.0),
        ]),
        ("s3", 8.0, [
            _unit("REVEAL", "탱크는 완공 직후부터 이미 새고 있었습니다", 0.5, 3.0),
        ]),
    ]
    return compute_first_10s_narration_timeline(_windows(scenes))


def test_passes_with_hook_proof_state_change_and_early_payoff_all_on_schedule():
    timeline = _strong_timeline()
    cuts = [0.0, 1.2, 4.0, 9.0, 12.0]  # a real cut lands at 1.2s -- inside the proof window
    result = verify_first_10s_retention(timeline, cuts)
    assert result["status"] == "PASS", result["reason"] if result["status"] != "PASS" else None


def test_fails_when_no_narration_timeline_at_all():
    result = verify_first_10s_retention([], [0.0, 1.0])
    assert result["status"] == "FAIL"
    assert "no real narration timing data" in result["reason"]


def test_fails_when_first_role_is_not_hook_in_the_first_second():
    scenes = [("s1", 0.0, [_unit("SETUP", "탱크는 완공 직후부터 이미 새고 있었습니다", 0.0, 3.0)])]
    timeline = compute_first_10s_narration_timeline(_windows(scenes))
    result = verify_first_10s_retention(timeline, [0.0, 1.2])
    assert result["status"] == "FAIL"
    assert "HOOK" in result["reason"]


def test_fails_when_the_picture_holds_static_through_the_proof_window():
    """The real published-video failure mode: everything else fine, but the
    opening picture never actually changes before 3s -- no visual proof."""
    timeline = _strong_timeline()
    cuts = [0.0, 9.0, 12.0]  # no cut lands in (0.2, 3.0]
    result = verify_first_10s_retention(timeline, cuts)
    assert result["status"] == "FAIL"
    assert "visual cut" in result["reason"]


def test_fails_when_no_state_change_by_8s():
    scenes = [
        ("s1", 0.0, [_unit("HOOK", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다", 0.0, 3.0)]),
        ("s2", 3.0, [_unit("SETUP", "탱크는 1915년에 지어졌습니다", 0.5, 4.0)]),  # flat, no tension marker, wrong role
    ]
    timeline = compute_first_10s_narration_timeline(_windows(scenes))
    result = verify_first_10s_retention(timeline, [0.0, 1.2, 9.0])
    assert result["status"] == "FAIL"
    assert "state-change" in result["reason"]


def test_fails_when_no_early_payoff_by_12s():
    scenes = [
        ("s1", 0.0, [_unit("HOOK", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다", 0.0, 3.0)]),
        ("s2", 3.0, [_unit("CRISIS", "구조대는 손 쓸 새도 없이 현장을 지켜봤습니다", 0.5, 3.0)]),
        ("s3", 13.0, [_unit("REVEAL", "탱크는 이미 새고 있었습니다", 0.5, 3.0)]),  # too late
    ]
    timeline = compute_first_10s_narration_timeline(_windows(scenes))
    result = verify_first_10s_retention(timeline, [0.0, 1.2, 9.0])
    assert result["status"] == "FAIL"
    assert "early payoff" in result["reason"]


def test_fails_when_first_10s_is_dominated_by_a_single_role_with_no_variety():
    scenes = [("s1", 0.0, [
        _unit("HOOK", "거대한 탱크가 무너지며 당밀이 거리를 덮쳤습니다", 0.0, 1.0),
        _unit("HOOK", "위험한 파도가 계속 밀려왔습니다", 1.0, 9.5),
    ])]
    timeline = compute_first_10s_narration_timeline(_windows(scenes))
    result = verify_first_10s_retention(timeline, [0.0, 1.2, 4.0, 9.0])
    assert result["status"] == "FAIL"
    assert "distinct narrative role" in result["reason"]


def test_timeline_uses_real_scene_cumulative_offsets_not_scene_relative_time():
    scenes = [
        ("s1", 0.0, [_unit("HOOK", "hook text", 0.0, 2.0)]),
        ("s2", 5.0, [_unit("CRISIS", "crisis text", 1.0, 3.0)]),
    ]
    timeline = compute_first_10s_narration_timeline(_windows(scenes))
    crisis = next(e for e in timeline if e["role"] == "CRISIS")
    assert crisis["start"] == 6.0  # 5.0 (scene start) + 1.0 (unit-relative start)


def test_high_retention_profile_passes_compact_escalating_arc():
    timeline = [
        _unit("HOOK", "result", 0.0, 3.6),
        _unit("CRISIS", "expectation breaks", 4.0, 6.5),
        _unit("REVEAL", "partial answer", 8.8, 10.0),
        _unit("EXPLANATION", "mechanism", 12.0, 16.0),
        _unit("TWIST", "new consequence", 20.0, 23.0),
        _unit("PAYOFF", "close gap", 29.0, 32.0),
    ]
    activity = {"first_5s_visual_changes": 2, "max_static_visual_seconds": 3.5}
    result = verify_high_retention_profile(timeline, activity, 36.0)
    assert result["status"] == "PASS", result


def test_high_retention_profile_fails_slow_hook_and_dead_opening():
    timeline = [
        _unit("HOOK", "too long", 0.0, 5.1),
        _unit("CRISIS", "change", 5.5, 8.0),
        _unit("REVEAL", "answer", 9.0, 11.0),
        _unit("TWIST", "twist", 22.0, 24.0),
        _unit("PAYOFF", "payoff", 30.0, 33.0),
    ]
    activity = {"first_5s_visual_changes": 1, "max_static_visual_seconds": 5.0}
    result = verify_high_retention_profile(timeline, activity, 36.0)
    assert result["status"] == "FAIL"
    assert "HOOK lasts" in result["reason"]
    assert "first 5s" in result["reason"]
    assert "static" in result["reason"]


def test_high_retention_profile_fails_when_twist_or_payoff_timing_is_flat():
    timeline = [
        _unit("HOOK", "result", 0.0, 3.0),
        _unit("CRISIS", "change", 4.0, 6.0),
        _unit("REVEAL", "answer", 8.5, 10.0),
        _unit("TWIST", "too early", 11.0, 13.0),
        _unit("PAYOFF", "too early", 15.0, 17.0),
    ]
    activity = {"first_5s_visual_changes": 2, "max_static_visual_seconds": 3.0}
    result = verify_high_retention_profile(timeline, activity, 36.0)
    assert result["status"] == "FAIL"
    assert "TWIST" in result["reason"]
    assert "PAYOFF" in result["reason"]
