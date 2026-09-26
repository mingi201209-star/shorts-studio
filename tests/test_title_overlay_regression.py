"""Real, pixel-level regression for the persistent top title. The old
implementation had drawtext code that looked correct and passed CI, but
never actually appeared in the final render: _title_filter read
getattr(scene, 'overlay_title', None), and the manifest only ever sets
overlay_title at the PROJECT level (examples/comet.json's top-level
"overlay_title" key) -- every individual Scene.overlay_title was always
None, so _title_filter(None) silently returned "" for every single scene.
No test ever exercised this path end-to-end, so the bug shipped invisibly.

These tests (a) prove render()'s data flow actually propagates
project.overlay_title down to each scene's composited clip, and (b) extract
real frames from the real rendered MP4 and verify title pixels are actually
present in the expected top region -- not just that a drawtext/subtitle
string exists somewhere in the source code.
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import cv2
import pytest

import shorts_studio.render as R

requires_ffmpeg = __import__("shutil").which("ffmpeg") is not None
pytestmark = pytest.mark.skipif(not requires_ffmpeg, reason="requires a real ffmpeg binary")


def _title_band_edge_var(frame_path: Path) -> float:
    img = cv2.imread(str(frame_path))
    # Covers the whole region above the picture's own top edge, where the
    # (now potentially 2-line, FontSize=130) title must fit entirely without
    # ever overlapping the picture box that starts at IMAGE_TOP_Y.
    band = img[10:R.IMAGE_TOP_Y - 10, :]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _render_clip(tmp_path: Path, title):
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,500 --> 00:00:02,000\n자막\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="titletest", motion=SimpleNamespace(type="push_in"))
    return R._composite_scene_clip(scene, None, audio, srt, 3.0, 30, build, 0, title=title)


def test_title_is_actually_visible_in_the_rendered_frame_top_region(tmp_path):
    clip = _render_clip(tmp_path, "비행기 창문 모서리는 왜 둥글까?")
    frame = tmp_path / "frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.1", "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
    var = _title_band_edge_var(frame)
    assert var > 50.0, f"no crisp title text detected near the top of the real rendered frame (edge_var={var:.1f})"


def test_no_title_produces_a_plain_top_region(tmp_path):
    """Control: without a title, the same top band must be plain (low edge
    energy) -- proves the previous test is actually detecting the title text
    and not some incidental artifact of the composition itself."""
    clip = _render_clip(tmp_path, None)
    frame = tmp_path / "frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.1", "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
    var = _title_band_edge_var(frame)
    assert var < 50.0, f"unexpected crisp content in the top region with no title requested (edge_var={var:.1f})"


def test_title_persists_across_the_scenes_duration(tmp_path):
    """The title must stay visible for the WHOLE scene, not just its first
    frame (a one-shot drawtext with a wrong 'enable' expression, or an SRT
    window shorter than the real audio duration, would only show it
    briefly)."""
    clip = _render_clip(tmp_path, "비행기 창문 모서리는 왜 둥글까?")
    for ts in (0.1, 1.5, 2.8):
        frame = tmp_path / f"frame_{ts}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", str(ts), "-i", str(clip), "-frames:v", "1", str(frame)], check=True, capture_output=True)
        var = _title_band_edge_var(frame)
        assert var > 50.0, f"title not visible at t={ts}s (edge_var={var:.1f})"


def test_render_propagates_project_level_overlay_title_to_every_scene(tmp_path, monkeypatch):
    """The actual bug: examples/comet.json sets overlay_title only at the
    Project level. Confirm render()'s real per-scene data flow passes that
    project-level title into _composite_scene_clip for EVERY scene, not
    relying on a per-scene field the manifest never populates."""
    captured_titles = []

    def fake_composite(scene, asset, audio, srt, duration, fps, build, index, title=None):
        captured_titles.append(title)
        clip = build / f"{scene.id}.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r={fps}:d={duration}", "-i", str(audio), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)], check=True, capture_output=True)
        return clip

    monkeypatch.setattr(R, "_composite_scene_clip", fake_composite)
    # This sandbox's ffmpeg build has no bundled ffprobe; render() gates on
    # both being present before doing any real work. ffmpeg is genuinely
    # available (checked by the module skip above), so only relax the
    # ffprobe presence check -- the per-scene loop (what this test actually
    # verifies) runs entirely before render() ever calls the real ffprobe.
    real_which = R.shutil.which
    monkeypatch.setattr(R.shutil, "which", lambda name: real_which(name) or (name == "ffprobe" and real_which("ffmpeg")))

    async def fake_synthesize_plan(plan, audio_path, timing_path, **kw):
        from shorts_studio.timing import WordTiming
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "1", "-q:a", "9", str(audio_path)], check=True, capture_output=True)
        timing_path.write_text("{}", encoding="utf-8")
        text = " ".join(p.text for p in plan)
        return [WordTiming(text, 0.0, 0.8)]

    monkeypatch.setattr(R, "synthesize_plan", fake_synthesize_plan)

    manifest = tmp_path / "m.json"
    manifest.write_text(
        """{"title":"t","width":1080,"height":1920,"fps":30,"overlay_title":"프로젝트 제목",
        "scenes":[{"id":"s1","narration":"하나","visual_description":"d"},
                   {"id":"s2","narration":"둘","visual_description":"d"}]}""",
        encoding="utf-8",
    )
    prev = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        try:
            R.render(str(manifest))
        except Exception:
            # This test only cares whether render()'s data flow propagates
            # the project-level title into every scene's composite call --
            # the fake compositor below doesn't burn in a real title, so the
            # separate final-video-QA gates (which DO check for one) are
            # expected to fail closed here; that's not what this test proves.
            pass
    finally:
        os.chdir(prev)

    assert captured_titles == ["프로젝트 제목", "프로젝트 제목"], captured_titles
