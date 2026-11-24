import math

from benchmarks.bascule_bridge import bascule_motion as m
from benchmarks.bascule_bridge import bascule_timeline as tl


def test_gate_passes():
    r = m.bascule_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    assert m.M_LEAF / 1000 >= 2000                                          # "each half weighs thousands of tons"
    assert m.M_CW > m.M_LEAF                                                # "a counterweight heavier than the road itself"
    w = m.opening(True)
    assert w["peak_hp"] <= 2 * 108                                          # "two motors no stronger than a car's engine"
    assert 45 <= m.T_OPEN <= 75                                             # "in about a minute"
    assert m.opening(False)["peak_hp"] > 50 * w["peak_hp"]                  # without the counterweight: far more
    assert m.cw_lowest_z(math.radians(m.OPEN_DEG)) < m.cw_lowest_z(0.0) - 6  # "the counterweight swings down into the pit"


def test_story_clock():
    assert m.angle(-5) == 0 and abs(m.angle(m.T_OPEN + 1) - math.radians(m.OPEN_DEG)) < 1e-9
    assert m.angle(m.T_DOWN + m.T_OPEN + 1) == 0
    ths = [m.angle(t / 4) for t in range(0, int(4 * m.T_OPEN) + 1)]
    assert all(b >= a for a, b in zip(ths, ths[1:]))
    assert m.T_OPEN < m.T_SHIP[0] and m.T_SHIP[1] < m.T_DOWN and m.gates_down(m.T_UP) and m.gates_down(m.T_DOWN + m.T_OPEN)


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.002


def test_cameras_clear_of_the_bridge_and_the_counterweight():
    """Section cameras stay on the open side of the cut; no camera is inside the counterweight, under the water or in a pit wall."""
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        x, y, z = tl.cam_world(sh)
        th = m.angle(sh["t"])
        if sh.get("section"):
            assert y < -0.5 or (32.0 < x < 48.0 and -9.6 < y < 9.6), f"frame {f} camera inside the cut street"
        else:
            assert z > -4.8 if abs(x) < 30 else z > 0.2, f"frame {f} camera under the water or the street"
        u = m.TRUNNION_X - x
        v = z - m.TRUNNION_Z
        uu = u * math.cos(-th) - v * math.sin(-th)
        vv = u * math.sin(-th) + v * math.cos(-th)
        (u0, u1), (v0, v1) = m.CW_BOX
        assert not (u0 - 0.3 < uu < u1 + 0.3 and v0 - 0.3 < vv < v1 + 0.3 and abs(y) < 8.3), f"frame {f} camera inside the counterweight"
