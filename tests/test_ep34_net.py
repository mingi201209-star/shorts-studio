"""EP.34 runaway-truck arrester nets: the model behind every claim in the narration, the net geometry the renderer draws, the
timeline rules and the sound's timing."""
import math

import numpy as np

from benchmarks.truck_net import net_motion as m
from benchmarks.truck_net import net_sfx as sx
from benchmarks.truck_net import net_timeline as tl


def test_gate_passes():
    r = m.net_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    r = m.net_physics()
    assert m.N_NETS == 8                                              # TxDOT El Paso and WYDOT Teton Pass: eight net stations
    assert r["nets_used"] >= 3                                        # "net after net"
    assert r["peak_g"] <= 1.5                                         # "gentle enough to protect the driver"
    assert r["rating_lb"] == 90000 and r["rating_mph"] == 90          # "a ninety-thousand-pound truck at ninety miles an hour"
    assert r["rating_nets_used"] == m.N_NETS and r["rating_stop_ft"] * m.FT < m.RAMP_END
    assert r["rating_tape_out_max_ft"] * m.FT < m.L_TAPE              # no tape runs out


def test_net_force_is_the_work_of_the_tapes():
    d = np.linspace(0.0, 60.0, 60001)
    f = np.array([m.net_force(x) for x in d])
    work = float(np.sum(0.5 * (f[1:] + f[:-1]) * np.diff(d)))
    assert math.isclose(work, m.TAPES_PER_NET * m.T_TAPE * m.payout(60.0), rel_tol=1e-4)
    assert m.net_force(0.0) == 0.0 and np.all(np.diff(f) >= -1e-9)    # builds up from nothing, never drops while the tapes pay out


def test_truck_only_slows_and_stops():
    rows = m.catch()
    v = np.array([r[2] for r in rows])
    x = np.array([r[1] for r in rows])
    assert v[0] == m.V0_MPH * m.MPH and v[-1] == 0.0
    assert np.all(np.diff(v) <= 1e-12) and np.all(np.diff(x) >= -1e-12)
    st = m.truck_state(-1.0)
    assert math.isclose(st["front_y"], -m.V0_MPH * m.MPH) and st["engaged"] == 0


def test_side_edge_keeps_the_net_length():
    for d in (0.5, 3.0, 12.0, 40.0):
        for s in (-1, 1):
            ex, ey = m.side_edge(d, 15.0, s)
            corner = (s * m.HALF_T, 15.0 + d)
            assert math.isclose(math.dist((ex, ey), corner), m.S_SIDE, rel_tol=1e-9)
            assert math.isclose(math.dist((ex, ey), (s * m.WALL_X, 15.0)), m.payout(d), rel_tol=1e-9, abs_tol=1e-12)
    assert m.side_edge(0.0, 30.0, 1) == (m.WALL_X, 30.0)


def test_truck_path_leaves_the_highway_into_the_ramp():
    assert m.path_x(-400.0) == m.ROAD_LANE and m.path_x(-60.0) == 0.0 and m.path_x(50.0) == 0.0
    hs = [m.heading(y) for y in np.linspace(-200, 0, 400)]
    assert max(abs(a - b) for a, b in zip(hs, hs[1:])) < 0.01


def test_timeline_rules():
    segs = tl.segments()
    assert tl.pace(segs)["status"] == "PASS", tl.pace(segs)["problems"]
    assert tl.scene_alignment(segs)["status"] == "PASS"
    labels = [s["label"] for s in segs]
    assert math.isclose(segs[labels.index("E2-pins")]["t0"], tl.word_start(5, "is"))      # "...the tape | is dragged through pins"
    assert math.isclose(segs[labels.index("J-loop")]["t0"], tl.word_start(9, "and"))
    reveals = [s for s in segs if s["flags"].get("reveal")]
    assert len(reveals) == 1 and reveals[0]["flags"].get("cut")
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert last["segment"] == "J-loop" and 0 < last["t"] <= first["t"]
    assert np.allclose(last["cam"]["loc"], first["cam"]["loc"]) and np.allclose(last["cam"]["target"], first["cam"]["target"])


def test_each_net_snaps_on_when_the_front_reaches_it():
    for rating in (False, True):
        te = sx.engage_times(rating)
        assert te[0] == 0.0 and all(b > a for a, b in zip(te, te[1:]) if b is not None)
        for t, y in zip(te, m.NET_Y):
            if t is not None:
                assert abs(m.truck_state(t, rating)["front_y"] - y) < 0.05
