from pathlib import Path

import pytest

from shorts_studio.captions import merge_scene_srt_files


def test_merge_scene_srt_files_offsets_cues_and_scales_to_final_duration(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    (build / "scene_01.srt").write_text(
        "1\n00:00:00,200 --> 00:00:01,000\n첫 장면 자막\n\n",
        encoding="utf-8",
    )
    (build / "scene_02.srt").write_text(
        "1\n00:00:00,000 --> 00:00:00,500\n두 번째 장면\n\n",
        encoding="utf-8",
    )
    windows = [
        {"scene": "scene_01", "start": 0.0, "duration": 2.0},
        {"scene": "scene_02", "start": 2.0, "duration": 2.0},
    ]

    result = merge_scene_srt_files(windows, build, 3.8, tmp_path / "dist" / "captions.srt")

    assert result["status"] == "PASS"
    assert result["cues"] == 2
    assert result["time_scale"] == pytest.approx(0.95)
    assert (tmp_path / "dist" / "captions.srt").read_text(encoding="utf-8") == (
        "1\n00:00:00,190 --> 00:00:00,950\n첫 장면 자막\n\n"
        "2\n00:00:01,900 --> 00:00:02,375\n두 번째 장면\n"
    )


def test_merge_scene_srt_files_fails_on_overlapping_windows(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    windows = [
        {"scene": "one", "start": 0.0, "duration": 2.0},
        {"scene": "two", "start": 1.5, "duration": 2.0},
    ]
    with pytest.raises(ValueError, match="overlapping scene window"):
        merge_scene_srt_files(windows, build, 4.0, tmp_path / "captions.srt")


def test_merge_scene_srt_files_fails_on_a_caption_past_scene_duration(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    (build / "scene.srt").write_text(
        "1\n00:00:00,000 --> 00:00:03,000\ntoo long\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="outside scene duration"):
        merge_scene_srt_files(
            [{"scene": "scene", "start": 0.0, "duration": 2.0}],
            build,
            2.0,
            tmp_path / "captions.srt",
        )
