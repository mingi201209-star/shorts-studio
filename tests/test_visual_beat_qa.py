from types import SimpleNamespace

import pytest

import shorts_studio.render as R
from shorts_studio.models import Scene, VisualBeat


def _beat(index, status="PASS"):
    return SimpleNamespace(
        start=float(index),
        visual_qa_requirements=[f"beat {index} is visible"],
        visual_qa_labels=[f"expected subject {index}"],
        visual_qa_negative_labels=[f"wrong subject {index}"],
        visual_qa_expected_sha256=[f"sha-{index}"],
    )


def test_scene_with_required_visual_beats_requires_beat_level_qa_metadata():
    with pytest.raises(ValueError, match="beat 0 must declare visual_qa_requirements"):
        Scene(
            id="scene_01",
            narration="A story.",
            visual_description="Two sequential visuals.",
            visual_qa_requirements=["first then second"],
            visual_beats=[VisualBeat(start=0, asset="wreck.jpg")],
        )


def test_visual_beat_qa_evaluates_every_beat_with_its_own_contract(monkeypatch, tmp_path):
    scene = SimpleNamespace(
        id="scene_01",
        narration="The wreck is followed by the intact aircraft.",
        visual_qa_requirements=["wreck first, intact aircraft second"],
        visual_beats=[_beat(0), _beat(1)],
    )
    clips = [tmp_path / "beat0.mp4", tmp_path / "beat1.mp4"]
    assets = [tmp_path / "wreck.jpg", tmp_path / "intact.jpg"]
    calls = []

    def evaluate(beat_scene, clip, provider, frame_path, asset_path=None):
        calls.append((beat_scene, clip, frame_path, asset_path))
        return {
            "scene": beat_scene.id,
            "status": "PASS",
            "requirements": beat_scene.visual_qa_requirements,
        }

    monkeypatch.setattr(R, "evaluate_scene_semantics", evaluate)
    result = R._evaluate_visual_beats(scene, clips, assets, object(), tmp_path)

    assert result["status"] == "PASS"
    assert [call[0].id for call in calls] == ["scene_01_beat_00", "scene_01_beat_01"]
    assert [call[1] for call in calls] == clips
    assert [call[3] for call in calls] == assets
    assert [call[0].visual_qa_expected_sha256 for call in calls] == [["sha-0"], ["sha-1"]]
    assert [beat["status"] for beat in result["beat_results"]] == ["PASS", "PASS"]


def test_failed_first_beat_cannot_be_hidden_by_a_passing_midpoint(monkeypatch, tmp_path):
    scene = SimpleNamespace(
        id="scene_01",
        narration="The wreck is followed by the intact aircraft.",
        visual_qa_requirements=["wreck first, intact aircraft second"],
        visual_beats=[_beat(0), _beat(1)],
    )
    statuses = iter(["FAIL", "PASS"])

    def evaluate(beat_scene, clip, provider, frame_path, asset_path=None):
        return {"scene": beat_scene.id, "status": next(statuses)}

    monkeypatch.setattr(R, "evaluate_scene_semantics", evaluate)
    result = R._evaluate_visual_beats(
        scene,
        [tmp_path / "beat0.mp4", tmp_path / "beat1.mp4"],
        [tmp_path / "wreck.jpg", tmp_path / "intact.jpg"],
        object(),
        tmp_path,
    )

    assert result["status"] == "FAIL"
    assert [beat["status"] for beat in result["beat_results"]] == ["FAIL", "PASS"]


def test_visual_beat_contracts_are_populated_in_comet_example():
    from shorts_studio.project import load_project

    project = load_project("examples/comet.json")
    opening = project.scenes[0]
    assert len(opening.visual_beats) == 4
    assert all(beat.visual_qa_requirements for beat in opening.visual_beats)
    assert all(beat.visual_qa_labels or beat.visual_qa_expected_sha256 for beat in opening.visual_beats)
    # Pin each asset to its intended visual beat; a scene-level hash set lets
    # the wrong image pass merely because it belongs somewhere in the scene.
    assert opening.visual_beats[0].visual_qa_expected_sha256 == [
        "be7dfb47e75292d104b4a3e88477e4b6b1bac720fae709c52d6ff97f8c750694"
    ]
    assert opening.visual_beats[1].visual_qa_expected_sha256 == [
        "dcb7d279331d7d370d2dd36cfd287f98923b453b529f793018ed6dd95900e40e"
    ]


def test_comet_visual_beats_change_no_later_than_every_three_and_a_half_seconds():
    import json
    from pathlib import Path
    project=json.loads(Path("examples/comet.json").read_text(encoding="utf-8"))
    assert len(project["scenes"]) == 7
    for scene in project["scenes"]:
        beats=scene["visual_beats"]
        starts=[beat["start"] for beat in beats]
        assert starts[0] == 0
        assert len({(beat.get("asset"),beat.get("asset_url")) for beat in beats}) >= 2
        assert all(right-left <= 3.5 for left,right in zip(starts,starts[1:])), (scene["id"],starts)
        assert all(beat["visual_qa_requirements"] and beat["visual_qa_labels"] for beat in beats)
