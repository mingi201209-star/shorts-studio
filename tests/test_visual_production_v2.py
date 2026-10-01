from shorts_studio.models import Project
from shorts_studio.production_v2 import (
    verify_visual_production_structure,
    verify_visual_production_timeline,
)


def _tag(role, mode, info):
    return {"role": role, "visual_mode": mode, "added_information": info}


def _project(*, second_start=12.0, abstract_run=False, strict=True):
    beats = [
        {"start": 0.0, "asset": "hero.mp4", "production": _tag("hero", "real_footage", "hero_result")},
        {"start": 3.0, "asset": "evidence.png", "production": _tag("evidence", "evidence_graphic", "evidence")},
        {"start": 6.0, "asset": "mechanism.mp4", "production": _tag("mechanism", "physical_animation", "mechanism")},
        {"start": second_start, "asset": "peak.mp4", "production": _tag("second_peak", "physical_animation", "second_peak")},
        {"start": 32.0, "asset": "payoff.mp4", "production": _tag("payoff", "physical_animation", "payoff")},
    ]
    if abstract_run:
        beats[2]["production"] = _tag("support", "evidence_graphic", "abstract_three")
        beats.insert(2, {"start": 5.0, "asset": "abstract.png",
                         "production": _tag("support", "evidence_graphic", "abstract_two")})
        beats[1]["production"] = _tag("evidence", "evidence_graphic", "abstract_one")
        beats[3]["production"] = _tag("mechanism", "evidence_graphic", "mechanism")
    return Project.model_validate({
        "title": "v2",
        "strict_visual_production_v2": strict,
        "observable_phenomenon": "a visible physical event",
        "silent_story": "result -> evidence -> mechanism -> second peak -> payoff",
        "scenes": [{
            "id": "s1",
            "narration": "test",
            "visual_description": "test",
            "visual_beats": beats,
        }],
    })


def test_non_opt_in_is_untouched():
    p = _project(strict=False)
    assert verify_visual_production_structure(p)["status"] == "NOT_EVALUATED"


def test_structure_requires_complete_classification():
    p = _project()
    p.scenes[0].visual_beats[1].production = None
    result = verify_visual_production_structure(p)
    assert result["status"] == "FAIL"
    assert "missing production classification" in result["reason"]


def test_structure_rejects_three_abstract_states_in_a_row():
    p = _project(abstract_run=True)
    result = verify_visual_production_structure(p)
    assert result["status"] == "FAIL"
    assert "consecutive non-physical" in result["reason"]


def test_timeline_enforces_second_peak_window_and_payoff():
    p = _project(second_start=12.0)
    ok = verify_visual_production_timeline(
        p, [{"scene": "s1", "start": 0.0, "duration": 40.0}], 40.0
    )
    assert ok["status"] == "PASS"
    assert ok["evidence"]["second_peak_start"] == 12.0

    bad = _project(second_start=8.0)
    result = verify_visual_production_timeline(
        bad, [{"scene": "s1", "start": 0.0, "duration": 40.0}], 40.0
    )
    assert result["status"] == "FAIL"
    assert "outside 10-25s" in result["reason"]


def test_human_silent_fail_blocks_candidate():
    p = _project()
    p.silent_interest_review = "fail"
    result = verify_visual_production_structure(p)
    assert result["status"] == "FAIL"
    assert "silent-interest review is FAIL" in result["reason"]
