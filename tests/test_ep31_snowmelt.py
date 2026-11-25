import numpy as np

from benchmarks.snowmelt_road import snowmelt_motion as m
from benchmarks.snowmelt_road import snowmelt_timeline as tl
from benchmarks.snowmelt_road import snowmelt_world as w


def test_gate_passes():
    r = m.snowmelt_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    assert 45 <= m.T_WATER * 9 / 5 + 32 <= 58                               # "around fifty degrees"
    assert m.melt_capacity_cm_h() >= m.SNOW_RATE_CM_H                        # "the snow melts as soon as it lands"
    assert m.film_margin(m.T_AIR_NAGAOKA) > 0 > m.film_margin(m.T_AIR_COLD)  # "near freezing so the water doesn't turn to ice"
    assert m.water_per_km_m3_h() > 100                                       # "it uses lots of water"
    assert m.PIPE_FLUX >= m.snow_load_w()                                    # "keep the warm water in pipes under the pavement"


def test_jets_stay_on_the_road_and_above_it():
    assert w.jet_reach() < w.WET_HALF < w.ROAD_HALF
    for t in np.linspace(0.0, 3.0, 13):
        p, v, u = w.droplets(float(t), -1e9, 1e9)
        assert len(p) == len(w.NOZZLE_Y) * 6 * w.DROPS
        assert p[:, 2].min() > -0.01 and p[:, 2].max() < 0.6 and np.abs(p[:, 0]).max() < w.WET_HALF
        half = w.droplets(float(t), -1e9, 1e9, (-1.0,))[0]
        assert len(half) * 2 == len(p) and half[:, 0].max() < 0.12


def test_snow_and_car():
    for t in (0.0, 41.0, 100.0):
        pos, size, near, rip = w.flakes(t, (0.0, 0.0, 1.5), (0.0, 30.0, 10.0), 0.0, (0.0, 0.5, 0.3))
        assert (pos[:, 2] >= w.surface_z(pos[:, 0]) - 1e-9).all() and len(pos) > 3000
        assert (np.abs(rip[:, 0]) < w.WET_HALF).all() and (rip[:, 2] < 0.45).all()
    assert w.car_y(w.CAR_T_REF) == w.CAR_Y_REF and w.LANE_X > 0                 # heading -y it keeps left (+x)
    assert w.car_y(w.CAR_T_REF + 1.0) < w.car_y(w.CAR_T_REF)


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.5 and first["cam"]["loc"] == last["cam"]["loc"]
    h2 = [s for s in segs if s["flags"].get("sink")][0]
    f0, f1 = int(np.ceil(h2["t0"] * tl.FPS)), int(np.ceil(h2["t1"] * tl.FPS)) - 1
    assert tl.frame_state(f0, segs)["sink"] < 0.05 and tl.frame_state(f1, segs)["sink"] > 0.95


def test_cameras_in_the_open():
    segs = tl.segments()
    for f in range(0, tl.frame_count(), 2):
        sh = tl.frame_state(f, segs)
        x, y, z = sh["cam"]["loc"]
        if sh.get("section"):
            assert 0.5 < x < 23.0, f"frame {f}: section camera outside the cut"
            continue
        assert z > 0.12, f"frame {f}: camera in the road"
        assert abs(x) < w.FRONT - 0.4 or z > 14.0, f"frame {f}: camera in the houses"
        if w.ROAD_HALF - 0.2 < abs(x) < w.ROAD_HALF + 1.2:
            assert z > 0.9, f"frame {f}: camera in a snowbank"
        if abs(x) > w.ROAD_HALF + w.GUTTER and z < 3.2:
            raise AssertionError(f"frame {f}: camera under the covered sidewalk")
        cy = w.car_y(sh["t"])
        if cy is not None:
            assert not (abs(x - w.LANE_X) < 1.2 and abs(y - cy) < 2.6 and z < 1.6), f"frame {f}: camera in the car"
