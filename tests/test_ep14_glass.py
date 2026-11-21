import numpy as np

from benchmarks.tempered_glass import glass_motion as m
from benchmarks.tempered_glass import glass_timeline as tl


def test_gate_passes():
    r = m.glass_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert 0.9 <= m.V_CRACK / m.MILE < 1.0                      # "nearly a mile per second"
    assert m.STRENGTH_RATIO == 4.0                               # "about four times stronger"
    ts, tc = m.temperatures(0.4)
    assert ts < m.T_SET < tc                                     # "the surface hardens first"
    s, c = m.stress(60.0)
    assert s < 0 < c                                             # "squeezes the surface tight"
    assert m.cube_aspect() < m.shard_aspect()                    # "blunt little cubes instead of knife-like shards"


def test_crack_front_reaches_every_cube_before_the_pane_lets_go():
    _, cen = m.cells()
    assert m.crack_time(cen).max() < m.T_RELEASE


def test_hammer_meets_the_impact_point():
    assert np.linalg.norm(m.hammer_tip(0.0) - m._p0_world()) < 1e-9


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > m.T_RELEASE                              # frame 1 is the burst
    assert abs(last["t"] - first["t"]) < 0.01 and last["cam"]["rel"] == first["cam"]["rel"]
