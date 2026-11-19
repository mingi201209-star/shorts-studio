import math

from benchmarks.abs_brake import abs_motion as m


def test_gate_passes():
    r = m.abs_physics()
    assert r["status"] == "PASS", r["problems"]


def test_locked_wheels_stop_but_car_moves():
    s = m.at("locked", 0.6)
    assert s["wheel_omega"] == 0.0 and s["speed"] > 5


def test_locked_car_goes_straight_with_wheel_turned():
    s = m.at("locked", 1.0)
    assert s["x"] == 0.0 and s["heading"] == 0.0 and abs(s["steer"]) > 0


def test_same_steering_in_both_cars():
    for t in (0.3, 0.8, 1.4):
        assert m.at("abs", t)["steer"] == m.at("locked", t)["steer"]


def test_abs_wheels_keep_rolling_and_pressure_pulses():
    s = [m.at("abs", 0.5 + i * 0.01) for i in range(30)]
    assert all(x["wheel_omega"] > 0 for x in s)
    assert max(x["pressure"] for x in s) - min(x["pressure"] for x in s) > 0.4


def test_box_only_moves_after_locked_hit():
    _, hit = m._run("locked")
    assert not m.box_pose("locked", hit["t"] - 0.01)["hit"]
    assert m.box_pose("locked", hit["t"] + 0.2)["y"] > m.BOX_Y + m.BOX_HALF[1]
    assert not m.box_pose("abs", 3.0)["hit"]


def test_lane_change_stays_inside_friction():
    for i in range(300):
        s = m.at("abs", i / 100)
        ay = s["speed"] ** 2 * abs(math.tan(s["steer"])) / m.WHEELBASE
        assert ay <= m.MU_PEAK * m.G
