import json
from pathlib import Path


def test_comet_story_identifies_the_adf_cutout_as_failure_origin():
    project = json.loads(Path("examples/comet.json").read_text(encoding="utf-8"))
    scenes = {scene["id"]: scene for scene in project["scenes"]}

    assert "최초 제트 여객기 코멧" in project["title"]
    assert "안테나 개구부" in scenes["scene_05"]["narration"]
    assert "리벳 구멍" in scenes["scene_05"]["narration"]
    assert "ADF" in scenes["scene_07"]["factual_notes"][0]
    assert "안테나 개구부" in scenes["scene_05"]["visual_description"]
    assert "객실 창문" in scenes["scene_05"]["visual_description"]
    assert "네모난 객실 창문" in scenes["scene_07"]["narration"]
    graphic = Path("assets/window_compare.svg").read_text(encoding="utf-8")
    assert "ADF 안테나 개구부" in graphic
    assert "사고의 시작점이 아님" in graphic
