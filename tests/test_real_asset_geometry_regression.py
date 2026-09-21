"""Regression: the real assets/window_compare.svg, run through the ACTUAL
production pipeline (rsvg-convert rasterize -> ffmpeg push_in composite ->
mid-point frame extraction -> CornerGeometryVisionProvider), must be
correctly classified as square-left/rounded-right, and a counterexample
where both sides show the SAME shape must fail. This caught a real bug: the
raw SVG classified correctly, but the H.264-compressed, motion-filtered
video frame that production actually evaluates did not -- vertex-count
fitting (approxPolyDP) was fooled by compression noise on straight edges.
Only the full pipeline output exercises that failure mode, so this test
does not use a synthetic image; it renders the real asset for real.
"""
import shutil
from pathlib import Path
from types import SimpleNamespace
import pytest
import shorts_studio.render as R
from shorts_studio.visual_qa import CornerGeometryVisionProvider, extract_representative_frame

requires_render_toolchain = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("rsvg-convert")),
    reason="requires ffmpeg + rsvg-convert (installed in render-smoke.yml; not in the fast test.yml job)",
)

REQUIREMENTS = ["왼쪽은 네 개의 90도 모서리", "오른쪽은 크게 둥근 모서리", "두 형태가 즉시 구별되어야 함"]

def _render_and_classify(tmp_path, svg_path, scene_id="scene_x"):
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "silence.mp3"
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "6", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:06,000\ncaption\n\n", encoding="utf-8")
    scene = SimpleNamespace(id=scene_id, motion=SimpleNamespace(type="push_in"))
    asset = R._resolve_asset({"asset": str(svg_path), "asset_url": None}, build, scene_id, 0)
    clip = R._composite_scene_clip(scene, asset, audio, srt, 6.0, 30, build, 0)
    frame = build / f"{scene_id}_qa.jpg"
    extract_representative_frame(clip, frame)
    return CornerGeometryVisionProvider().evaluate(frame, REQUIREMENTS)

@requires_render_toolchain
def test_real_window_compare_svg_passes_through_full_render_pipeline():
    svg = Path(__file__).resolve().parent.parent / "assets" / "window_compare.svg"
    assert svg.exists(), "assets/window_compare.svg must exist"
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result = _render_and_classify(Path(td), svg)
    assert result["status"] == "PASS", result
    assert "square" in result["shapes"] and "rounded" in result["shapes"], result

def _make_variant_svg(path, left_rx, right_rx):
    path.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
<rect width="1080" height="1920" fill="#11151b"/>
<rect x="90" y="520" width="360" height="650" rx="{left_rx}" fill="#8ec9e8" stroke="white" stroke-width="28"/>
<rect x="630" y="520" width="360" height="650" rx="{right_rx}" fill="#8ec9e8" stroke="white" stroke-width="28"/>
</svg>""", encoding="utf-8")

@requires_render_toolchain
def test_both_sides_square_counterexample_fails_through_full_pipeline(tmp_path):
    svg = tmp_path / "both_square.svg"; _make_variant_svg(svg, 0, 0)
    result = _render_and_classify(tmp_path, svg, scene_id="both_square")
    assert result["status"] == "FAIL", result

@requires_render_toolchain
def test_both_sides_rounded_counterexample_fails_through_full_pipeline(tmp_path):
    svg = tmp_path / "both_rounded.svg"; _make_variant_svg(svg, 150, 150)
    result = _render_and_classify(tmp_path, svg, scene_id="both_rounded")
    assert result["status"] == "FAIL", result
