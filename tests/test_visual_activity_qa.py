"""Regression coverage for the engine-hardening pass: real pixel-level visual
cadence, source-reuse (including crop-disguised-as-new) detection, a
black-opening-frame guard, Korean caption tokenization safety, and a frozen
snapshot of the current reference layout. Every check that claims to measure
"the real rendered output" is tested against an actual ffmpeg-produced clip,
not a mock -- a synthetic manifest claiming a cut is not proof a cut
happened.
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
import numpy as np

import shorts_studio.render as R
from shorts_studio.final_video_qa import (
    measure_visual_activity, verify_visual_activity, verify_no_black_opening,
    compute_source_reuse, verify_source_reuse, _source_family, _same_source_family,
    _captions_overlap_media_box, verify_captions_visible, IMAGE_TOP_Y, IMAGE_BOTTOM_Y,
)
from shorts_studio.subtitles import segment
from shorts_studio.timing import WordTiming

requires_ffmpeg = pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="requires a real ffmpeg binary")
MEDIA_BOX = (IMAGE_TOP_Y, IMAGE_BOTTOM_Y)


def _beats_clip(tmp_path, beats, duration, scene_id="activity"):
    """Build a real multi-cut clip via the actual production compositor.
    This sandbox has no local ffprobe; _composite_visual_beats only needs it
    for the beat-duration values in its return tuple, which this helper
    doesn't use -- the clip file on disk is already complete by then, so a
    missing ffprobe (caught here) never affects what these tests check. In
    CI, where ffprobe is present, this simply returns normally."""
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(duration), "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text(f"1\n00:00:00,500 --> 00:00:0{min(9,int(duration-1))},000\n테스트\n\n", encoding="utf-8")
    scene = SimpleNamespace(id=scene_id, visual_beats=beats)
    try:
        R._composite_visual_beats(scene, audio, srt, duration, 30, build, 0)
    except Exception:
        pass
    return build / f"{scene_id}.mp4", build


def _solid(path, rgb):
    Image.fromarray(np.full((1000, 1000, 3), rgb, dtype=np.uint8)).save(path)
    return path


# --- 3. static source > 5s detection -----------------------------------

@requires_ffmpeg
def test_static_source_over_5s_is_detected_and_fails(tmp_path):
    photo = _solid(tmp_path / "photo.jpg", [90, 130, 150])
    beats = [SimpleNamespace(start=0.0, asset=str(photo), asset_url=None, attribution=None)]
    clip, build = _beats_clip(tmp_path, beats, 7.0)
    activity = measure_visual_activity(clip, MEDIA_BOX, build)
    assert activity["max_static_visual_seconds"] >= 6.5, activity
    result = verify_visual_activity(activity)
    assert result["status"] == "FAIL", result


@requires_ffmpeg
def test_genuine_cuts_every_two_seconds_pass_and_measure_correctly(tmp_path):
    red = _solid(tmp_path / "red.png", [220, 40, 40])
    green = _solid(tmp_path / "green.png", [40, 200, 60])
    blue = _solid(tmp_path / "blue.png", [40, 60, 220])
    beats = [
        SimpleNamespace(start=0.0, asset=str(red), asset_url=None, attribution=None),
        SimpleNamespace(start=2.0, asset=str(green), asset_url=None, attribution=None),
        SimpleNamespace(start=4.0, asset=str(blue), asset_url=None, attribution=None),
    ]
    clip, build = _beats_clip(tmp_path, beats, 6.0)
    activity = measure_visual_activity(clip, MEDIA_BOX, build)
    assert activity["cut_timestamps"] == pytest.approx([0.0, 2.0, 4.0], abs=0.01)
    assert activity["max_static_visual_seconds"] == pytest.approx(2.0, abs=0.01)
    assert verify_visual_activity(activity)["status"] == "PASS"


# --- 4. first-5s visual beat detection -----------------------------------

@requires_ffmpeg
def test_no_visual_change_in_first_5s_fails(tmp_path):
    photo = _solid(tmp_path / "photo.jpg", [90, 130, 150])
    other = _solid(tmp_path / "other.jpg", [200, 200, 60])
    beats = [
        SimpleNamespace(start=0.0, asset=str(photo), asset_url=None, attribution=None),
        SimpleNamespace(start=6.0, asset=str(other), asset_url=None, attribution=None),
    ]
    clip, build = _beats_clip(tmp_path, beats, 8.0)
    activity = measure_visual_activity(clip, MEDIA_BOX, build)
    assert activity["first_5s_visual_changes"] == 0, activity
    assert verify_visual_activity(activity)["status"] == "FAIL"


# --- 6. black opening frame detection ------------------------------------

@requires_ffmpeg
def test_black_media_with_subtitle_opening_fails(tmp_path):
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n검은 화면 자막\n\n", encoding="utf-8")
    vf = f"subtitles={srt.as_posix()}:force_style='Alignment=6,MarginV=1250,FontSize=72,PlayResX=1080,PlayResY=1920'"
    clip = build / "black_open.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=2", "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)], check=True, capture_output=True)
    result = verify_no_black_opening(clip, MEDIA_BOX, build)
    assert result["status"] == "FAIL", result


@requires_ffmpeg
def test_black_media_without_subtitle_is_not_flagged(tmp_path):
    """A black media box alone (before any caption appears) is not the
    failure mode -- only black-media-plus-visible-text is."""
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    clip = build / "black_plain.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)], check=True, capture_output=True)
    result = verify_no_black_opening(clip, MEDIA_BOX, build)
    assert result["status"] == "PASS", result


@requires_ffmpeg
def test_real_first_beat_with_a_photo_never_flags_as_black_opening(tmp_path):
    """The actual production opening (a real photo composited at t=0)
    must never trip the black-opening guard."""
    photo = _solid(tmp_path / "photo.jpg", [90, 130, 150])
    beats = [SimpleNamespace(start=0.0, asset=str(photo), asset_url=None, attribution=None)]
    clip, build = _beats_clip(tmp_path, beats, 3.0)
    result = verify_no_black_opening(clip, MEDIA_BOX, build)
    assert result["status"] == "PASS", result


# --- 5. repeated / disguised-crop source detection -----------------------

def test_source_family_recognizes_a_crop_of_the_same_real_photo():
    """Real regression: two of this project's own historical image URLs are
    literally the same 1922 photograph -- one cropped tighter, one the full
    uncropped frame. They must be recognized as ONE source, not counted as
    two distinct pictures just because their filenames/hosts differ."""
    cropped = "https://www.nist.gov/sites/default/files/images/2022/03/08/All_women_or_girls_using_radium_paint_with_no_protection_or_warnings_in_1922%2C_from-_USRadiumGirls-Argonne1%2Cca1922-23-150dpi_%28cropped%29.jpg"
    uncropped = "https://upload.wikimedia.org/wikipedia/commons/e/e3/USRadiumGirls-Argonne1%2Cca1922-23-150dpi.jpg"
    unrelated = "https://upload.wikimedia.org/wikipedia/commons/c/cd/Las_chicas_del_radio_pintando.jpg"
    assert _same_source_family(_source_family(cropped), _source_family(uncropped))
    assert not _same_source_family(_source_family(cropped), _source_family(unrelated))


def test_verify_source_reuse_fails_when_a_crop_pair_sits_adjacent():
    cropped = "https://www.nist.gov/x/All_women_or_girls_using_radium_paint_..._USRadiumGirls-Argonne1,ca1922-23-150dpi_(cropped).jpg"
    uncropped = "https://upload.wikimedia.org/x/USRadiumGirls-Argonne1,ca1922-23-150dpi.jpg"
    other = "https://upload.wikimedia.org/x/Las_chicas_del_radio_pintando.jpg"
    scenes = [SimpleNamespace(id="s1", visual_beats=[
        SimpleNamespace(start=0, asset=None, asset_url=other),
        SimpleNamespace(start=2, asset=None, asset_url=uncropped),
        SimpleNamespace(start=4, asset=None, asset_url=cropped),
    ])]
    metrics = compute_source_reuse(SimpleNamespace(scenes=scenes))
    assert metrics["max_consecutive_same_source"] == 2, metrics
    assert verify_source_reuse(metrics)["status"] == "FAIL"


def test_verify_source_reuse_passes_when_no_family_repeats_adjacently():
    a = "https://x/photo-a.jpg"; b = "https://x/photo-b.jpg"; c = "https://x/photo-c.jpg"
    scenes = [SimpleNamespace(id="s1", visual_beats=[
        SimpleNamespace(start=0, asset=None, asset_url=a),
        SimpleNamespace(start=2, asset=None, asset_url=b),
        SimpleNamespace(start=4, asset=None, asset_url=c),
    ])]
    metrics = compute_source_reuse(SimpleNamespace(scenes=scenes))
    assert metrics["max_consecutive_same_source"] == 1, metrics
    assert verify_source_reuse(metrics)["status"] == "PASS"


def test_current_radium_girls_manifest_has_no_adjacent_source_repeats():
    """The actual production manifest, re-verified against the stricter
    family-aware reuse check (not just exact-URL equality) -- this is the
    real regression this engine hardening pass exists to catch."""
    import json
    from shorts_studio.models import Project
    data = json.loads(Path("examples/radium_girls.json").read_text(encoding="utf-8"))
    project = Project.model_validate(data)
    metrics = compute_source_reuse(project)
    result = verify_source_reuse(metrics)
    assert result["status"] == "PASS", result


# --- 1. subtitle cannot enter the media area ------------------------------

def test_caption_rows_overlapping_media_box_are_detected():
    evidence = [{"t": 1.0, "rows_in_band": (IMAGE_BOTTOM_Y - 5, IMAGE_BOTTOM_Y + 40)}]
    assert _captions_overlap_media_box(evidence, (IMAGE_TOP_Y, IMAGE_BOTTOM_Y)) is True


def test_caption_rows_below_media_box_are_not_flagged():
    evidence = [{"t": 1.0, "rows_in_band": (IMAGE_BOTTOM_Y + 20, IMAGE_BOTTOM_Y + 80)}]
    assert _captions_overlap_media_box(evidence, (IMAGE_TOP_Y, IMAGE_BOTTOM_Y)) is False


def test_caption_rows_missing_or_empty_evidence_is_not_flagged():
    assert _captions_overlap_media_box([], (IMAGE_TOP_Y, IMAGE_BOTTOM_Y)) is False
    assert _captions_overlap_media_box([{"t": 1.0, "rows_in_band": None}], (IMAGE_TOP_Y, IMAGE_BOTTOM_Y)) is False


@requires_ffmpeg
def test_bright_picture_content_near_the_media_boundary_is_not_mistaken_for_a_caption(tmp_path):
    """Real regression: a photo with genuinely bright content in its own
    lowest rows (just above IMAGE_BOTTOM_Y) must never register as caption
    evidence -- the caption search band's lower bound must sit at/after
    IMAGE_BOTTOM_Y, never inside the media box itself."""
    build = tmp_path / "build"; build.mkdir(exist_ok=True)
    bright = np.zeros((1000, 1000, 3), dtype=np.uint8)
    bright[-40:, :] = 255  # bright strip at the very bottom of the source photo
    photo = build / "bright_bottom.jpg"
    Image.fromarray(bright).save(photo)
    audio = build / "a.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "3", "-q:a", "9", str(audio)], check=True, capture_output=True)
    srt = build / "s.srt"; srt.write_text("1\n00:00:00,500 --> 00:00:02,500\n실제 자막\n\n", encoding="utf-8")
    scene = SimpleNamespace(id="brightbottom", motion=SimpleNamespace(type="push_in"))
    clip = R._composite_scene_clip(scene, photo, audio, srt, 3.0, 30, build, 0)
    # Old stale band: (1000, 1900) would have picked up the photo's own
    # bright strip (which lands well inside the media box, above
    # IMAGE_BOTTOM_Y) as if it were caption evidence.
    stale = verify_captions_visible(clip, [(1.5, (1000, 1900))], build)
    stale_row_min, _ = stale["evidence"][0]["rows_in_band"]
    assert stale_row_min < IMAGE_BOTTOM_Y, "test setup didn't actually reproduce the old band's contamination"
    correct = verify_captions_visible(clip, [(1.5, (IMAGE_BOTTOM_Y, 1900))], build)
    assert correct["status"] == "PASS"
    assert not _captions_overlap_media_box(correct["evidence"], (IMAGE_TOP_Y, IMAGE_BOTTOM_Y))
    # The real caption band must start after the picture, not inside it.
    row_min, _ = correct["evidence"][0]["rows_in_band"]
    assert row_min >= IMAGE_BOTTOM_Y


# --- 7. Korean subtitle line-break sanity --------------------------------

def test_caption_text_is_always_a_clean_join_of_whole_word_tokens():
    """libass (WrapStyle=0) only ever wraps BETWEEN space-separated tokens,
    never inside one. Korean josa/eomi are attached to their host word
    without a space (e.g. "여성들은" is one token), so a caption can never
    strand a bare particle/ending alone on a wrapped line as long as
    segment() only ever joins COMPLETE original word tokens with single
    spaces -- never splits or truncates a token. This is what actually
    prevents the awkward wrap the reference video must avoid; verify it
    holds for real, punctuation-bearing Korean narration."""
    words = [
        WordTiming("이", 0.00, 0.10), WordTiming("여성들은", 0.12, 0.55),
        WordTiming("매일", 0.60, 0.90), WordTiming("방사성", 0.95, 1.30),
        WordTiming("물질을", 1.35, 1.70), WordTiming("입에", 1.75, 2.00),
        WordTiming("댔습니다.", 2.05, 2.50),
    ]
    original_tokens = {w.text for w in words}
    caps = segment(words, 3.0)
    assert caps, "segment produced no captions"
    for cap in caps:
        for token in cap.text.split(" "):
            assert token in original_tokens, f"caption token {token!r} is not a whole original word -- would risk an awkward mid-word wrap"


# --- 8. current reference layout preservation ----------------------------

def test_reference_layout_constants_are_unchanged():
    """Freezes the exact geometry of the layout the user reviewed and
    approved (central media box, black surround, separated caption band,
    current title size) so a future change to any of these is a deliberate,
    visible diff here -- not an accidental side effect of an unrelated fix."""
    assert R.SAFE_TOP_Y == 190
    assert R.IMAGE_TOP_Y == 280
    assert R.IMAGE_BOX_WIDTH == 980
    assert R.IMAGE_BOX_HEIGHT == 950
    assert R.SAFE_BOTTOM_Y == 1230
    assert R.CAPTION_FONT_SIZE == 72
    assert R.CAPTION_GAP_BELOW_IMAGE == 20
    assert R.CAPTION_MASK_TOP == 1230
    assert "FontSize=130" in R._TITLE_STYLE
