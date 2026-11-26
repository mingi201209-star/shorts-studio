"""EP.33 ship-impact dolphins: the model behind every claim in the narration, the timeline rules and the shared reveal sting."""
import math

import numpy as np

from benchmarks.ship_dolphin import dolphin_motion as m
from benchmarks.ship_dolphin import dolphin_timeline as tl


def test_gate_passes():
    r = m.dolphin_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    r = m.dolphin_physics()
    assert 0.8 * 30 <= r["peak_million_lb"] <= 30                     # "nearly thirty million pounds of force"
    assert 0.85 * 6700 <= r["rock_t"] <= 1.05 * 6700                  # "up to six thousand seven hundred tons of crushed rock"
    assert r["gap_to_pier_m"] > 20                                     # "stops before it ever touches the pier"
    assert 0 < r["bow_crush_m"] and 0 < r["ring_dent_m"]               # the ring bends and the bow crumples


def test_collision_slows_the_ship_to_a_stop():
    rows = m.collision()
    v = np.array([r[2] for r in rows])
    d = np.array([r[1] for r in rows])
    assert v[0] == m.V0 and v[-1] == 0.0 and np.all(np.diff(v) <= 1e-12) and np.all(np.diff(d) >= -1e-12)
    st = m.ship_state(-10.0)
    assert math.isclose(st["bow_y"], m.contact_y() - 10.0 * m.V0)


def test_dolphins_guard_the_pier_side_of_the_channel():
    for x, y in m.dolphin_centres():
        assert y < -m.PIER_HALF[1] and math.hypot(x, y) - m.DOL_R > math.hypot(m.PIER_HALF[0], m.PIER_HALF[1]) - 10


def test_spray_stays_above_the_water():
    for k in range(m.N_SPRAY):
        for t in np.arange(0.0, 4.0, 0.05):
            p = m.spray_pose(k, float(t))
            if p is not None:
                assert p[0][2] >= m.spray()[k][3] / 2 - 1e-6


def test_timeline_rules():
    segs = tl.segments()
    assert tl.pace(segs)["status"] == "PASS", tl.pace(segs)["problems"]
    assert tl.scene_alignment(segs)["status"] == "PASS"
    labels = [s["label"] for s in segs]
    assert math.isclose(segs[labels.index("D2-crushed-rock")]["t0"], tl.word_start(4, "with"))
    reveals = [s for s in segs if s["flags"].get("reveal")]
    assert len(reveals) == 1 and reveals[0]["flags"].get("cut")
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert last["segment"] == "I-loop" and 0 < last["t"] <= first["t"]
    assert np.allclose(last["cam"]["loc"], first["cam"]["loc"]) and np.allclose(last["cam"]["target"], first["cam"]["target"])
