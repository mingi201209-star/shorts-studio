import numpy as np

from benchmarks.guardrail_end import terminal_motion as m
from benchmarks.guardrail_end import terminal_timeline as tl


def test_gate_passes():
    r = m.terminal_physics()
    assert r["status"] == "PASS", r["problems"]


def test_numbers_quoted_in_the_film():
    stop = m._terminal()[-1][1] - m.CRUSH_MAX
    assert 1.8 <= stop / m.CAR_LEN <= 2.6                       # "about two car lengths"
    assert abs(m.V0 / m.MPH - 60) < 1e-9                        # "sixty to zero"
    assert m.CRUSH_MAX < m.CABIN_FROM_NOSE                      # "the cabin is untouched"
    assert m.SPEAR_M > m.CABIN_FROM_NOSE + 0.5                  # "it spears right into the cabin"


def test_ribbon_never_crosses_itself_and_leaves_the_rail_line():
    d = m._terminal()[-1][1] - m.CRUSH_MAX
    assert m.ribbon_min_clearance(d) > 0.06
    verts, faces = m.ribbon_mesh(d)
    assert len(faces) > 100 and np.isfinite(verts).all()


def test_posts_snap_in_order():
    times = [t for t in m.post_break_times() if t is not None]
    assert len(times) >= 3 and times == sorted(times)


def test_timeline_and_loop():
    segs = tl.segments()
    assert tl.scene_alignment(segs)["status"] == "PASS"
    first = tl.frame_state(0, segs)
    last = tl.frame_state(tl.frame_count() - 1, segs)
    assert first["t"] > 0 and m.terminal_state(first["t"])["head_d"] > 0.5      # frame 1 is already the hit
    assert abs(last["t"] - first["t"]) < 0.03 and last["cam"]["rel"] == first["cam"]["rel"]
