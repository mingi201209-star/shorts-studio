from benchmarks import hook_gate as hg


def test_box_metrics():
    inside, width = hg.box_metrics([0.2, 0.7, 0.3, 0.6])
    assert abs(inside - 1.0) < 1e-9 and abs(width - 0.5) < 1e-9
    inside, width = hg.box_metrics([-0.5, 0.5, 0.0, 1.0])            # half of the subject is off the left edge
    assert abs(inside - 0.5) < 1e-9 and abs(width - 0.5) < 1e-9


def _segs(first_cut):
    return [{"t0": 0.0}, {"t0": first_cut}]


def test_opening_rule():
    assert hg.opening_rule(_segs(1.3), 2.6)                             # cut away after 1.3 s: the EP.14-EP.19 pattern
    assert not hg.opening_rule(_segs(2.6), 2.6)
    assert not hg.opening_rule(_segs(1.9), 1.89)                        # a first line shorter than 2 s
    assert hg.opening_rule(_segs(4.0), 3.3)                             # held too long


def test_opening_hook_framing():
    frames = [{"frame": f, "parts": [{"subject_box": [0.1, 0.6, 0.3, 0.6]}]} for f in range(24)]
    assert hg.opening_hook(frames, _segs(2.5), 2.5, 24)["status"] == "PASS"
    frames[3]["parts"][0]["subject_box"] = [0.45, 0.55, 0.4, 0.5]       # too small
    assert hg.opening_hook(frames, _segs(2.5), 2.5, 24)["status"] == "FAIL"
    frames[3]["parts"][0]["subject_box"] = [-0.4, 1.05, 0.1, 0.7]       # a long machine filling the picture, ends cut: readable
    assert hg.opening_hook(frames, _segs(2.5), 2.5, 24)["status"] == "PASS"
    frames[3]["parts"][0]["subject_box"] = [-2.5, 1.6, -1.0, 1.4]       # one wheel filling the frame: most of the car outside
    assert hg.opening_hook(frames, _segs(2.5), 2.5, 24)["status"] == "FAIL"
