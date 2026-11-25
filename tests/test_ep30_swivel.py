import math

import numpy as np

from benchmarks.swivel_bridge import swivel_motion as m
from benchmarks.swivel_bridge import swivel_timeline as tl


def test_gate_passes():
    r = m.swivel_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    assert m.MASS_T == 46000                                                 # "forty-six thousand tons"
    assert 850 <= m.LENGTH / m.FT < 900                                      # "almost nine hundred feet long"
    assert abs(math.degrees(m.turned(m.T_TURN + 1)) - 52.4) < 1e-9 and m.T_TURN == 68 * 60   # "fifty-two degrees in sixty-eight minutes"
    rate = 52.4 / 68.0
    assert 7 <= 6.0 / rate <= 9                                              # "about eight times slower than a clock's minute hand"
    assert m.WINDOW[1] - m.WINDOW[0] < 120 * 60 and m.WINDOW[0] < 0 < m.T_TURN < m.WINDOW[1]   # "a window of under two hours"


def test_turn_is_smooth_and_complete():
    a = [m.turned(t) for t in np.arange(-10, m.T_TURN + 10, 5.0)]
    assert all(b >= x - 1e-12 for x, b in zip(a, a[1:]))
    assert not m.over_tracks(-1) and m.over_tracks(m.T_TURN + 1) and m.clearance_over_wires() > 1.0


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.5 and first["cam"]["loc"] == last["cam"]["loc"]


def test_cameras_clear_of_the_bridge_the_trains_and_the_ground():
    segs = tl.segments()
    for f in range(0, tl.frame_count(), 3):
        sh = tl.frame_state(f, segs)
        x, y, z = sh["cam"]["loc"]
        assert z > 1.2, f"frame {f} camera at the ground"
        h = m.heading(sh["t"])
        u = np.array([math.sin(h), math.cos(h)])
        rel = np.array([x, y]) - np.array(m.PIER)
        along = float(rel @ u)
        across = abs(float(rel @ np.array([math.cos(h), -math.sin(h)])))
        inside_deck = abs(along) < m.HALF + 1 and across < m.DECK_W / 2 + 1 and m.deck_bottom_z(min(abs(along), m.HALF)) - 1 < z < m.DECK_TOP + 2
        assert not inside_deck, f"frame {f} camera in the deck"
        assert math.dist((x, y), m.PIER) > 9.0 or z > m.DECK_TOP + 2, f"frame {f} camera in the pier or the swivel"
        for k in range(2):
            tx = tl.train_x(k, sh["t"])
            if tx is not None:
                ty = tl.TRACK_OF[k]
                assert not (tx - 8 * 25.6 - 1 < x < tx + 1 and abs(y - ty) < 2.5 and z < 5.0), f"frame {f} camera in a train"
