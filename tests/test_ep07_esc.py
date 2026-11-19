import math

from benchmarks.esc_stability import esc_motion as m


def test_gate_passes():
    r = m.esc_physics()
    assert r["status"] == "PASS", r["problems"]


def test_without_esc_the_car_spins_and_with_esc_it_does_not():
    assert max(abs(m.at("off", i / 20)["heading"]) for i in range(90)) > math.radians(100)
    assert max(abs(m.at("esc", i / 20)["heading"]) for i in range(90)) < math.radians(25)


def test_esc_brakes_the_outside_front_wheel():
    for i in range(90):
        s = m.at("esc", i / 20)
        if s["esc_force"] > 300:
            assert s["esc_side"] * s["yaw_rate"] > 0      # turning left (r > 0) -> right wheel (+1) braked


def test_same_steering_in_both_cars():
    for t in (0.3, 0.8, 1.4, 2.0):
        assert m.at("esc", t)["steer"] == m.at("off", t)["steer"]


def test_both_cars_clear_the_box():
    for v in ("esc", "off"):
        for i in range(90):
            s = m.at(v, i / 20)
            if abs(s["y"] + m.CAR_NOSE - m.BOX_Y) < 1.0:
                assert abs(s["x"]) > m.CAR_HALF_W + m.BOX_HALF[0]
