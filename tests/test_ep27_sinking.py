import numpy as np

from benchmarks.submersible_bridge import sinking_motion as m
from benchmarks.submersible_bridge import sinking_timeline as tl
from benchmarks.submersible_bridge import sinking_world as w


def test_gate_passes():
    r = m.sinking_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    assert 24 <= -m.Z_DOWN / m.FT <= 28                                     # "sinks about twenty-six feet underwater"
    assert 12 <= m.V_SINK * 60 / m.FT <= 14                                 # "about thirteen feet a minute"
    assert 0 < m.Z_DOWN - m.CANAL_BED <= 1.0                                # "settles almost on the bottom of the canal"
    over = [t for t in np.arange(150, 220, 0.5) if m.ship_over_deck(t)]
    assert over and min(-m.SHIP_DRAFT - m.deck_z(t) for t in over) > 1.0  # "ships sail right over the top of the drowned road"
    assert m.MAST_H + m.LIFT_CLEAR + m.LIFT_MACHINERY > m.MAST_H            # "a lift bridge would need towers taller than the masts"
    assert m.wet(m.t_out() + 3) > 0.9                                       # "rises again dripping wet"


def test_story_clock():
    zs = [m.deck_z(t) for t in np.arange(-10, m.T_UP0 + m.move_time() + 20, 1.0)]
    assert max(zs) == m.Z_UP and min(zs) == m.Z_DOWN
    down = [m.deck_z(t) for t in np.arange(0, m.move_time(), 0.5)]
    assert all(b <= a + 1e-12 for a, b in zip(down, down[1:]))
    assert m.gates_down(-30) == 1.0 and m.gates_down(-50) == 0.0 and m.gates_down(m.t_gates_open() + 10) == 0.0
    assert not m.ship_over_deck(m.T_DOWN0 + m.move_time()) and not m.ship_over_deck(m.T_UP0)


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.002 and first["cam"]["loc"] == last["cam"]["loc"]


def test_cameras_clear_of_the_land_the_water_line_the_deck_and_the_ship():
    segs = tl.segments()
    for f in range(0, tl.frame_count(), 2):
        sh = tl.frame_state(f, segs)
        x, y, z = sh["cam"]["loc"]
        ground = float(w.ground_z(np.array([x]), np.array([y]))[0])
        assert z > ground + 0.5, f"frame {f} camera in the ground"
        if sh.get("under"):
            assert z < -0.3, f"frame {f} under-water shot with the camera at the surface"
        else:
            assert z > 0.3, f"frame {f} camera at or under the water"
        lo, hi = tl.deck_box(sh["t"])
        assert not (lo[0] - 0.3 < x < hi[0] + 0.3 and lo[1] - 0.3 < y < hi[1] + 0.3 and lo[2] - 0.3 < z < hi[2] + 0.3), f"frame {f} camera in the deck"
        bow = m.ship_bow_y(sh["t"])
        assert not (abs(x) < m.SHIP_BEAM / 2 + 0.5 and bow - m.SHIP_L - 0.5 < y < bow + 0.5 and -m.SHIP_DRAFT - 0.5 < z < 3.0), f"frame {f} camera in the ship"
