"""The production runner's own checks: source-internal cuts and gate failure naming."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")

_SPEC = importlib.util.spec_from_file_location(
    "produce_topic", Path(__file__).resolve().parents[1] / "scripts" / "produce_topic.py")
produce_topic = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(produce_topic)


def _clip(path, graph):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", graph, "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_a_hard_cut_inside_the_beat_is_found_and_one_after_it_is_not(tmp_path):
    cut = _clip(tmp_path / "cut.mp4",
                "testsrc2=size=320x240:rate=30:duration=2[a];smptebars=size=320x240:rate=30:duration=2[b];[a][b]concat=n=2")
    found = produce_topic.source_cuts(cut, 4.0)
    assert len(found) == 1 and abs(found[0] - 2.0) < 0.1
    assert produce_topic.source_cuts(cut, 1.5) == [], "a cut after the beat has left the screen does not matter"


def test_continuous_motion_is_not_reported_as_a_cut(tmp_path):
    moving = _clip(tmp_path / "moving.mp4", "testsrc2=size=320x240:rate=30:duration=4")
    assert produce_topic.source_cuts(moving, 4.0) == []


def test_gate_failures_name_each_failed_gate_with_its_reason(tmp_path):
    qa = {
        "final_video_qa": {"checks": {
            "visual_cut_cadence": {"status": "FAIL", "reason": "picture hold exceeds the visual cut limit",
                                   "failures": [{"scene": "s_reveal", "longest_hold": 4.25}]},
            "captions_visible": {"status": "PASS"}}},
        "semantic_visual_qa": {"results": [{"scene": "s_twist", "status": "FAIL", "beat_results": [
            {"scene": "s_twist_beat_02", "status": "FAIL", "reason": "frame is too blurry for mobile viewing"},
            {"scene": "s_twist_beat_03", "status": "PASS"}]}]},
        "subtitle_reports": [{"scene": "s_hook", "status": "PASS"}],
    }
    found = produce_topic.gate_failures(qa, tmp_path / "missing.log")
    assert len(found) == 2
    assert "visual_cut_cadence" in found[0] and "4.25" in found[0]
    assert "s_twist_beat_02" in found[1] and "blurry" in found[1]


def test_a_crash_before_any_gate_reports_the_last_log_line(tmp_path):
    log = tmp_path / "render.log"
    log.write_text("first\nRuntimeError: scene s_hook: no asset candidate could be rendered\n", encoding="utf-8")
    found = produce_topic.gate_failures({}, log)
    assert len(found) == 1 and "no asset candidate" in found[0]


def test_opening_motion_flags_footage_the_render_integrity_gate_would_fail(tmp_path):
    steady = _clip(tmp_path / "steady.mp4", "testsrc2=size=980x926:rate=30:duration=1.5")
    grain = _clip(tmp_path / "grain.mp4", "nullsrc=size=980x926:rate=30:duration=1.5,geq=lum='random(1)*255':cb=128:cr=128")
    calm = produce_topic.opening_motion(steady, 2.0)
    assert len(calm["errors"]) == 2 and not calm["risky"]
    rough = produce_topic.opening_motion(grain, 2.0)
    assert rough["risky"] and rough["worst_error"] > produce_topic.RENDERED_STATE_MAX_ERROR


def test_prescreen_stops_on_unsteady_opening_frames_before_loading_the_vision_model(tmp_path, monkeypatch):
    grain = _clip(tmp_path / "grain.mp4", "nullsrc=size=980x926:rate=30:duration=1.5,geq=lum='random(1)*255':cb=128:cr=128")
    import shorts_studio.visual_qa as visual_qa
    monkeypatch.setattr(visual_qa, "default_vision_provider", lambda: pytest.fail("the vision model must not load"))
    manifest = {"scenes": [{"id": "s_hook", "visual_beats": [{"asset": str(grain)}]}]}
    result = produce_topic.prescreen(manifest, tmp_path / "work", [1.4])
    assert result["status"] == "FAIL" and "s_hook[0] grain.mp4" in result["reason"]


def test_a_zoom_of_an_earlier_picture_is_reported_as_a_replay_and_a_new_picture_is_not(tmp_path):
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(7)
    texture = (rng.random((926, 980, 3)) * 255).astype(np.uint8)
    texture = np.asarray(Image.fromarray(texture).resize((245, 232)).resize((980, 926), Image.BICUBIC))
    paths = {}
    for name, picture in {"wide": texture,
                          "zoom": np.asarray(Image.fromarray(texture[150:750, 200:835]).resize((980, 926))),
                          "other": np.asarray(Image.fromarray(255 - texture[::-1]))}.items():
        paths[name] = tmp_path / f"{name}.png"
        Image.fromarray(picture).save(paths[name])
    frames = [(name, "same source", produce_topic.gate_frame(paths[name], 2.0)) for name in ("wide", "other", "zoom")]
    found = produce_topic.replayed_pictures(frames)
    assert found == ["zoom repeats the picture of wide"]


def test_back_to_back_lookalike_beats_are_reported_as_one_static_picture(tmp_path):
    calm_a = _clip(tmp_path / "a.mp4", "color=c=0x406080:size=980x926:rate=30:duration=3")
    calm_b = _clip(tmp_path / "b.mp4", "color=c=0x426282:size=980x926:rate=30:duration=3")
    other = _clip(tmp_path / "c.mp4", "color=c=0xE0A020:size=980x926:rate=30:duration=3")
    merged = produce_topic.static_runs([("a", calm_a, 2.8), ("b", calm_b, 2.6), ("c", other, 2.0)])
    assert merged == ["a + b read as one 5.4s picture"]
    assert produce_topic.static_runs([("a", calm_a, 2.8), ("c", other, 2.6), ("b", calm_b, 2.0)]) == []
