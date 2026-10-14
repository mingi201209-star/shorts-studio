"""The declarative topic builder: spec validation, media preparation and the manifest it writes.

No network: sources are small synthetic files made with FFmpeg and Pillow, and the
downloads are replaced by copies of them. Everything after the download is the real code
path, and the manifest is checked with the project's real contracts."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
from PIL import Image

from shorts_studio import topic_builder as tb
from shorts_studio.final_video_qa import verify_retention_contract
from shorts_studio.production_v2 import verify_visual_production_structure
from shorts_studio.project import load_project
from shorts_studio.visual_change import audit_visual_changes

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")

BRIEF = {
    "topic_id": "demo",
    "familiar_subject": "젖은 도로 위를 달리는 자동차 타이어",
    "contradiction_fact": "타이어가 회전하고 있어도 도로에 전혀 닿지 않을 수 있습니다",
    "surprising_consequence_fact": "멀쩡한 타이어도 빗길에서 도로와의 접촉을 완전히 잃을 수 있습니다",
    "counterintuitive_fact": "타이어 홈이 있어도 물의 양이 많으면 접촉을 지키지 못할 수 있습니다",
    "anomaly_fact": "젖은 도로 위에서 타이어가 돌기만 하고 바닥을 밟지 못하는 경우가 있습니다",
    "payoff_text": "물이 빠지는 속도보다 쌓이는 속도가 빨라지면 타이어는 물 위로 떠서 도로와의 접촉을 잃을 수 있습니다",
    "grounded_facts": ["타이어 트레드 홈은 접촉 영역의 물 배출에 도움을 줍니다"],
}
HOOKS = {
    "contradiction": "빗길에선 타이어가 돌고 있어도, 실은 도로에 닿지 않을 수 있습니다.",
    "surprising_consequence": "놀랍게도 멀쩡한 타이어가 빗길에선 도로와의 접촉을 잃을 수 있습니다.",
    "counterintuitive_fact": "타이어 홈이 멀쩡해도, 실은 물을 다 빼내지 못할 수 있습니다.",
    "visible_anomaly": "이상하게도 빗길에선 타이어가 돌면서도 바닥을 밟지 못할 수 있습니다.",
}


def _beat(asset, cue, info, role, mode="real_footage", kind="concept"):
    return {"asset": asset, "cue": cue, "info_role": info, "concept_id": f"c_{asset}", "state_id": f"s_{asset}",
            "kind": kind, "qa_label": f"real footage showing {info.replace('_', ' ')}",
            "requirement": f"{cue} 장면이 실제 화면에 보여야 함", "role": role, "visual_mode": mode}


def spec_dict():
    return {
        "topic_id": "demo", "title": "타이어가 도로에서 뜨는 이유", "overlay_title": "타이어가 도로에서 뜬다",
        "brief": dict(BRIEF), "hooks": dict(HOOKS),
        "observable_phenomenon": "젖은 도로에서 타이어가 물막 위에 올라타 접촉을 잃는다.",
        "silent_story": "빗길 → 타이어 → 물막 → 홈 → 물 쐐기 → 물막 위 → 운전 시점",
        "visual_description": "Real footage with callouts on the real picture.",
        "scene_requirement": "각 내레이션 단서에 맞는 장면이 실제 화면에 보여야 함",
        "sources": {
            "wide": {"kind": "video", "url": "https://example.invalid/wide.mp4", "page": "https://example.invalid/wide",
                     "attribution": "A / Example / CC0"},
            "tall": {"kind": "video", "url": "https://example.invalid/tall.mp4", "page": "https://example.invalid/tall",
                     "attribution": "B / Example / CC0"},
            "photo": {"kind": "photo", "url": "https://example.invalid/photo.jpg", "page": "https://example.invalid/photo",
                      "attribution": "C / Example / CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/"},
        },
        "clips": {
            "spray": {"source": "wide", "seconds": 2.0},
            "tire": {"source": "tall", "seconds": 2.0, "focus": [0.5, 0.2]},
            "surface": {"source": "wide", "start": 1.0, "seconds": 2.0, "focus": [0.9, 0.5]},
            "grooves": {"source": "photo"},
            "wheel": {"source": "tall", "start": 1.0, "seconds": 2.0},
            "pov": {"source": "wide", "start": 2.0, "seconds": 2.0, "focus": [0.1, 0.5]},
            "film_base": {"source": "tall", "start": 2.0, "seconds": 2.0},
        },
        "overlays": {
            "wedge": {"base": "film_base", "headline": "하이드로플레이닝",
                      "callouts": [{"text": "물 쐐기", "at": [300, 300], "target": [420, 520]},
                                   {"text": "접촉면", "at": [680, 620], "target": [560, 760], "appear": 0.8, "color": "#7FD1FF"}]},
        },
        "scenes": [
            {"id": "s_hook", "phrases": [{"role": "HOOK", "text": "(판정된 훅으로 교체됨)"},
                                         {"role": "CRISIS", "text": "문제는 고무가 아니라, 타이어 밑으로 파고드는 물입니다."}],
             "beats": [_beat("spray", "빗길에선 타이어가 돌고 있어도", "real_tires_throwing_spray", "hero"),
                       _beat("tire", "실은 도로에 닿지 않을 수 있습니다", "real_tire_closeup", "support"),
                       _beat("surface", "문제는 고무가 아니라", "real_water_film", "support")]},
            {"id": "s_reveal", "phrases": [{"role": "REVEAL", "text": "타이어 홈은 이 물을 옆으로 빼냅니다."},
                                           {"role": "EXPLANATION", "text": "그런데 속도가 빨라지면, 물이 더 빨리 밀려듭니다."}],
             "beats": [_beat("grooves", "타이어 홈은 이 물을 옆으로 빼냅니다", "real_tread_grooves", "evidence", "real_photo"),
                       _beat("wheel", "그런데 속도가 빨라지면", "real_wheel_speed", "mechanism")]},
            {"id": "s_twist", "phrases": [{"role": "TWIST", "text": "결국 타이어가 물막 위에 올라탑니다."},
                                          {"role": "PAYOFF", "text": "이게 바로 하이드로플레이닝입니다."}],
             "beats": [_beat("pov", "결국 타이어가 물막 위에 올라탑니다", "real_driver_pov", "second_peak"),
                       _beat("wedge", "이게 바로 하이드로플레이닝입니다", "named_water_wedge", "payoff")]},
        ],
        "fact_sources": ["NHTSA 하이드로플레이닝 안전 안내 (https://www.nhtsa.gov)"],
    }


@pytest.fixture(scope="module")
def raw_sources(tmp_path_factory):
    root = tmp_path_factory.mktemp("raw")

    def video(name, size):
        out = root / name
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration=5",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)], check=True)
        return out
    photo = root / "photo.jpg"
    Image.effect_noise((2600, 2200), 64).convert("RGB").save(photo, quality=90)
    return {"wide": video("wide.mp4", "1920x1080"), "tall": video("tall.mp4", "1080x1920"), "photo": photo}


@pytest.fixture(scope="module")
def built(tmp_path_factory, raw_sources):
    """One real build shared by the tests that only read its outputs."""
    root = tmp_path_factory.mktemp("build")
    spec = tb.TopicSpec.model_validate(spec_dict())
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(tb, "fetch_sources", lambda spec, source_dir, cache_dir=None: raw_sources)
        # The narration preflight calls the TTS provider; it has its own test below.
        patch.setattr(tb, "check_narration_timing", lambda spec, hook, work: {
            "status": "PASS", "beats": [{"beat": f"b{i}", "seconds": 1.0} for i in range(7)]})
        return tb.build_topic(spec, root)


def test_box_crop_keeps_the_box_aspect_and_follows_focus():
    w, h, x, y = tb.box_crop(1920, 1080)
    assert (h, y) == (1080, 0) and abs(w / h - tb.BOX_W / tb.BOX_H) < 0.01 and x == (1920 - w) // 2
    assert tb.box_crop(1920, 1080, (0.0, 0.5))[2] == 0
    assert tb.box_crop(1920, 1080, (1.0, 0.5))[2] == 1920 - w
    w, h, x, y = tb.box_crop(1080, 1920, (0.5, 0.25))
    assert w == 1080 and abs(w / h - tb.BOX_W / tb.BOX_H) < 0.01 and y == round((1920 - h) * 0.25)


def test_spec_rejects_broken_references_and_reused_pictures():
    data = spec_dict()
    data["clips"]["tire"]["source"] = "missing"
    with pytest.raises(ValueError, match="unknown source"):
        tb.TopicSpec.model_validate(data)
    data = spec_dict()
    data["scenes"][1]["beats"][1]["asset"] = "spray"
    with pytest.raises(ValueError, match="used twice"):
        tb.TopicSpec.model_validate(data)
    data = spec_dict()
    data["scenes"][0]["phrases"][0]["role"] = "SETUP"
    with pytest.raises(ValueError, match="HOOK"):
        tb.TopicSpec.model_validate(data)
    data = spec_dict()
    data["overlays"]["wedge"]["base"] = "nope"
    with pytest.raises(ValueError, match="unknown clip"):
        tb.TopicSpec.model_validate(data)


def test_a_distorting_or_oversized_crop_is_refused():
    with pytest.raises(ValueError, match="aspect"):
        tb._resolved_crop(tb.ClipSpec(source="s", crop="1000:500:0:0"), 1920, 1080)
    with pytest.raises(ValueError, match="leaves"):
        tb._resolved_crop(tb.ClipSpec(source="s", crop="1114:1080:900:0"), 1920, 1080)


def test_a_photo_too_small_for_the_picture_is_refused(tmp_path):
    small = tmp_path / "small.jpg"
    Image.new("RGB", (800, 700), "gray").save(small)
    with pytest.raises(ValueError, match="upscaled"):
        tb.prepare_photo(small, tmp_path / "out.jpg", tb.ClipSpec(source="s"))


def test_a_clip_longer_than_its_source_is_refused(tmp_path, raw_sources):
    with pytest.raises(ValueError, match="needs"):
        tb.prepare_video_clip(raw_sources["wide"], tmp_path / "x.mp4", tb.ClipSpec(source="s", start=4.0, seconds=3.0))


def test_a_prepared_clip_is_rebuilt_when_its_recipe_changes_and_reused_when_it_does_not(tmp_path, raw_sources):
    out = tmp_path / "clip.mp4"
    left = tb.ClipSpec(source="s", seconds=2.0, focus=(0.0, 0.5))
    tb.prepare_video_clip(raw_sources["wide"], out, left)
    first, first_mtime = tb.sha256(out), out.stat().st_mtime_ns
    tb.prepare_video_clip(raw_sources["wide"], out, left)
    assert out.stat().st_mtime_ns == first_mtime, "the same recipe must reuse the prepared file"
    tb.prepare_video_clip(raw_sources["wide"], out, left.model_copy(update={"focus": (1.0, 0.5)}))
    assert tb.sha256(out) != first, "an edited crop must never keep the stale picture"


def test_clips_are_prepared_for_their_measured_time_on_screen_only():
    spec = tb.TopicSpec.model_validate(spec_dict())
    timing = {"beats": [{"seconds": s} for s in (1.2, 0.2, 1.9, 2.4, 1.0, 1.3, 2.6)]}
    holds = tb.asset_holds(spec, timing)
    assert holds["film_base"] == 2.6, "an overlay's base is on screen for the overlay's beat"
    assert holds["spray"] == 1.2 and "wedge" not in holds
    clip = tb.ClipSpec(source="s", seconds=6.0)
    assert tb.trimmed(clip, 2.4).seconds == pytest.approx(2.4 + tb.HOLD_MARGIN_SECONDS)
    assert tb.trimmed(clip, 0.2).seconds == 1.5
    assert tb.trimmed(tb.ClipSpec(source="s", seconds=2.0), 2.4).seconds == 2.0, "never longer than authored"
    assert tb.trimmed(clip, None) is clip
    with pytest.raises(ValueError, match="measured beats"):
        tb.asset_holds(spec, {"beats": timing["beats"][:3]})


def test_callout_outside_the_picture_is_refused(tmp_path):
    with pytest.raises(ValueError, match="does not fit"):
        tb.render_callout_layer(tb.CalloutSpec(text="물 쐐기", at=(960, 300), target=(500, 500)), tmp_path / "c.png")


def test_callout_layer_is_transparent_except_for_the_label(tmp_path):
    out = tb.render_callout_layer(tb.CalloutSpec(text="물 쐐기", at=(300, 300), target=(420, 520)), tmp_path / "c.png")
    layer = Image.open(out)
    assert layer.size == (tb.BOX_W, tb.BOX_H) and layer.mode == "RGBA"
    alpha = layer.getchannel("A")
    assert alpha.getpixel((900, 880)) == 0, "untouched picture must stay fully visible"
    assert alpha.getpixel((300, 300)) > 150, "label plate must be opaque enough to read"
    assert alpha.getpixel((420, 520)) > 200, "target dot must be drawn"


def test_build_writes_prepared_pictures_and_a_manifest_the_real_contracts_accept(built):
    manifest = json.loads(built["manifest"].read_text(encoding="utf-8"))

    for key, path in built["assets"].items():
        if path.suffix == ".mp4":
            probe = json.loads(subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=width,height,r_frame_rate,pix_fmt:format=duration", "-of", "json", str(path)],
                capture_output=True, text=True, check=True).stdout)
            stream = probe["streams"][0]
            assert (stream["width"], stream["height"], stream["r_frame_rate"], stream["pix_fmt"]) == (
                tb.BOX_W, tb.BOX_H, "30/1", "yuv420p"), key
            assert float(probe["format"]["duration"]) >= 1.8, key
        else:
            assert Image.open(path).size == (tb.BOX_W * 2, tb.BOX_H * 2), key

    first = manifest["scenes"][0]["narration_plan"][0]
    assert first["role"] == "HOOK" and first["text"] in HOOKS.values() and first["hook_type"] in HOOKS
    assert manifest["scenes"][0]["narration"].startswith(first["text"])
    assert manifest["silent_interest_review"] == "pending", "the builder must never claim a human verdict"
    for flag in ("strict_meaningful_visual_changes", "strict_retention_contract", "strict_visual_production_v2"):
        assert manifest[flag] is True

    beats = [b for s in manifest["scenes"] for b in s["visual_beats"]]
    for beat in beats:
        digest = tb.sha256(tb.Path(beat["asset"]))
        assert beat["visual_qa_expected_sha256"] == [digest] == [beat["visual_change"]["source_sha256"]]
        assert beat["attribution"]
    overlay_beat = beats[-1]
    assert overlay_beat["asset"].endswith("wedge.mp4") and overlay_beat["attribution"] == "B / Example / CC0"

    project = load_project(built["manifest"])
    assert audit_visual_changes(project)["status"] == "PASS"
    assert verify_visual_production_structure(project)["status"] == "PASS"
    assert verify_retention_contract(project)["status"] == "PASS"


def test_overlay_adds_labels_and_leaves_the_rest_of_the_picture_alone(tmp_path, built):
    import numpy as np

    def frame(path, seconds):
        out = tmp_path / f"{path.stem}_{seconds}.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(seconds), "-i", str(path), "-frames:v", "1", str(out)],
                       check=True)
        return np.asarray(Image.open(out).convert("RGB")).astype(int)
    base, labelled = frame(built["assets"]["film_base"], 1.5), frame(built["assets"]["wedge"], 1.5)
    difference = np.abs(base - labelled).max(axis=2)
    assert difference[280:320, 240:360].mean() > 20, "the label plate must be visible on the picture"
    assert difference[840:900, 40:200].mean() < 6, "pixels away from every label must be the base picture"
    early = frame(built["assets"]["wedge"], 0.0)
    assert np.abs(base[600:640, 620:740] - early[600:640, 620:740]).mean() < np.abs(
        base[600:640, 620:740] - labelled[600:640, 620:740]).mean(), "the second label fades in later than the first frame"


def test_description_credits_only_the_sources_that_are_on_screen():
    data = spec_dict()
    data["sources"]["unused"] = {"kind": "video", "url": "https://example.invalid/unused.mp4",
                                 "page": "https://example.invalid/unused", "attribution": "Unused / Example / CC0"}
    text = tb.upload_description(tb.TopicSpec.model_validate(data))
    for expected in ("A / Example / CC0", "B / Example / CC0", "C / Example / CC BY 4.0",
                     "https://creativecommons.org/licenses/by/4.0/", "NHTSA"):
        assert expected in text
    assert "Unused" not in text


def test_hook_strategy_without_a_grounding_fact_is_refused():
    data = spec_dict()
    data["hooks"]["unresolved_cause_effect"] = "타이어 홈이 물을 계속 빼내는데도, 이상하게 접촉을 잃는 순간이 옵니다."
    with pytest.raises(ValueError, match="without a brief fact"):
        tb.select_hook(tb.TopicSpec.model_validate(data))


def test_cached_download_is_reused_and_a_long_rate_limit_fails_fast(tmp_path, monkeypatch):
    url = "https://upload.wikimedia.org/x/clip.webm"
    cache = tmp_path / "cache"
    cached = tb.cache_path(url, cache)
    cached.parent.mkdir()
    cached.write_bytes(b"\x1a\x45\xdf\xa3" + b"0" * 400_000)
    monkeypatch.setattr(tb.urllib.request, "urlopen", lambda *a, **k: pytest.fail("a cached file must not be requested again"))
    out = tb._fetch(url, tmp_path / "out.webm", 300_000, tb._validate_video, cache)
    assert out.read_bytes() == cached.read_bytes()

    import email.message
    headers = email.message.Message()
    headers["Retry-After"] = "600"

    def refuse(*a, **k):
        raise tb.urllib.error.HTTPError(url, 429, "Too Many Requests", headers, None)
    monkeypatch.setattr(tb.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(tb.time, "sleep", lambda s: pytest.fail("must not wait out a 10-minute rate limit"))
    with pytest.raises(RuntimeError, match="rate limiting"):
        tb._fetch(url, tmp_path / "other.webm", 300_000, tb._validate_video)


def test_stage_timer_records_each_stage_even_when_it_fails():
    timer = tb.StageTimer()
    assert timer.run("ok", lambda: 7) == 7
    with pytest.raises(ZeroDivisionError):
        timer.run("boom", lambda: 1 / 0)
    assert [s["stage"] for s in timer.report()["stages"]] == ["ok", "boom"]


def _hook(spec):
    return tb.select_hook(spec)


def test_cues_are_checked_against_the_hook_that_won():
    spec = tb.TopicSpec.model_validate(spec_dict())
    hook = _hook(spec)
    tb.check_cues(spec, hook)
    data = spec_dict()
    data["scenes"][0]["beats"][0]["cue"] = "어디에도 없는 말"
    data["scenes"][1]["beats"][1]["cue"] = "니다"
    broken = tb.TopicSpec.model_validate(data)
    with pytest.raises(ValueError) as error:
        tb.check_cues(broken, hook)
    message = str(error.value)
    assert hook.text in message and "'어디에도 없는 말' occurs 0" in message and "'니다' occurs 2" in message


def test_text_contracts_fail_before_any_media_work(monkeypatch):
    monkeypatch.setattr(tb, "fetch_sources", lambda *a, **k: pytest.fail("no download may start before the text contracts pass"))
    data = spec_dict()
    data["scenes"][2]["beats"][0]["role"] = "support"  # no second_peak any more
    spec = tb.TopicSpec.model_validate(data)
    with pytest.raises(ValueError, match="second_peak"):
        tb.check_text_contracts(spec, _hook(spec))
    data = spec_dict()
    data["scenes"][0]["beats"][0]["requirement"] = "젖은 노면 위 자동차가 물보라를 일으키는 장면"
    spec = tb.TopicSpec.model_validate(data)
    with pytest.raises(ValueError, match="share no common words"):
        tb.check_text_contracts(spec, _hook(spec))
    good = spec_dict()
    good["scenes"][0]["beats"][0]["requirement"] = "빗길에선 타이어가 물보라를 일으키는 실제 장면"
    spec = tb.TopicSpec.model_validate(good)
    tb.check_text_contracts(spec, _hook(spec))


def _fake_synthesis(seconds_per_word):
    """Stand-in for the network call only: writes the timing file the renderer writes."""
    def synthesize(scene, build, **kwargs):
        words, units, cursor = [], [], 0.0
        for phrase in scene.narration_plan:
            start = cursor
            for token in phrase.text.split():
                words.append({"text": token, "start": cursor, "end": cursor + seconds_per_word * 0.9})
                cursor += seconds_per_word
            units.append({"role": phrase.role, "text": phrase.text, "start": start, "end": cursor})
        (build / f"{scene.id}.timing.json").write_text(json.dumps({"words": words, "units": units}), encoding="utf-8")
        return build / f"{scene.id}.mp3", cursor, build / f"{scene.id}.srt", {"status": "PASS"}, [], units
    return synthesize


def test_narration_timing_reports_measured_beats_and_fails_a_long_hold(tmp_path, monkeypatch):
    from shorts_studio import render as renderer
    data = spec_dict()
    data["scenes"][0]["beats"][0]["requirement"] = "빗길에선 타이어가 물보라를 일으키는 실제 장면"
    spec = tb.TopicSpec.model_validate(data)
    hook = _hook(spec)
    monkeypatch.setattr(renderer, "_synthesize_scene_audio", _fake_synthesis(1.4))
    with pytest.raises(ValueError) as error:
        tb.check_narration_timing(spec, hook, tmp_path / "slow")
    message = str(error.value)
    assert "cut cadence" in message and "measured beats:" in message and "s_hook[0]=" in message
    monkeypatch.setattr(renderer, "_synthesize_scene_audio", _fake_synthesis(0.1))
    with pytest.raises(ValueError, match="beats shorter than 1.2s"):
        tb.check_narration_timing(spec, hook, tmp_path / "fast")


def test_labelled_pictures_are_collected_on_one_preview_sheet(built):
    sheet = built["manifest"].parent / "work" / "overlays_preview.jpg"
    assert sheet.is_file()
    assert Image.open(sheet).size == (tb.BOX_W // 2 * len(spec_dict()["overlays"]), tb.BOX_H // 2)
