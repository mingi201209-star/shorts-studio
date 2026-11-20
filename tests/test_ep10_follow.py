from benchmarks.following import follow_motion as m


def test_gate_passes():
    r = m.follow_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    assert round(m.reaction_distance() / 0.9144) >= 44          # "over forty yards"
    assert round(m.braking_distance()) == 46                       # "the car ahead stops in forty six meters"
    assert round(m.reaction_distance() + m.braking_distance()) == 86
    assert m.V0 * 2.0 / 0.9144 > 50                                # two seconds at 60 mph: "more than fifty yards"
