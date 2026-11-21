import math

from benchmarks.tire_blowout import blowout_motion as m
from benchmarks.tire_blowout import blowout_timeline as tl


def test_gate_passes():
    r = m.blowout_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert 14.5 <= m.revs_per_second(60 * m.MPH) <= 15.5                 # "fifteen times every second" at sixty
    assert m.LEAK_PSI_PER_MONTH == 1.0                                  # "about a pound of air every month"
    assert m.deflection(m.P_LOW) > m.deflection(m.P_SPEC)               # the low tyre bends more
    assert m.temp_eq(m.P_LOW) > m.temp_eq(m.P_SPEC) + 15               # "all that bending turns into heat"
    assert m.bond_life_hours(m.P_LOW) < m.bond_life_hours(m.P_SPEC) / 10    # "the heat slowly cooks the glue"


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0 and m.airborne_count(first["t"]) >= 25          # frame 1 is the burst with rubber in the air
    assert abs(last["t"] - first["t"]) < 0.15 and last["cam"]["rel"] == first["cam"]["rel"]


def test_no_camera_inside_the_car_or_a_piece():
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        if sh["variant"] == "parked":
            continue
        st = m.state(sh["pose_t"])
        c = sh["cam"]
        lx, ly, lz = c["loc"]
        if c["rel"] == "car":
            lx, ly = lx + st["x"], ly + st["y"] - sh["y_shift"]
        elif c["rel"] == "wheel":
            w = m.wheel_world(sh["pose_t"])
            lx, ly, lz = lx + w[0], ly + w[1] - sh["y_shift"], lz + w[2]
        dx, dy = lx - st["x"], ly - (st["y"] - sh["y_shift"])
        psi = st["psi"]
        fwd, side = dy * math.cos(psi) - dx * math.sin(psi), dx * math.cos(psi) + dy * math.sin(psi)
        assert lz > 1.6 or not (-2.2 < fwd < 2.1 and abs(side) < 0.95), f"frame {f} camera in the car"
        if sh["t"] >= 0:
            for k in range(m.N_DEBRIS):
                p = m.debris_pose(k, sh["t"])
                if p is not None:
                    assert sum((a - b) ** 2 for a, b in zip(p[0], (lx, ly + sh["y_shift"], lz))) > 0.25 ** 2, f"frame {f} camera inside piece {k}"
