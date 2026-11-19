"""EP.05 belt model: the modern belt (pretensioner + load limiter) against a plain belt in the same crash."""
import numpy as np
import pytest

from benchmarks.belt_limiter import belt_motion as bm


@pytest.fixture(autouse=True)
def _fresh_cache():
    bm.response.cache_clear()
    yield
    bm.response.cache_clear()


def test_gate_passes_for_the_chosen_numbers():
    g = bm.belt_limiter_physics()
    assert g["status"] == "PASS", g
    assert g["peak_modern_g"] < g["peak_plain_g"]
    assert g["peak_modern_g"] <= bm.LIMIT_G + 0.5


def test_modern_belt_lowers_the_peak_by_a_clear_margin_but_not_a_magic_one():
    plain, modern = bm.response("plain")["peak_g"][-1], bm.response("modern")["peak_g"][-1]
    assert 0.2 < 1.0 - modern / plain < 0.5       # honest size of the effect in this one-dimensional model (about 30 %)


def test_only_the_modern_belt_pays_out_and_only_above_the_cap():
    assert bm.response("plain")["payout_m"].max() == 0.0
    m = bm.response("modern")
    assert m["payout_m"].max() > 0.05
    assert not np.any(np.diff(m["payout_m"]) < -1e-12)
    cap_g = bm.LIMIT_G + 0.5
    assert m["chest_g"][m["payout_m"] == 0.0].max() <= cap_g


def test_pretensioner_holds_the_driver_back_while_the_plain_belt_lets_him_move():
    tc = bm.contact_time_s()
    assert bm.at("plain", tc)["pull_back_m"] == 0.0
    t = tc + bm.PRETENSION_DELAY_S + bm.PRETENSION_TIME_S
    plain, modern = bm.at("plain", t), bm.at("modern", t)
    assert modern["pull_back_m"] > 0.01
    assert modern["travel_m"] < plain["travel_m"] - 0.01


def test_modern_belt_gives_more_travel_but_stays_inside_the_room():
    assert bm.response("modern")["r"].max() > bm.response("plain")["r"].max() - 0.02
    assert bm.response("modern")["r"].max() < bm.ROOM_M


def test_chest_colour_scale_separates_the_two_belts():
    end_plain, end_modern = bm.at("plain", 0.5)["injury"], bm.at("modern", 0.5)["injury"]
    assert end_plain > 0.3 and end_modern < 0.15


def test_gate_rejects_a_chest_that_runs_out_of_room(monkeypatch):
    monkeypatch.setattr(bm, "ROOM_M", 0.20)
    bm.response.cache_clear()
    g = bm.belt_limiter_physics()
    assert g["status"] == "FAIL" and any("room" in p or "cap" in p for p in g["problems"])


def test_gate_rejects_a_limiter_that_never_acts(monkeypatch):
    monkeypatch.setattr(bm, "LIMIT_G", 500.0)
    bm.response.cache_clear()
    g = bm.belt_limiter_physics()
    assert g["status"] == "FAIL"
