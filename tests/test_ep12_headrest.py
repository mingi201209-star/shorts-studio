from benchmarks.headrest import head_motion as m
from benchmarks.headrest import head_timeline as tl


def test_gate_passes():
    r = m.head_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    lo, t_lo = m.peak("low")
    hi, _ = m.peak("high")
    assert 55 <= lo < 60                       # "almost sixty degrees"
    assert 0.08 <= t_lo <= 0.15                # "in about a tenth of a second"
    assert hi < 20                             # "the neck stops under twenty degrees"
    assert round(lo / hi) == 3                 # "one neck bends three times further"
    assert 100 * m.BACKSET / 2.54 < 2          # "the head moves less than two inches"


def test_timeline():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    hit = next(f for f in range(tl.frame_count()) if tl.frame_state(f, segs)["t"] >= 0)
    assert hit / tl.FPS < 0.5
    last, first = tl.frame_state(tl.frame_count() - 1, segs), tl.frame_state(0, segs)
    assert abs(last["t"] - first["t"]) < 0.06 and last["t"] < 0      # both before the hit: nothing moves yet
