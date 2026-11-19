import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"benchmarks"/"road_safety"/"rumble_cc0_reuse.py"

def test_pinned_source_and_no_quality_downgrade():
    code=SOURCE.read_text()
    ast.parse(code)
    assert "a82e05825f907cc99678ab12855527552e34323b31ae801625af4a0f563ed877" in code
    assert '"CYCLES"' in code
    assert "1080" in code and "1920" in code
    assert "32" in code
    assert '"upload_ready":False' in code

def test_no_static_hold_or_interpolation():
    txt=SOURCE.read_text()
    assert "scene.render.render" not in txt
    assert "bpy.ops.render.render(write_still=True)" in txt
    assert "car.location=(x,-.30" in txt
