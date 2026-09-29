from types import SimpleNamespace

from shorts_studio.production_quality import verify_production_quality_v2


def beat(start, kind, *, hero=False, internal="none", moving=True):
    return SimpleNamespace(
        start=float(start),
        presentation_kind=kind,
        hero_visual=hero,
        internal_text=internal,
        asset=f"asset_{start}.mp4" if moving else f"asset_{start}.png",
        asset_url=None,
    )


def project_with(beats):
    scene = SimpleNamespace(id="s1", visual_beats=beats, asset=None, asset_url=None)
    return SimpleNamespace(scenes=[scene])


def test_production_quality_v2_passes_evidence_led_motion_rich_timeline():
    beats = [
        beat(0, "real_motion", hero=True),
        beat(2, "physical_animation"),
        beat(5, "explanatory_diagram", moving=False),
        beat(7, "physical_animation"),
        beat(10, "real_motion", hero=True),
        beat(13, "physical_animation"),
        beat(16, "explanatory_diagram", moving=False),
        beat(18, "physical_animation"),
        beat(21, "real_still", moving=False),
        beat(24, "physical_animation"),
        beat(27, "real_motion", hero=True),
    ]
    result = verify_production_quality_v2(
        project_with(beats),
        [{"scene": "s1", "start": 0.0, "duration": 30.0}],
        30.0,
    )
    assert result["status"] == "PASS", result
    assert result["metrics"]["silent_watch_proxy"] == "PASS"
    assert result["human_silent_review"]["status"] == "REQUIRED"


def test_production_quality_v2_rejects_explanation_cards_in_first_five_seconds():
    beats = [
        beat(0, "real_motion", hero=True),
        beat(2, "explanatory_diagram", moving=False),
        beat(5, "physical_animation"),
        beat(10, "real_motion", hero=True),
        beat(15, "physical_animation"),
        beat(20, "real_still", moving=False),
        beat(24, "physical_animation"),
        beat(27, "real_motion"),
    ]
    result = verify_production_quality_v2(project_with(beats), [{"scene": "s1", "start": 0.0, "duration": 30.0}], 30.0)
    assert result["status"] == "FAIL"
    assert any("first 5 seconds" in x for x in result["failures"])


def test_production_quality_v2_rejects_two_explanation_cards_in_a_row():
    beats = [
        beat(0, "real_motion", hero=True),
        beat(3, "physical_animation"),
        beat(6, "explanatory_diagram", moving=False),
        beat(9, "text_card", moving=False),
        beat(12, "real_motion", hero=True),
        beat(16, "physical_animation"),
        beat(20, "real_still", moving=False),
        beat(24, "physical_animation"),
        beat(27, "real_motion"),
    ]
    result = verify_production_quality_v2(project_with(beats), [{"scene": "s1", "start": 0.0, "duration": 30.0}], 30.0)
    assert result["status"] == "FAIL"
    assert any("consecutively" in x for x in result["failures"])


def test_production_quality_v2_rejects_sentence_level_internal_text():
    beats = [
        beat(0, "real_motion", hero=True),
        beat(3, "physical_animation"),
        beat(6, "explanatory_diagram", moving=False, internal="sentence"),
        beat(9, "physical_animation"),
        beat(12, "real_motion", hero=True),
        beat(16, "physical_animation"),
        beat(20, "real_still", moving=False),
        beat(24, "physical_animation"),
        beat(27, "real_motion"),
    ]
    result = verify_production_quality_v2(project_with(beats), [{"scene": "s1", "start": 0.0, "duration": 30.0}], 30.0)
    assert result["status"] == "FAIL"
    assert any("internal prose" in x for x in result["failures"])


def test_production_quality_v2_requires_second_moving_hero_between_10_and_25_seconds():
    beats = [
        beat(0, "real_motion", hero=True),
        beat(3, "physical_animation"),
        beat(6, "explanatory_diagram", moving=False),
        beat(8, "physical_animation"),
        beat(12, "real_motion", hero=False),
        beat(16, "physical_animation"),
        beat(20, "real_still", moving=False),
        beat(24, "physical_animation"),
        beat(27, "real_motion"),
    ]
    result = verify_production_quality_v2(project_with(beats), [{"scene": "s1", "start": 0.0, "duration": 30.0}], 30.0)
    assert result["status"] == "FAIL"
    assert any("second moving hero visual" in x for x in result["failures"])


def test_production_quality_v2_rejects_static_explanatory_ending():
    beats = [
        beat(0, "real_motion", hero=True),
        beat(3, "physical_animation"),
        beat(6, "explanatory_diagram", moving=False),
        beat(8, "physical_animation"),
        beat(12, "real_motion", hero=True),
        beat(16, "physical_animation"),
        beat(20, "real_still", moving=False),
        beat(24, "physical_animation"),
        beat(27, "explanatory_diagram", moving=False),
    ]
    result = verify_production_quality_v2(project_with(beats), [{"scene": "s1", "start": 0.0, "duration": 30.0}], 30.0)
    assert result["status"] == "FAIL"
    assert any("final visual" in x for x in result["failures"])
