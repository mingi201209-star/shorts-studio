import numpy as np

from benchmarks.cable_barrier import cable_motion as m
from benchmarks.cable_barrier import cable_timeline as tl


def test_gate_passes():
    r = m.cable_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert len(m.ROPE_Z) == 3                                    # "three steel ropes"
    assert abs(m._peak()[1] / m.FT - 8) < 0.8                    # "about eight feet"
    assert m.V0 / m.MPH == 60


def test_ropes_follow_the_car_and_spring_back():
    t, d, _ = m._peak()
    assert m.rope_offset(np.array([m.state(t)["kink_y"]]), t)[0] > 0.9 * d
    assert m.rope_offset(np.array([0.0]), 4.0).max() < 0.05


def test_oncoming_car_is_on_the_far_side():
    assert m.ONCOMING_X > 6 and m.state(-3.0)["cx"] < -6


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0 and m.state(first["t"])["depth"] > 0.5        # frame 1 is the catch
    assert abs(last["t"] - first["t"]) < 0.04 and last["cam"]["rel"] == first["cam"]["rel"]


def test_no_camera_inside_a_car():
    """EP.15 storyboard: shot H's camera sat in the car's path and went black. Check every frame against both cars' footprints."""
    import math
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        st, c = m.state(sh["t"]), sh["cam"]
        cx, cy, psi = -st["cx"], st["cy"], st["psi"]
        lx, ly, lz = c["loc"]
        if c["rel"] == "car":
            lx, ly = lx + cx, ly + cy
        dx, dy = lx - cx, ly - cy
        fwd, side = dy * math.cos(psi) - dx * math.sin(psi), dx * math.cos(psi) + dy * math.sin(psi)
        assert lz > 1.8 or not (-m.TAIL - 0.4 < fwd < m.NOSE + 0.4 and abs(side) < m.HALF_W + 0.4), f"frame {f} camera in the car"
        assert lz > 1.8 or not (abs(lx + m.ONCOMING_X) < 1.3 and abs(ly - m.oncoming_y(sh["t"])) < 2.5), f"frame {f} camera in the oncoming car"
