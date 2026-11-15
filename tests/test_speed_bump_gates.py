import numpy as np
from benchmarks.speed_bump import preview_gates as g


def img(car_h, bump_w, top=40):
    a = np.zeros((100, 100, 3), np.uint8)
    a[:] = (60, 60, 70)
    a[top:top + car_h, 20:60] = (30, 80, 200)
    a[90:92, 10:10 + bump_w] = (230, 170, 20)
    return a


def test_passes_when_cars_big_and_motion_visible_and_bumps_differ():
    first = {"hump": img(40, 70), "short": img(40, 20)}
    series = {"hump": [img(40, 70, top=36)], "short": [img(40, 20, top=37)]}
    assert g.evaluate(first, series)["objective_pass"]


def test_fails_when_cars_tiny():
    first = {"hump": img(8, 70), "short": img(8, 20)}
    series = {"hump": [img(8, 70, top=30)], "short": [img(8, 20, top=30)]}
    r = g.evaluate(first, series)
    assert not r["checks"]["cars_fill_picture"] and not r["objective_pass"]


def test_fails_without_motion():
    first = {"hump": img(40, 70), "short": img(40, 20)}
    series = {"hump": [img(40, 70)], "short": [img(40, 20)]}
    assert not g.evaluate(first, series)["checks"]["body_motion_visible"]


def test_editorial_items_stay_unverified():
    assert all(v.startswith("UNVERIFIED") for k, v in g.FIRST_THREE_SECONDS.items() if not k.startswith("objective"))
