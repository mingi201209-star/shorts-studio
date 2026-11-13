import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.road_safety import runaway_ramp_motion as m


def test_gravel_stops_the_truck_within_the_clip():
    s = m.simulate()
    assert s[-1]["v"] == 0.0
    assert m.stop_time(s) < 25.0


def test_stop_distance_close_to_constant_decel_estimate():
    s = m.simulate()
    ideal = m.SPEED0 ** 2 / (2 * m.GRAVEL_C * m.G)
    # sink-in ramp lengthens it a little but not by more than ~10 m
    assert ideal < s[-1]["x"] < ideal + 10.0


def test_paved_road_takes_far_longer_than_gravel():
    assert m.stop_distance(m.PAVED_C) > 10 * m.stop_distance(m.GRAVEL_C)


def test_speed_never_increases_and_distance_never_decreases():
    s = m.simulate()
    for a, b in zip(s, s[1:]):
        assert b["v"] <= a["v"] + 1e-12 and b["x"] >= a["x"] - 1e-12


def test_energy_audit_balances():
    assert abs(m.audit_energy(m.simulate())["ratio"] - 1.0) < 0.02


def test_never_claims_calibration():
    assert m.summary(m.simulate())["physically_calibrated"] is False


def test_gravel_grains_are_ballistic_and_land_in_the_bed():
    s = m.simulate()
    gr = m.build_gravel(s)
    assert 1500 < len(gr) < 12000
    end_t = len(s) / m.FPS
    for g in gr[::40]:
        x, y, z = m.grain_position(g, end_t)
        assert abs(z - g["r"]) < 1e-9 and abs(x) < 6.0 and y > 0.0


def test_gravel_emission_follows_speed_and_stops_with_the_truck():
    s = m.simulate()
    gr = m.build_gravel(s)
    assert max(g["t0"] for g in gr) <= m.stop_time(s) + 0.1
    first_half = sum(1 for g in gr if g["t0"] < 5.0)
    assert first_half > 0.5 * len(gr)


def test_gates_accept_the_simulated_motion_and_reject_exaggeration():
    from benchmarks.road_safety import runaway_ramp_gates as g
    s = m.simulate()
    summ = m.summary(s)
    summ["paved_stop_distance_m"] = round(m.stop_distance(m.PAVED_C))
    summ["energy_ratio"] = round(m.audit_energy(s)["ratio"], 4)
    assert g.motion_plausibility(summ)["status"] == "PASS"
    bad = dict(summ, stop_distance_m=60.0)
    assert g.motion_plausibility(bad)["status"] == "FAIL"
    assert g.motion_plausibility(dict(summ, physically_calibrated=True))["status"] == "FAIL"


def test_manifest_shots_match_the_renderer_and_cover_every_frame():
    import json, re
    man = json.loads((Path(__file__).resolve().parents[1] / "examples/experiments/runaway-ramp-manifest.json").read_text())
    src = (Path(__file__).resolve().parents[1] / "benchmarks/road_safety/render_runaway_ramp.py").read_text()
    ids = re.findall(r'"(\w+)": \(-?\d', src.split("SIM_RANGE = ")[1].split("\n\n")[0])
    assert [s["id"] for s in man["shots"]] == ids
    assert man["shots"][0]["start"] == 1 and man["shots"][-1]["end"] == man["total_frames"] == 960
    for a, b in zip(man["shots"], man["shots"][1:]):
        assert b["start"] == a["end"] + 1
    assert man["look"] == "cinematic" and man.get("physically_calibrated", False) is False
