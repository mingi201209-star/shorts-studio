from benchmarks.airbag import airbag_motion as m
from benchmarks.airbag import airbag_timeline as tl


def test_gate_passes():
    r = m.airbag_physics()
    assert r["status"] == "PASS", r["problems"]


def test_bag_fills_then_vents():
    tc = m.contact_time_s()
    assert m.fill(tc) == 0.0
    assert m.fill(tc + m.FIRE_DELAY_S + m.FILL_S + 1e-6) == 1.0
    assert m.vent(tc + 0.15) < 0.6


def test_airbag_lowers_head_load_a_lot():
    r = m.airbag_physics()
    assert r["peak_head_g_off"] > 4 * r["peak_head_g_on"]


def test_film_lines_align_and_bare_head_hits_in_opening():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    a = segs[0]
    hit_dt = next(i / 1000 for i in range(200) if m.at("off", m.contact_time_s() + i / 1000)["head_m"] >= m.HEAD_GAP_M)
    assert a["sim0"] < hit_dt < a["sim1"]
