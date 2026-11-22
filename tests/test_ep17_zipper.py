import math

import numpy as np

from benchmarks.road_zipper import zipper_motion as m
from benchmarks.road_zipper import zipper_timeline as tl


def test_gate_passes():
    r = m.zipper_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert 1350 <= m.block_mass_kg() / m.LB <= 1650                      # "about fifteen hundred pounds"
    assert abs(m.SHIFT / m.FT - 12) < 1e-9                               # "twelve feet", one lane


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.1 and last["cam"]["rel"] == first["cam"]["rel"]


def test_no_camera_inside_a_car_a_block_or_the_machine():
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        t, v, c = sh["t"], sh["variant"], sh["cam"]
        ym = m.machine_y(t) if v != "morning" else 0.0
        lx, ly, lz = c["loc"]
        if c["rel"] == "machine":
            ly += m.machine_y(t)
        for x, y, _ in m.traffic(t, v):
            assert lz > 1.6 or not (abs(lx - x) < 1.0 and abs(ly - y) < 2.4), f"frame {f} camera in a car"
        b = m.blocks(t, v)
        d = np.hypot(b["x"] - lx, b["y"] - ly)
        assert lz > b["z"].max() + 0.9 or d.min() > 0.45, f"frame {f} camera in the wall"
        if v != "morning":
            for wx in m.MACHINE_WHEEL_X:
                for wy in (-6.6, -5.4, 5.4, 6.6):
                    assert math.dist((lx, ly, lz), (wx, ym + wy, 0.5)) > 0.8, f"frame {f} camera in a machine wheel"
