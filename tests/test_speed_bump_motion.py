import numpy as np
from benchmarks.speed_bump import speed_bump_motion as m


def test_short_bump_pushes_harder_than_long_at_same_height_and_speed():
    s = m.summary(m.simulate(m.BUMPS["short"]))
    h = m.summary(m.simulate(m.BUMPS["hump"]))
    assert s["peak_body_g"] > 2.0 * h["peak_body_g"]


def test_same_car_same_speed_same_height():
    assert m.BUMPS["short"]["height"] == m.BUMPS["hump"]["height"]
    r = m.simulate(m.BUMPS["hump"])
    assert abs(r["speed"] - 20 / 3.6) < 1e-9


def test_rest_before_and_settles_after():
    r = m.simulate(m.BUMPS["hump"])
    assert abs(r["body"][0]) < 1e-6
    assert abs(r["body"][-1]) < 0.01


def test_not_calibrated_flag():
    assert m.CLAIMS["physically_calibrated"] is False
