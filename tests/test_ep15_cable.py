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
