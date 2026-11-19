"""Regression guards for PRIVATE original-3D, first-5s-only A/B recuts."""
import importlib.util
from pathlib import Path
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "benchmarks" / "road_safety" / "episode2_first5_ab_editorial.py"


def source():
    spec = importlib.util.spec_from_file_location("real3d_first5_ab", SCRIPT)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_first_five_seconds_reuse_three_distinct_original_native_3d_beats():
    m = source()
    assert sorted(m.SHOT_PLANS) == ["A", "B"]
    for key, plan in m.SHOT_PLANS.items():
        assert len(plan) == 3
        assert sum(end-start for start,end in plan) == 150
        assert all(isinstance(n, int) and 0 <= start < end <= 900
                   for start,end in plan for n in [start,end])
        assert len({start//150 for start, end in plan}) == 3
        assert plan[-1][0] >= 300
    assert m.SHOT_PLANS["A"][0][0] == 0
    assert m.SHOT_PLANS["B"][0][0] >= 150


def test_exact_original_first5_voice_and_caption_gutter_preserved():
    m = source()
    for key in ("A", "B"):
        graph = m.build_filtergraph(m.SHOT_PLANS[key], full=True)
        assert "crop=1080:1400:0:0" in graph
        assert "crop=1080:520:0:1400" in graph
        assert "trim=start_frame=0:end_frame=150" in graph
        assert "trim=start_frame=150:end_frame=900" in graph
        assert "concat=n=2:v=1:a=0" in graph
        assert "fps=30" in graph
    assert m.RENDERER_SOURCE_SHA256 == "1ed298a8b17b6927c2aec01238ae968da7b297173aa7fbd25db21ac7e0f9d42d"


def test_visual_change_gate_unchanged_and_first5_must_change():
    m=source()
    assert m.PIXEL_DELTA_THRESHOLD == 12.
    assert m.SAMPLING_FPS == 2.
    assert m.evaluate_differences([7,7,6,7,6,7,6,7,6])["status"] == "FAIL"
    report=m.evaluate_differences([7,7,21,7,7,7,33,6,6])
    assert report["status"] == "PASS"
    assert report["first_5s_visual_changes"] == 2
    assert report["cut_timestamps_s"] == [0.,1.5,3.5]


def test_cannot_fake_cut_by_different_caption_or_break_provenance():
    m=source()
    with pytest.raises(ValueError):
        m.build_filtergraph(((0, 150),), full=True)
    with pytest.raises(ValueError):
        m.build_filtergraph(((0, 45), (60,120), (315, 360)), full=True)
    assert m.review_status == "INTERNAL_REVIEW_ONLY_EDITORIAL_HOLD"
    assert m.automatic_upload_authorized is False


def test_pure_functions_require_no_blender_ffmpeg_cv2_or_pydantic():
    m=source()
    assert m.evaluate_differences([0.] * 9)["status"] == "FAIL"
    assert m.build_filtergraph(m.SHOT_PLANS["B"],full=False)
