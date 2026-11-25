import math

import numpy as np

from benchmarks.car_tower import tower_motion as m
from benchmarks.car_tower import tower_timeline as tl


def test_gate_passes():
    r = m.tower_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    assert 6.0 <= m.V_LIFT / m.FT < 7.0                                     # "climbs almost seven feet a second"
    assert m.N_FLOORS * m.N_BAYS == 400 and m.N_FLOORS == 20                # "four hundred cars on twenty floors"
    assert m.worst_fetch() < 120 and m.fetch_time() < 120                   # "brings their car down in under two minutes"
    assert m.worst_fetch() <= m.RECORD_S                                    # within the published 1 min 44 s


def test_story():
    assert m.hero_car(-10)["where"] == "tunnel" and m.hero_car(5)["where"] == "fork"
    assert m.hero_car(60)["where"] == "bay" and m.hero_car(199)["where"] == "bay"
    assert m.hero_car(300)["where"] == "station"
    zs = [m.carriage(t)["z"] for t in np.arange(0.0, 23.0, 0.5)]
    assert all(b >= a - 1e-9 for a, b in zip(zs, zs[1:]))
    bay = m.hero_car(60)
    th = m.bay_angle(m.HERO_BAY)
    assert abs(bay["x"] - m.R_BAY * math.cos(th)) < 1e-9 and abs(bay["z"] - (m.floor_z(m.HERO_FLOOR) + m.RAIL_H)) < 1e-9


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert abs(last["t"] - first["t"]) < 0.002 and first["cam"]["loc"] == last["cam"]["loc"]


def test_cameras_clear_of_the_silos_the_cars_and_the_ground():
    segs = tl.segments()
    slot = m.bay_angle(m.SLOT_BAY)
    for f in range(0, tl.frame_count(), 2):
        sh = tl.frame_state(f, segs)
        x, y, z = tl.cam_world(sh)
        r = math.hypot(x, y)
        if z < -0.2:
            in_station = abs(x) < 7.6 and abs(y) < 7.6 and -3.9 < z < -0.5
            in_tunnel = abs(x) < 3.3 and y < -8.0 and -3.9 < z < -0.5
            assert in_station or in_tunnel, f"frame {f} camera in the ground"
        elif r < m.R_GLASS + 0.4:
            d_ang = abs((math.atan2(y, x) - slot + math.pi) % (2 * math.pi) - math.pi)
            assert d_ang < math.pi / m.N_BAYS * 0.8 and m.R_BAY - m.CAR_L / 2 + 0.2 < r < m.R_GLASS - 0.3, f"frame {f} camera inside the silo's stacks"
        else:
            assert z > 0.3, f"frame {f} camera at ground level"
        assert math.hypot(x - 30.0, y - 16.0) > m.R_GLASS + 0.5, f"frame {f} camera inside the twin silo"
        h = m.hero_car(sh["t"])
        assert math.dist((x, y, z), (h["x"], h["y"], h["z"] + 0.7)) > 1.6, f"frame {f} camera in the red car"
        c = m.carriage(sh["t"])
        if abs(z - c["z"]) < 1.2:
            assert r > 7.2, f"frame {f} camera in the carriage's sweep"
