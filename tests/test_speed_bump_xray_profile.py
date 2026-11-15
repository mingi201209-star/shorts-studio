import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = r"""
import sys, json
sys.path.insert(0, %r)
from benchmarks.speed_bump import speed_bump_motion as m
assert m.FILM == "xray" and m.PASS_FRAMES == 960
prev = 0
for a, b, k, l in m.SHOTS:
    assert a == prev + 1; prev = b
assert prev == 960
assert m.xray_factor(1) == 0 and m.xray_factor(300) == 1 and m.xray_factor(800) == 0
fs = [m.xray_factor(f) for f in range(130, 180)]
assert fs == sorted(fs)
starts = [0.0, 4.61, 10.48, 16.29, 21.52, 26.67]   # spoken beat starts measured by the audio check
for beat, frame in m.BEAT_PICTURE_START.items():
    assert abs(starts[beat - 1] - (frame - 1) / 30) <= 1.2, (beat, frame)
assert starts[1] < m.BEAT2_BEFORE_FRAME / 30
print("ok")
""" % str(ROOT)


def test_xray_profile_is_consistent():
    env = dict(os.environ, EP03_FILM="xray")
    out = subprocess.run([sys.executable, "-I", "-c", CODE], env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_default_profile_is_the_finished_film():
    sys.path.insert(0, str(ROOT))
    from benchmarks.speed_bump import speed_bump_motion as m
    assert m.FILM == "v1" and m.XRAY_RAMPS == (0, 0, 0, 0) and m.xray_factor(300) == 0.0
