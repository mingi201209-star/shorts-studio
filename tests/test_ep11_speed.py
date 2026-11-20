from benchmarks.speed_energy import speed_motion as m
from benchmarks.speed_energy import speed_timeline as tl


def test_gate_passes():
    r = m.speed_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert round(100 * (m.energy_kj("fast") / m.energy_kj("slow") - 1)) == 78      # "seventy-eight percent more energy"
    assert round(100 * m.crush_m("slow") / 2.54) in (20, 21)                       # "about twenty inches"
    assert round(100 * m.crush_m("fast") / 2.54) == 28                              # "nearly twenty-eight"
    assert (m.storeys("slow"), m.storeys("fast")) == (3, 5)                        # three- and five-story falls
    assert round(m.fast_speed_where_slow_stops_mph()) == 35                        # "still doing thirty-five"
    assert m.energy_kj("fast") / m.energy_kj("slow") > 1.7                         # "almost twice the crash"


def test_crush_grows_with_speed_energy_with_its_square():
    assert abs(m.crush_m("fast") / m.crush_m("slow") - 40 / 30) < 1e-9
    assert abs(m.energy_kj("fast") / m.energy_kj("slow") - (40 / 30) ** 2) < 1e-9


def test_timeline():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    hit = next(f for f in range(tl.frame_count()) if tl.frame_state(f, segs)["t"] >= 0)
    assert hit / tl.FPS < 1.0                                                       # the crash lands in the first second
    last, first = tl.frame_state(tl.frame_count() - 1, segs), tl.frame_state(0, segs)
    assert abs(last["t"] - first["t"]) < 0.06                                       # loop closes
