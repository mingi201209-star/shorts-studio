import math

from benchmarks.runway_emas import emas_motion as m
from benchmarks.runway_emas import emas_timeline as tl


def test_gate_passes():
    r = m.emas_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert round(m.V0 / m.MPH) == 81 and round(m.V0 / m.KT) == 70           # "rolling in at eighty miles an hour" (70 knots)
    assert m.stop_distance() < m.BED_L                                      # it stops inside the bed
    assert m.SINK > 0.5                                                     # "the tires sink in"


def test_run_slows_monotonically_and_stops():
    vs = [m.speed(t / 20) for t in range(-60, 200)]
    assert all(a >= b - 1e-9 for a, b in zip(vs, vs[1:]))
    assert m.speed(m.stop_time() + 0.1) == 0
    assert m.bed_depth(m.Y_BED - 1) == 0 and m.bed_depth(m.Y_BED + 60) == m.DEPTH1


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0 and abs(last["t"] - first["t"]) < 0.002 and last["variant"] == first["variant"]


def test_no_camera_inside_anything():
    """The camera is never under the ground or the bed, inside the fuselage, a wing, an engine or a landing gear."""
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        x, y, z = tl.cam_world(sh)
        floor = m.bed_depth(y) if abs(x) < m.BED_W / 2 else 0.0
        assert z > floor + 0.25, f"frame {f} camera under the ground or the bed"
        yp = tl.plane_y(sh)
        ly = y - yp                                                          # in the jet's frame
        assert not (abs(x) < 2.3 and -21.0 < ly < 19.2 and 0.9 < z < 5.6), f"frame {f} camera in the fuselage"
        if 1.4 < abs(x) < 17.6:
            le = 4.6 - (abs(x) - 1.6) * math.tan(math.radians(25))
            wz = 2.05 + (abs(x) - 1.6) / 15.6 * 1.6
            assert not (le - 7.6 < ly < le + 0.4 and wz - 0.6 < z < wz + 0.8), f"frame {f} camera in a wing"
        for sx in (-1, 1):
            assert not (math.hypot(x - sx * 5.0, z - 1.62) < 1.3 and 3.5 < ly < 8.3), f"frame {f} camera in an engine"
            assert not (abs(x - sx * m.MAIN_X) < 1.0 and -0.9 < ly < 0.9 and z < 2.2), f"frame {f} camera in a main gear"
        assert not (abs(x) < 0.6 and m.WHEELBASE - 0.6 < ly < m.WHEELBASE + 0.6 and z < 1.6), f"frame {f} camera in the nose gear"
