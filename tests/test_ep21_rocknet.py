import math

import numpy as np

from benchmarks.rock_net import rocknet_motion as m
from benchmarks.rock_net import rocknet_timeline as tl


def test_gate_passes():
    r = m.rocknet_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert m.M == 20000 and round(m.V0 / m.MPH) == 60                       # "a twenty-ton boulder", "twenty tons at sixty miles an hour"
    assert 0.5 * m.M * m.V0 ** 2 / 1e3 <= m.RATED_KJ                        # "the biggest nets"
    assert m.w_max() > 20 * m.FT                                            # "more than twenty feet"
    assert m.loop_radius(10.0) < m.LOOP_R0 - 0.15                           # "these steel loops shrink"


def test_catch_is_monotonic_then_rests():
    ws = [m.deflection(t / 200) for t in range(0, int(m.stop_time() * 200))]
    assert all(a <= b + 1e-9 for a, b in zip(ws, ws[1:]))
    assert m.rock_speed(m.stop_time() + 0.1) == 0
    assert m.brake_slip(5.0) == m.brake_slip(m.stop_time())                 # brakes never run back
    assert m.brake_power(-0.1) == 0 and m.brake_power(0.3) > 0


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0.1 and abs(last["t"] - first["t"]) < 0.002 and last["variant"] == first["variant"]


def _net_x(y, h, w):
    """Downhill reach of the net surface at net coordinates (y, h) (same bulge as the renderer, without the rock pocket)."""
    dy, dh = y - m.HIT_Y, h - m.HIT_H
    d = w * math.exp(-(dy / 3.6) ** 2) * math.exp(-(dh / 3.0) ** 2)
    return m.X_B - d * math.cos(m.SLOPE)


def test_no_camera_inside_anything():
    """The camera is never under the slope or the valley side, inside the net, the boulder or a post."""
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        x, y, z = sh["cam"]["loc"]
        if x > m.X_TOE:
            assert z > m.slope_z(x) + 0.8, f"frame {f} camera under the slope"
        elif x < -4.4:
            assert z > 0.72 * (x + 4.4) + 1.0, f"frame {f} camera under the valley side"
        else:
            assert z > 0.4, f"frame {f} camera under the road"
        t = sh["t"] if sh["variant"] == "catch" else 30.0
        w = m.deflection(t) if sh["variant"] == "catch" else 0.0
        if -15.3 < y < 15.3 and m.Z_B - 0.5 < z < m.Z_B + m.H_NET + 0.5:
            nx = _net_x(y, z - m.Z_B, w)
            assert not (nx - 0.6 < x < m.X_B + 0.6), f"frame {f} camera in the net"
        c = m.rock_center(t)
        assert np.linalg.norm(np.array([x, y, z]) - c) > m.R_ROCK + 0.8, f"frame {f} camera in the rock"
        for yp in m.POST_YS:
            assert math.hypot(x - m.X_B, y - yp) > 0.6 or z > m.Z_B + m.H_NET + 0.6, f"frame {f} camera in a post"
