import math

from benchmarks.wedge_barrier import wedge_motion as m
from benchmarks.wedge_barrier import wedge_timeline as tl


def test_gate_passes():
    r = m.wedge_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert abs(m.plate_front(10.0)[1] / m.FT - 3.0) < 0.25            # "nearly three feet high"
    assert 0.8 <= m.RISE_TIME <= 1.5                                  # "rises in about a second"
    assert abs(m.TRUCK_MASS / m.LB - 15000) < 1 and m.V0 / m.MPH == 50   # "a fifteen thousand pound truck going fifty"


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0 and m.car_state(first["t"])["crush"] > 0.3        # frame 1 is the car already crushing into the face
    assert abs(last["t"] - first["t"]) < 0.01 and last["cam"]["rel"] == first["cam"]["rel"]


STATIC = [  # (centre, size) boxes the camera must stay out of (EP.18 storyboard: a camera inside the booth island went black)
    ((-5.6, 7.0, 0.08), (2.6, 6.0, 0.16)), ((-5.6, 7.0, 1.4), (2.0, 2.6, 2.5)), ((0.0, 0.0, 0.06), (0.3, 1000.0, 0.14)),
]


def test_no_camera_inside_anything():
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        x, y, z = sh["cam"]["loc"]
        for (cx, cy, cz), (sx, sy, sz) in STATIC:
            assert not (abs(x - cx) < sx / 2 + 0.1 and abs(y - cy) < sy / 2 + 0.1 and abs(z - cz) < sz / 2 + 0.1), f"frame {f} camera in a box"
        for bx in [-12.5 + 1.4 * k for k in range(4)] + [7.5 + 1.4 * k for k in range(4)]:
            assert math.hypot(x - bx, y + 0.7) > 0.4 or z > 1.1, f"frame {f} camera in a bollard"
        if not sh.get("cut"):
            assert z > 0.1, f"frame {f} camera under the ground"
        st = m.car_state(sh["t"]) if sh["variant"] == "car" else m.truck_state(sh["t"])
        lane = m.LANE_A if sh["variant"] == "car" else m.LANE_B
        half, front, back = (0.95, m.NOSE, m.TAIL) if sh["variant"] == "car" else (1.35, m.TRUCK_NOSE, m.TRUCK_TAIL)
        assert not (abs(x - lane) < half and st["y"] - back - 0.3 < y < st["y"] + front + 0.3 and z < 4.0), f"frame {f} camera in the vehicle"
