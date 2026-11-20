from benchmarks.hydroplaning import hydro_motion as m


def test_gate_passes():
    r = m.hydro_physics()
    assert r["status"] == "PASS", r["problems"]


def test_horne_rule_of_thumb():
    assert abs(m.horne_mph(32) - 50.9) < 0.1


def test_same_steering_until_the_puddle():
    for t in (0.2, 0.5, 0.8):
        assert abs(m.at("new", t)["steer"] - m.at("worn", t)["steer"]) < 1e-9


def test_grip_only_lost_in_water():
    assert m.grip_fraction("worn", 30.0, False) == 1.0
    assert m.grip_fraction("worn", 30.0, True) < 0.1
    assert m.grip_fraction("new", 25.0, True) > 0.7
