"""EP.36 friction buffer stop: the model behind every claim, the two comparisons, the timeline rules, and the channel's caption
look."""
import math

from benchmarks.buffer_stop import stop_motion as m
from benchmarks.buffer_stop import stop_timeline as tl
from benchmarks.identity import captions


def test_gate_passes():
    r = m.stop_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    r = m.stop_physics()
    assert r["cars"] == 6                                                       # "a six-car train"
    assert abs(r["speed_mph"] - 15) <= 1                                         # "at fifteen miles an hour"
    assert 55 <= r["stop_ft"] <= 62                                              # "stops in about sixty feet" (Oleo: 18 m at 25 km/h)
    assert r["peak_g"] < m.CAR_HARD_BRAKING_G and r["car_g"] >= m.CAR_HARD_BRAKING_G   # "gentler than slamming on the brakes in your car"
    assert r["wall_g"] > 5                                                       # "hitting a solid wall would wreck it"
    assert r["pair_kN"] <= 50                                                    # Oleo: up to 50 kN per pair of shoes
    assert r["buffer_max_m"] > 0.1                                               # "the hydraulic buffers squash first"


def test_energy_goes_into_friction_and_oil():
    rows = m.impact()
    e_in = 0.5 * m.TRAIN_KG * m.V0 ** 2
    e_out = rows[-1][8] + rows[-1][9] + 0.5 * m.BUFFER_K * max(0.0, rows[-1][6]) ** 2
    assert abs(e_out - e_in) / e_in < 0.02
    assert rows[-1][8] / e_in > 0.9                                              # the shoes take nearly all of it, as heat
    v = [r[2] for r in rows]
    assert all(b <= a + 1e-12 for a, b in zip(v, v[1:])) and v[-1] == 0.0       # the train only ever slows


def test_comparisons():
    w = m.wall_state(1.0)
    assert w["train_speed"] == 0 and math.isclose(w["crush"], m.WALL_CRUSH, rel_tol=1e-6)
    c = m.car_state(10.0)
    assert c["speed"] == 0 and math.isclose(c["x"], m.CAR_V0 ** 2 / (2 * m.CAR_DECEL_G * m.G), rel_tol=1e-6)


def test_timeline_rules():
    segs = tl.segments()
    assert tl.pace(segs)["status"] == "PASS", tl.pace(segs)["problems"]
    assert tl.scene_alignment(segs)["status"] == "PASS"
    labels = [s["label"] for s in segs]
    assert math.isclose(segs[labels.index("B2-built-to-slide")]["t0"], tl.word_start(2, "buffer"))    # "...so this | buffer stop is built to slide"
    assert math.isclose(segs[labels.index("E2-heat")]["t0"], tl.word_start(5, "and"))                 # "| and the friction turns..."
    assert math.isclose(segs[labels.index("I2-push-back")]["t0"], tl.word_start(9, "it"))            # "push | it back, and tighten them again"
    assert segs[1]["t0"] <= 3.6
    reveals = [s for s in segs if s["flags"].get("reveal")]
    assert len(reveals) == 1 and reveals[0]["flags"].get("xray")
    assert [s["variant"] for s in segs].count("split") == 1


def test_caption_look_highlights_numbers_and_fits():
    text = (tl.AUDIO.parent / "film.ass").read_text(encoding="utf8")
    styled = captions.restyle(text)
    assert captions.STYLE in styled
    assert captions.YELLOW + "six-car" in styled and captions.YELLOW + "fifteen" in styled and captions.YELLOW + "sixty" in styled
    assert captions.widest_line_px(styled) <= captions.MAX_LINE_PX


def test_wreck_folds_take_exactly_the_crush():
    """The what-if's cab sides fold like an accordion: the folds shorten the zone by exactly the model's crush, the front strips
    fold first and most, none past FOLD_MAX, and nothing is folded before the hit."""
    back, front, n = m.FOLD
    w = (back - front) / n
    for c in (0.0, 0.02, 0.1, 0.2, m.WALL_CRUSH):
        th = m.fold_angles(c)
        assert len(th) == n
        assert math.isclose(sum(w * (1.0 - math.cos(a)) for a in th), c, abs_tol=1e-9)
        assert all(0.0 <= a <= m.FOLD_MAX + 1e-12 for a in th)
        assert th == sorted(th)
    assert max(m.fold_angles(0.0)) == 0.0
    assert max(m.fold_angles(m.WALL_CRUSH)) > math.radians(45)               # a wreck you can see, not a dent


def test_heat_builds_through_the_heat_line():
    """The thermal look in E2 follows the shoes' friction heat in the model: rising through the shot, past half of the total."""
    segs = tl.segments()
    e2 = next(s for s in segs if s["label"] == "E2-heat")
    end = m.state(m.impact()[-1][0])["shoe_heat_kJ"]
    t0, t1 = e2["sim0"], e2["sim1"]
    h0, h1 = m.state(t0)["shoe_heat_kJ"] / end, m.state(t1)["shoe_heat_kJ"] / end
    assert 0.3 < h0 < h1 <= 1.0
