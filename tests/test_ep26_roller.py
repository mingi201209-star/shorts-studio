import math

import numpy as np

from benchmarks.roller_barrier import roller_motion as m
from benchmarks.roller_barrier import roller_timeline as tl
from benchmarks.roller_barrier import roller_world as w


def test_gate_passes():
    r = m.roller_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    ro, st = m.crash("roller"), m.crash("steel")
    assert abs(m.V0 / m.MPH - 62.1) < 0.1                                   # "a sixty-two mile an hour crash test"
    assert st["e_fric"] > 5 * ro["e_fric"]                                  # "they spin instead of scraping" (the steel rail scrapes)
    assert ro["e_foam"] > 0 and ro["max_defl"] > m.SQ_MAX                   # "the foam squashes to soak up the hit"
    sideways = 0.5 * m.M_CAR * (m.V0 * math.sin(m.ANGLE0)) ** 2
    assert ro["e_spin"] > 0.15 * sideways                                   # "turns part of the crash into rotation"
    assert ro["exit_speed"] / m.V0 > 0.8 and ro["exit_speed"] > st["exit_speed"]   # "the car keeps rolling forward"
    assert ro["exit_angle_deg"] < 0                                         # "steered back toward its lane"
    assert len(ro["spun"]) >= 8


def test_rollers_spin_squash_and_spring_back():
    ks = sorted(m.crash("roller")["spun"])
    k = ks[len(ks) // 2]
    t0 = m.crash("roller")["spun"][k][0]
    spins = [m.roller_spin(k, t0 + x) for x in np.linspace(0, 3, 30)]
    assert spins[0] == 0 and all(b >= a for a, b in zip(spins, spins[1:])) and spins[-1] > 20
    ys = (np.arange(-6, 22) + 0.5) * m.ROLL_PITCH
    worst = max(m.barrier_state(t, ys)[0].max() for t in np.linspace(0.01, 0.3, 15))
    assert abs(worst - m.SQ_MAX) < 1e-9
    sq, gv = m.barrier_state(2.5, ys)
    assert sq.max() < 0.002 and gv.max() < 0.01                             # foam and posts back in shape
    assert len(m.spark_points(0.15)) > 30 and not m.spark_points(-0.1)


def test_world_layout():
    assert w.lane_check()["status"] == "PASS"
    ax, hs, s = w.barrier_axis()
    i = int(np.argmin(np.abs(s)))
    assert abs(ax[i, 0] - w.AXIS_OFF) < 1e-6 and abs(ax[i, 1] - s[i]) < 1e-6     # s = y on the hero straight
    p, h, ks = w.roller_stations(-2, 10)
    assert np.allclose(p[2:, 0], w.AXIS_OFF) and np.allclose(p[:, 1], (ks + 0.5) * m.ROLL_PITCH, atol=0.02)


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.002 and first["cam"]["loc"] == last["cam"]["loc"]


def test_cameras_clear_of_the_car_the_barrier_the_trees_and_the_ground():
    segs = tl.segments()
    for f in range(0, tl.frame_count(), 2):
        sh = tl.frame_state(f, segs)
        x, y, z = tl.cam_world(sh)
        d, _ = w.signed_offset(np.array([[x, y]]))
        d = float(d[0])
        ground = float(w.ground_z(np.array([d]), np.array([x]), np.array([y]))[0])
        if w.TREE_CLEAR[0] < d or d < w.TREE_CLEAR[1]:
            assert z > ground + 18.0, f"frame {f} camera among the trees (d={d:.1f}, z={z:.1f})"
        elif 3.8 < d < 6.0:
            assert z > 1.3, f"frame {f} camera in the barrier"
        else:
            assert z > max(0.4, ground + 0.4), f"frame {f} camera in the ground"
        p = tl.car_pose(sh)
        if p["visible"]:
            c, s = math.cos(p["psi"]), math.sin(p["psi"])
            dx, dy = x - p["x"], y - p["y"]
            right, fwd = c * dx - s * dy, s * dx + c * dy
            inside = abs(right) < m.CAR_HALF_W + 0.3 and -m.CAR_REAR - 0.3 < fwd < m.CAR_FRONT + 0.3 and z < 1.26 + 0.3
            assert not inside, f"frame {f} camera inside the car"
