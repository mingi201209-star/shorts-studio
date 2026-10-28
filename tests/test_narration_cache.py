import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from shorts_studio.models import Scene
from shorts_studio.narration_cache import export_cache, reuse_scene_audio
from shorts_studio.render import CAPTION_STYLE, _caption_style


def fixture_cache(tmp_path):
    manifest = tmp_path / "project.json"
    manifest.write_text(json.dumps({"title": "cache", "scenes": [
        {"id": "scene_01", "narration": "기체가 갈라졌습니다.", "visual_description": "aircraft"}
    ]}))
    source = tmp_path / "source"
    source.mkdir()
    (source / "scene_01.mp3").write_bytes(b"known-audio")
    (source / "scene_01.timing.json").write_text(json.dumps({
        "words": [{"text": "기체가", "start": 0, "end": 1},
                  {"text": "갈라졌습니다.", "start": 1, "end": 2}], "units": []
    }))
    cache = tmp_path / "cache"
    export_cache(manifest, source, cache)
    scene = Scene(id="scene_01", narration="기체가 갈라졌습니다.", visual_description="new graphic", caption_font_size=88)
    return scene, cache

def test_cached_narration_preserves_bytes_and_caption_coverage(tmp_path):
    scene, cache = fixture_cache(tmp_path)
    output = reuse_scene_audio(scene, tmp_path / "build", cache)
    assert output[0].read_bytes() == b"known-audio"
    assert output[3]["status"] == "PASS"
    assert output[4][-1].end == 2

@pytest.mark.parametrize("change", ["audio", "timings", "source", "text", "plan"])
def test_changed_cache_or_narration_fails_closed(tmp_path, change):
    scene, cache = fixture_cache(tmp_path)
    if change == "audio":
        (cache / "scene_01.mp3").write_bytes(b"different")
    elif change == "timings":
        (cache / "scene_01.timing.json").write_text("{}")
    elif change == "source":
        (cache / "source-manifest.json").write_text("{}")
    elif change == "text":
        scene.narration = "다른 문장입니다."
    else:
        from shorts_studio.models import NarrationPhrase
        scene.narration_plan = [NarrationPhrase(role="HOOK", text="다른 말")]
    with pytest.raises(ValueError):
        reuse_scene_audio(scene, tmp_path / "build", cache)
    assert not (tmp_path / "build/scene_01.mp3").exists()

def test_default_style_preserved_and_large_style_keeps_safe_anchor():
    assert _caption_style(SimpleNamespace()) == CAPTION_STYLE
    changed = _caption_style(SimpleNamespace(caption_font_size=88))
    assert "FontSize=88" in changed
    assert "MarginV=1250" in changed
    assert "PlayResY=1920" in changed

@pytest.mark.parametrize("size", [0, 47, 97, 1000])
def test_unsafe_font_sizes_rejected(size):
    with pytest.raises(ValidationError):
        Scene(id="x", narration="text", visual_description="picture", caption_font_size=size)
