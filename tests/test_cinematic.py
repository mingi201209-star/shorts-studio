import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import cinematic


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def test_sun_vector_is_unit_and_elevated():
    v = cinematic.sun_vector((1.0, 1.0), 35.0)
    assert abs(_norm(v) - 1.0) < 1e-9
    assert abs(v[2] - math.sin(math.radians(35.0))) < 1e-9


def test_light_points_away_from_sun():
    v = cinematic.sun_vector((0.0, 1.0), 20.0)
    d = cinematic.light_direction(v)
    assert all(abs(a + b) < 1e-12 for a, b in zip(v, d))


def test_grade_filter_stays_in_rgb_and_never_uses_eq_or_noise():
    g = cinematic.GRADE_FILTER
    assert g.startswith("format=gbrp") and g.endswith("format=yuv420p")
    assert "eq=" not in g and "noise=" not in g  # YUV-plane filters tint RGB planes


def test_grade_filter_keeps_hue_on_a_real_frame(tmp_path):
    import shutil
    if shutil.which("ffmpeg") is None:
        return
    import numpy as np
    from PIL import Image
    src = tmp_path / "in.png"
    arr = np.zeros((64, 64, 3), np.uint8)
    arr[:] = (90, 90, 90)
    Image.fromarray(arr).save(src)
    out = tmp_path / "out.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", cinematic.GRADE_FILTER,
                    str(out)], check=True)
    m = np.asarray(Image.open(out).convert("RGB")).reshape(-1, 3).mean(0)
    assert max(m) - min(m) < 6, m  # neutral grey stays neutral
