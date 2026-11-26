"""EP.32 truck-mounted attenuator: the model behind every claim in the narration, the timeline rules and the signature sting."""
import math

import numpy as np

from benchmarks.attenuator_truck import tma_motion as m
from benchmarks.attenuator_truck import tma_timeline as tl
from benchmarks.signature_sting import RISE_S, reveal_sting


def test_gate_passes():
    r = m.tma_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    r = m.tma_physics()
    assert 7.0 <= r["car_crush_ft"] <= 9.0                       # "slows down over about eight feet of crushing metal"
    assert 3.0 <= r["truck_roll_ft"] <= 6.5                      # "it only rolls a few feet"
    assert r["pickup_lb"] == 5000 and r["speed_mph"] == 62        # "a five-thousand-pound pickup at sixty-two miles an hour"
    assert r["pickup_crush_ft"] < r["stroke_ft"]                 # and it is stopped inside the cushion
    assert m.TRUCK_MASS / m.CAR_MASS > 5                          # "the truck is heavy"


def test_rows_crush_from_the_back_one_after_another():
    prev = (0.0, 0.0, 0.0)
    for c in np.linspace(0.0, m.STROKE, 400):
        s = m.stage_crush(float(c))
        assert all(b >= a - 1e-12 for a, b in zip(prev, s))       # nothing un-crushes
        for k in (1, 2):
            assert s[k] == 0.0 or s[k - 1] >= m.STAGE_STROKE[k - 1] - 1e-9
        prev = s
    assert m.STAGE_FORCE[0] < m.STAGE_FORCE[1] < m.STAGE_FORCE[2]


def test_crash_conserves_order_and_stops():
    rows, t_crush = m.car_crash()
    t = np.array([r[0] for r in rows])
    x1, x2, v1, v2 = (np.array([r[i] for r in rows]) for i in (1, 2, 3, 4))
    assert np.all(np.diff(t) > 0) and np.all(x1 - x2 >= -1e-9)    # the car never passes back out of the cushion
    assert v1[-1] == 0.0 and v2[-1] == 0.0 and 0.1 < t_crush < 0.2
    assert np.all(np.diff(x2) >= -1e-12)                           # the truck only moves forward
    st = m.car_state(-1.0)
    assert math.isclose(st["y"] + m.NOSE, -m.CUSHION_L - m.V0, rel_tol=1e-9)


def test_cushion_swings_down_from_upright():
    a = [m.fold_angle(t) for t in np.linspace(0.0, m.FOLD_START + m.FOLD_TIME + 0.5, 60)]
    assert math.isclose(a[0], math.pi / 2) and a[-1] == 0.0 and all(y <= x + 1e-12 for x, y in zip(a, a[1:]))


def test_debris_stays_above_the_ground():
    for k in range(m.N_DEBRIS):
        for t in np.arange(0.0, 3.0, 0.02):
            p = m.debris_pose(k, float(t))
            if p is not None:
                assert p[0][2] >= m.debris()[k][3][2] / 2 - 1e-6


def test_timeline_rules():
    segs = tl.segments()
    assert tl.pace(segs)["status"] == "PASS", tl.pace(segs)["problems"]
    assert tl.scene_alignment(segs)["status"] == "PASS"
    labels = [s["label"] for s in segs]
    g2 = segs[labels.index("G2-few-feet")]
    assert math.isclose(g2["t0"], tl.word_start(7, "so"))         # "...braked, | so it only rolls a few feet": the cut is on "so"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert last["segment"] == "I-loop" and 0 < last["t"] <= first["t"]
    assert np.allclose(last["cam"]["loc"], first["cam"]["loc"]) and np.allclose(last["cam"]["target"], first["cam"]["target"])


def test_signature_sting_is_the_same_every_time_and_lands_on_the_reveal_cut():
    a, b = reveal_sting(), reveal_sting()
    assert np.array_equal(a, b) and np.max(np.abs(a)) <= 1.0 + 1e-9
    i = int(RISE_S * 48000)
    assert np.sqrt(np.mean(a[i:i + 2400] ** 2)) > 3 * np.sqrt(np.mean(a[:i // 2] ** 2))   # the shing lands at the cut
    reveals = [s for s in tl.segments() if s["flags"].get("reveal")]
    assert len(reveals) == 1 and reveals[0]["flags"].get("cut")
