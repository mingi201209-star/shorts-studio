import math

from benchmarks.manhole_blast import manhole_motion as m
from benchmarks.manhole_blast import manhole_timeline as tl


def test_gate_passes():
    r = m.manhole_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert round(m.M_COVER / m.LB) == 300                                   # "a cast iron cover weighing up to three hundred pounds"
    assert m.concentration(m.T_IGNITE) > m.LFL                              # the gas can burn when the spark comes ("fills the vault")
    assert m.concentration(36000.0, vented=True) < 0.5 * m.LFL              # "gas escapes through the holes instead of building up"
    assert 3 * m.IN <= m.Z_LATCH <= 4 * m.IN                                # "they pop up a few inches"
    r = m._blast("latched")
    assert abs(r["z_max"] - m.Z_LATCH) < 1e-3 and r["t_back"] is not None


def test_cover_flight_lands_beside_the_hole_and_settles():
    tland = m.landing_time()
    dx, dy = m.drift(tland)
    assert math.hypot(dx, dy) > 2 * m.R_COVER
    assert m.apex() - m.T_COVER > 5.0
    assert abs(m.tumble(tland) - 2 * math.pi) < 1e-6                        # one turn over: it lands face up
    assert m.wobble(tland + 0.2)[0] > m.wobble(tland + 1.2)[0] > m.wobble(tland + 3.0)[0] == 0.0


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0 and abs(last["t"] - first["t"]) < 0.002 and last["variant"] == first["variant"]


def test_no_camera_inside_anything():
    """Street shots: the camera above the road, out of the buildings, the parked car and the fire. Cut-open shots: the camera on the
    open side of the cut, never inside the soil or the vault walls."""
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        x, y, z = tl.cam_world(sh)
        if sh.get("section"):
            assert x < m.MX - 0.05, f"frame {f} camera inside the cut ground"
            continue
        floor = 0.15 if abs(x) > 6.0 else 0.0
        assert z > floor + 0.2, f"frame {f} camera under the street"
        assert abs(x) < 9.6, f"frame {f} camera in a building"
        assert not (3.8 < x < 5.7 and 5.2 < y < 9.6 and z < 1.6), f"frame {f} camera in the parked car"
        if sh["variant"] in ("blast", "latched"):
            assert math.hypot(x - m.MX, y - m.MY) > 1.2, f"frame {f} camera in the fire"
