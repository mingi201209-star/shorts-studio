import math

import numpy as np

from benchmarks.blade_lifter import blade_motion as m
from benchmarks.blade_lifter import blade_timeline as tl
from benchmarks.roller_barrier import roller_world as rw


def test_gate_passes():
    r = m.blade_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    assert abs(math.degrees(m.ALPHA_MAX) - 60) < 1e-9                       # "as steep as sixty degrees"
    assert abs(math.cos(m.ALPHA_MAX) - 0.5) < 1e-9                          # "sticks out only half as far"
    assert math.degrees(m.PSI_MAX) <= 20 + 1e-9                             # "swing the blade sideways" (the published 20 degrees)
    assert 0.85 * m.FOOTBALL_FT <= m.L_BLADE / m.FT < m.FOOTBALL_FT          # "almost as long as a football field"
    assert 11.5 <= m.V / m.MPH <= 13                                        # "about twelve miles an hour"
    assert 20 <= m.WIND_LIMIT / m.MPH <= 25                                 # "over twenty miles an hour"


def test_flat_hits_lifted_clears():
    flat = [m.clearance(m.s_of(t), "flat") for t in np.arange(0, 35, 1.0)]
    lift = [m.clearance(m.s_of(t), "lifted") for t in np.arange(0, 35, 1.0)]
    assert min(g for _, g in flat) < 0 and max(o for o, _ in flat) > 30
    assert min(g for _, g in lift) > 1.0


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.002 and first["cam"]["loc"] == last["cam"]["loc"]


def test_cameras_clear_of_the_land_the_trees_and_the_rig():
    segs = tl.segments()
    for f in range(0, tl.frame_count(), 3):
        sh = tl.frame_state(f, segs)
        x, y, z = tl.cam_world(sh)
        if sh.get("field"):                                                    # the comparison set: flat park, checked below
            assert z > 10.0
            continue
        d, _ = rw.signed_offset(np.array([[x, y]]))
        d = float(d[0])
        ground = float(rw.ground_z(np.array([d]), np.array([x]), np.array([y]))[0])
        assert z > ground + 1.0, f"frame {f} camera in the ground"
        if d > rw.TREE_CLEAR[0] or d < rw.TREE_CLEAR[1]:
            assert z > ground + 20.0, f"frame {f} camera among the trees"
        pts = tl.blade_points(sh, 60)
        assert np.min(np.linalg.norm(pts - np.array([x, y, z]), axis=1)) > 3.0, f"frame {f} camera in the blade"
        p, _ = m.at(tl.rig_s(sh))
        assert math.dist((x, y), (p[0], p[1])) > 4.0 or z > 8.0, f"frame {f} camera in the rig"


def test_football_field_comparison():
    assert abs(m.FIELD_PLAY - 300 * m.FT) < 1e-6 and 0 < m.FIELD_PLAY - m.L_BLADE < 10.0      # the tip ends about 7 yards short
    segs = tl.segments()
    g = [s for s in segs if s["label"].startswith("G-")][0]
    assert g["flags"].get("field") and sum(1 for s in segs if s["flags"].get("field")) == 1
    fx, fy = tl.FIELD
    for f in range(int(g["t0"] * tl.FPS) + 1, int(g["t1"] * tl.FPS)):
        x, y, z = tl.frame_state(f, segs)["cam"]["loc"]
        assert abs(x - fx) < 30 and y < fy - m.FIELD_LONG / 2 - 10 and z > 30, f"frame {f}: camera not behind the end zone"
