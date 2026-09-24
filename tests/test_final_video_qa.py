"""Unit tests for the viewer-facing final-video QA module: each check must
actually look at real rendered frames (or real structural data) and fail
closed on a real defect, not just succeed by construction.
"""
import subprocess
from types import SimpleNamespace

import pytest

import shorts_studio.render as R
from shorts_studio.final_video_qa import (
    verify_bottom_safe_area_clean, verify_captions_visible,
    verify_composition_9x16, verify_no_semantic_skip, verify_scenes_present,
    verify_title_visible, verify_picture_caption_gutter, verify_visual_cut_cadence,
)

requires_ffmpeg = pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="requires a real ffmpeg binary")


def _clip_with_title(tmp_path, title):
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,500 --> 00:00:02,000\n자막입니다\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="x", motion=SimpleNamespace(type="push_in"))
    return R._composite_scene_clip(scene, None, audio, srt, 3.0, 30, build, 0, title=title), build


@requires_ffmpeg
def test_verify_title_visible_passes_with_real_title(tmp_path):
    clip, build = _clip_with_title(tmp_path, "비행기 창문 모서리는 왜 둥글까?")
    result = verify_title_visible(clip, [0.2, 1.5, 2.8], build)
    assert result["status"] == "PASS", result


@requires_ffmpeg
def test_verify_title_visible_fails_without_a_title(tmp_path):
    clip, build = _clip_with_title(tmp_path, None)
    result = verify_title_visible(clip, [0.2, 1.5], build)
    assert result["status"] == "FAIL", result


@requires_ffmpeg
def test_verify_captions_visible_detects_real_caption(tmp_path):
    clip, build = _clip_with_title(tmp_path, None)
    result = verify_captions_visible(clip, [(1.2, (1300, 1900))], build)
    assert result["status"] == "PASS", result


@requires_ffmpeg
def test_verify_captions_visible_fails_when_no_caption_in_expected_band(tmp_path):
    clip, build = _clip_with_title(tmp_path, None)
    # Sample during silence (before the caption's own window starts).
    result = verify_captions_visible(clip, [(0.05, (1300, 1900))], build)
    assert result["status"] == "FAIL", result


def _noisy_bottom_asset(path):
    import numpy as np
    from PIL import Image
    w, h = 1200, 2000
    rng = np.random.default_rng(42)
    img = np.full((h, w, 3), 255, dtype=np.uint8)
    img[int(h * 0.88):, :] = rng.integers(0, 255, size=(h - int(h * 0.88), w, 3), dtype=np.uint8)
    Image.fromarray(img).save(path)
    return path


@requires_ffmpeg
def test_verify_bottom_safe_area_clean_passes_on_the_fixed_composition(tmp_path):
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "2", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,500\n자막\n\n", encoding="utf-8")
    asset = _noisy_bottom_asset(build / "asset.png")
    scene = SimpleNamespace(id="x", motion=SimpleNamespace(type="push_in"))
    clip = R._composite_scene_clip(scene, asset, audio, srt, 2.0, 30, build, 0)
    result = verify_bottom_safe_area_clean(clip, [0.2, 1.8], build, (R.SAFE_BOTTOM_Y, 1920))
    assert result["status"] == "PASS", result


@requires_ffmpeg
def test_verify_bottom_safe_area_clean_fails_on_the_pre_fix_unbounded_composition(tmp_path):
    """Proves this check isn't vacuous: reproducing the OLD (unbounded fg)
    composition with a realistic textured marker must fail it."""
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "2", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:01,500\n자막\n\n", encoding="utf-8")
    asset = _noisy_bottom_asset(build / "asset.png")
    old_vf = (
        "split=2[bgsrc][fgsrc];[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:8[bg];"
        "[fgsrc]scale=1000:1720:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,"
        "zoompan=z='min(zoom+0.0007,1.12)':d=1:s=1080x1920:fps=30,"
        f"subtitles={srt.as_posix()}:force_style='Alignment=2,MarginV=48,FontSize=18,Outline=2,Shadow=0,Bold=1'"
    )
    old_clip = build / "old.mp4"
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(asset), "-i", str(audio), "-t", "2",
                     "-vf", old_vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(old_clip)],
                    check=True, capture_output=True)
    result = verify_bottom_safe_area_clean(old_clip, [0.2], build, (R.SAFE_BOTTOM_Y, 1920))
    assert result["status"] == "FAIL", result


def test_verify_composition_9x16_passes_and_fails_correctly():
    good = {"streams": [{"codec_type": "video", "width": 1080, "height": 1920}]}
    bad = {"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}
    assert verify_composition_9x16(good)["status"] == "PASS"
    assert verify_composition_9x16(bad)["status"] == "FAIL"


def test_verify_scenes_present_detects_missing_and_reordered_scenes():
    expected = ["s1", "s2", "s3"]
    assert verify_scenes_present(expected, [{"scene": "s1"}, {"scene": "s2"}, {"scene": "s3"}])["status"] == "PASS"
    assert verify_scenes_present(expected, [{"scene": "s1"}, {"scene": "s3"}])["status"] == "FAIL"
    assert verify_scenes_present(expected, [{"scene": "s2"}, {"scene": "s1"}, {"scene": "s3"}])["status"] == "FAIL"


def test_verify_no_semantic_skip_is_always_strict_regardless_of_env_flag():
    # Deliberately does not read SHORTS_REQUIRE_SEMANTIC_QA -- this check must
    # never be silently disabled by an environment change.
    results = [{"scene": "s1", "status": "PASS"}, {"scene": "s2", "status": "NOT_EVALUATED"}]
    assert verify_no_semantic_skip(results)["status"] == "FAIL"
    assert verify_no_semantic_skip([{"scene": "s1", "status": "PASS"}])["status"] == "PASS"


@requires_ffmpeg
def test_picture_caption_gutter_is_black_on_real_render(tmp_path):
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "2", "-q:a", "9", str(audio)], check=True, capture_output=True)
    clip, build = _clip_with_title(tmp_path, None)
    result = verify_picture_caption_gutter(clip, [1.2], build)
    assert result["status"] == "PASS", result


def test_visual_cut_cadence_rejects_long_static_holds():
    scenes = [SimpleNamespace(id="s1", visual_beats=[SimpleNamespace(start=0), SimpleNamespace(start=3)])]
    assert verify_visual_cut_cadence([{"scene":"s1","duration":6.2}], scenes)["status"] == "PASS"
    assert verify_visual_cut_cadence([{"scene":"s1","duration":7.0}], scenes)["status"] == "FAIL"


@requires_ffmpeg
def test_narration_continuity_rejects_dropped_speech_gap(tmp_path):
    import math
    import struct
    import wave
    from shorts_studio.final_video_qa import verify_narration_continuity

    def wave_with_pause(path, pause):
        rate = 24000
        duration = 0.3 + pause + 0.3
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(b"".join(
                struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * n / rate))
                            if n / rate < 0.3 or n / rate > 0.3 + pause else 0)
                for n in range(int(duration * rate))
            ))

    broken = tmp_path / "broken.wav"
    good = tmp_path / "good.wav"
    wave_with_pause(broken, 1.8)
    wave_with_pause(good, 0.4)
    assert verify_narration_continuity(broken)["status"] == "FAIL"
    assert verify_narration_continuity(good)["status"] == "PASS"
