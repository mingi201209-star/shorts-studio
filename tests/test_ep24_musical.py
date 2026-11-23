import math

from benchmarks.musical_road import musical_motion as m
from benchmarks.musical_road import musical_timeline as tl


def test_gate_passes():
    r = m.musical_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_and_claims_in_the_film():
    for name in ("B3", "E4", "F#4", "G#4"):
        assert abs(m.cents(m.played_freq(name, "design", m.V_DESIGN), m.freq(name))) < 0.5      # the plan is in tune
        assert m.freq(name) >= 150                                                              # "hundreds of thumps a second"
    flats = [m.cents(m.played_freq(n, "built", m.V_DESIGN), m.freq(n)) for n in ("B3", "E4", "F#4", "G#4")]
    assert all(c < 0 for c in flats) and flats == sorted(flats, reverse=True)                   # "every note flat, the high notes most"
    assert m.played_freq("B3", "design", m.V_SLOW) < m.played_freq("B3", "design", m.V_DESIGN)    # "drive slower ... drops in pitch"
    assert abs(m.V_DESIGN / m.freq("B3") / m.IN - 4.0) < 0.15                                    # the repeated note is about 4 in apart


def test_thumps_follow_the_grooves():
    front, rear = m.hits("design", "design")
    assert all(b > a for a, b in zip(front, front[1:]))
    assert abs(rear[0] - front[0] - m.WHEELBASE / m.V_DESIGN) < 1e-9
    assert len(m.grooves("built")) < len(m.grooves("design"))
    assert m.road_end("built") == m.road_end("design")


def test_timeline_pace_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    assert tl.pace(segs)["status"] == "PASS"
    first, last = tl.frame_state(0, segs), tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0 and abs(last["t"] - first["t"]) < 0.002 and last["variant"] == first["variant"]


def test_no_camera_inside_the_car_or_the_ground():
    segs = tl.segments()
    for f in range(tl.frame_count()):
        sh = tl.frame_state(f, segs)
        x, y, z = tl.cam_world(sh)
        assert z > 0.05, f"frame {f} camera under the road"
        cs = tl.car_state(sh)
        if cs["visible"]:
            inside = abs(x - m.CAR_X) < 0.85 and cs["y"] - 2.1 < y < cs["y"] + 2.0 and z < 1.3
            assert not inside, f"frame {f} camera inside the car"
            assert math.dist((x, y), (m.CAR_X, cs["y"])) > 1.0 or z > 1.4, f"frame {f} camera too close to the car"
