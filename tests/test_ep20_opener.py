import math

from benchmarks.can_opener import opener_motion as m
from benchmarks.can_opener import opener_timeline as tl


def test_gate_passes():
    r = m.opener_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert round(m.CLEAR_OLD / m.FT, 3) == round(11 + 8 / 12, 3)                 # "only eleven foot eight"
    assert round((m.TRUCK_H - m.CLEAR_OLD) / m.IN) == 16                         # "thirteen feet, sixteen inches too tall"
    assert round(m.TRUCK_H / m.FT, 6) == 13.0
    assert round(m.RAISE / m.IN) == 8 and m.TRUCK_H > m.CLEAR_NEW                # "raised the bridge eight inches" / "still hit it"
    assert m.SKIN_T < m.DIME_T                                                   # "aluminum thinner than a dime"
    assert m.CAB_H < m.CLEAR_OLD                                                 # "the cab is lower"


def test_peel_follows_travel_and_stops():
    assert m.peel(-0.5) == 0 and m.peel(0.0) == 0
    ps = [m.peel(t / 100) for t in range(0, 200)]
    assert all(a <= b + 1e-12 for a, b in zip(ps, ps[1:]))
    assert 2.5 < m.peel(5.0) < m.BOX_L - 0.8
    assert m.rivets_popped(0.5) > m.rivets_popped(0.2) > 0
    assert m.speed(5.0) == 0 and m.braking(1.0) and not m.braking(0.2)


def test_warned_truck_stops_and_light_turns_red():
    assert m.signal(-0.1, "warned") == "green" and m.signal(2.0, "warned") == "red"
    assert m.warned_y(30.0) + m.CAB_FRONT < m.Y_STOP
    assert m.peel(3.0, "warned") == 0


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] >= 0 and abs(last["t"] - first["t"]) < 0.002 and last["variant"] == first["variant"]
    assert last["cam"]["rel"] == first["cam"]["rel"]


def _inside_box(p, lo, hi, margin=0.25):
    return all(lo[i] - margin < p[i] < hi[i] + margin for i in range(3))


def test_no_camera_inside_anything():
    """The camera is never inside the truck (with its roof scroll), the beam, its columns, the bridge, the abutments, the signal, a
    detector pole, a lamp post or a tree, never under the road and never inside a building."""
    segs = tl.segments()
    trees = [(-5.2, -73), (5.2, -66), (-5.2, -86), (5.2, -52), (5.2, -21.0), (-5.2, 20), (5.2, 27), (-5.2, 38), (5.2, 50)]
    poles = [(4.6, -14.6), (4.9, -28.0), (4.3, m.Y_SENSOR), (-4.3, m.Y_SENSOR), (-5.6, -56), (5.6, -38), (-5.6, -36), (5.6, 16), (-5.6, 30)]
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        p = tl.cam_world(sh)
        v = sh["variant"]
        assert p[2] > 0.2, f"frame {f} camera under the road"
        assert abs(p[0]) < 6.2, f"frame {f} camera inside a building or the embankment"
        clear = m.clearance(v, sh["t"]) if v != "warned" else m.CLEAR_OLD
        if v != "raising":
            yf = m.box_front_y(sh["t"], v)
            assert not _inside_box(p, (m.X_LANE - 1.25, yf - m.BOX_L - 0.1, 0.0), (m.X_LANE + 1.25, yf + m.CAB_FRONT, m.TRUCK_H + 1.6)), f"frame {f} camera in the truck"
        assert not _inside_box(p, (-6.4, -m.BEAM_T / 2, clear), (6.4, m.BEAM_T / 2, clear + m.BEAM_D)), f"frame {f} camera in the beam"
        for sx in (-1, 1):
            assert not _inside_box(p, (sx * 4.05 - 0.16, -0.16, 0.0), (sx * 4.05 + 0.16, 0.16, clear)), f"frame {f} camera in a column"
        assert not _inside_box(p, (-7.7, 0.5, clear + 0.1), (7.7, 4.7, clear + 2.2)), f"frame {f} camera in the bridge"
        assert not _inside_box(p, (1.2, -14.9, 3.9), (4.7, -14.3, 6.2)), f"frame {f} camera in the signal"
        for (x, y) in poles:
            assert math.hypot(p[0] - x, p[1] - y) > 0.5 or p[2] > 7.8, f"frame {f} camera in a pole"
        for (x, y) in trees:
            assert math.hypot(p[0] - x, p[1] - y) > 2.6 or p[2] > 7.5, f"frame {f} camera in a tree"
