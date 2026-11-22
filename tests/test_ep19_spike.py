import math

from benchmarks.spike_strip import spike_motion as m
from benchmarks.spike_strip import spike_timeline as tl


def test_gate_passes():
    r = m.spike_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert 20 <= m.time_to_flat() <= 40                                   # "flat in about half a minute"
    assert m.V0 / m.MPH == 60                                             # "a blowout at sixty"
    assert m.time_to_flat() / m.BLOWOUT_TAU > 500                         # "instead of bursting"


def test_deflation_is_monotonic_and_choked_first():
    assert m.vent_speed(0.1, "front") > 300                               # sonic jet at the start
    ps = [m.gauge_after(t) for t in range(0, 60, 2)]
    assert all(a >= b for a, b in zip(ps, ps[1:]))


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] >= 0 and abs(last["t"] - first["t"]) < 0.002 and last["cam"]["rel"] == first["cam"]["rel"]


def test_no_camera_inside_the_car_or_under_the_road():
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        st = m.state(sh["pose_t"])
        x, y, z = sh["cam"]["loc"]
        if sh["cam"]["rel"] == "wheel":
            x, y, z = x + m.X_LANE + m.WHEEL_OFFSET[0], y + st["y"] + m.WHEEL_OFFSET[1], z + m.R
        elif sh["cam"]["rel"] == "car":
            x, y = x + st["x"], y + st["y"]
        assert z > 0.03, f"frame {f} camera under the road"
        assert not (abs(x - m.X_LANE) < 0.9 and st["y"] - 2.2 < y < st["y"] + 2.1 and z < 1.4), f"frame {f} camera in the car"
