"""ffmpeg has no built-in SVG decoder, so SVG scene assets (e.g. the window
comparison graphic) must be rasterized to PNG before compositing. This must
fail loudly if the rasterizer is missing, never silently skip the asset."""
from pathlib import Path
import shorts_studio.render as render_mod

def test_svg_asset_is_rasterized_before_use(tmp_path, monkeypatch):
    svg = tmp_path / "shape.svg"; svg.write_text("<svg></svg>")
    calls = []
    monkeypatch.setattr(render_mod.shutil, "which", lambda name: "/usr/bin/rsvg-convert" if name == "rsvg-convert" else "/usr/bin/"+name)
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"fake-png")
        class R: pass
        return R()
    monkeypatch.setattr(render_mod.subprocess, "run", fake_run)
    result = render_mod._resolve_asset({"asset": str(svg), "asset_url": None}, tmp_path, "s1", 0)
    assert result.suffix == ".png"
    assert result.exists()
    assert any("rsvg-convert" in c for c in calls[0])

def test_svg_rasterization_fails_loudly_without_rsvg_convert(tmp_path, monkeypatch):
    svg = tmp_path / "shape.svg"; svg.write_text("<svg></svg>")
    monkeypatch.setattr(render_mod.shutil, "which", lambda name: None)
    import pytest
    with pytest.raises(RuntimeError, match="rsvg-convert"):
        render_mod._resolve_asset({"asset": str(svg), "asset_url": None}, tmp_path, "s1", 0)

def test_non_svg_asset_is_untouched(tmp_path, monkeypatch):
    img = tmp_path / "photo.jpg"; img.write_bytes(b"x")
    result = render_mod._resolve_asset({"asset": str(img), "asset_url": None}, tmp_path, "s1", 0)
    assert result == img
