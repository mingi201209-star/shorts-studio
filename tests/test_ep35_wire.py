"""EP.35 carrier arresting wire: the model behind every claim, the wire geometry the renderer draws, the timeline rules, and the
channel's caption look."""
import math

import numpy as np

from benchmarks.carrier_wire import wire_motion as m
from benchmarks.carrier_wire import wire_timeline as tl
from benchmarks.identity import captions


def test_gate_passes():
    r = m.wire_physics()
    assert r["status"] == "PASS", r["problems"]


def test_claims_in_the_film():
    r = m.wire_physics()
    assert abs(r["speed_mph"] - 150) <= 1 and r["jet_lb"] == 50000            # "a fifty-thousand-pound jet ... a hundred fifty miles an hour"
    assert abs(r["stop_ft"] - 340) <= 5                                        # Mk 7 Mod 3: about 340 ft
    assert 0.8 * m.FOOTBALL_FIELD_FT <= r["stop_ft"] <= 1.1 * m.FOOTBALL_FIELD_FT   # "about the length of a football field"
    assert r["wires"] == 4 and r["caught"] == 3                                # "one of four steel cables"
    assert r["cable_life"] == 125                                              # "after a hundred twenty-five landings"


def test_engine_takes_the_jets_motion_and_the_thrust():
    rows = m.arrest()
    d_stop = rows[-1][1]
    e_in = 0.5 * m.mass() * m.V0 ** 2 + m.thrust() * d_stop
    assert 55e6 < e_in < 70e6                                                  # about 64 MJ in the Mk 7's description
    v = np.array([r[2] for r in rows])
    taut = int(0.1 / m.DT)                                                     # full power pushes a touch harder than the slack wire
    assert v[:taut].max() - m.V0 < 0.01 and np.all(np.diff(v[taut:]) <= 1e-12) and v[-1] == 0.0


def test_wire_halves_pull_along_the_deck():
    for d in (1.0, 10.0, 60.0, 100.0):
        L = math.hypot(m.SPAN, d)
        assert math.isclose(2 * m.tension(d) * d / L, m.pull(d), rel_tol=1e-9)
        assert math.isclose(m.payout(d), L - m.SPAN, rel_tol=1e-9)
    assert m.pull(0.0) == 0.0 and m.payout(-3.0) == 0.0


def test_timeline_rules():
    segs = tl.segments()
    assert tl.pace(segs)["status"] == "PASS", tl.pace(segs)["problems"]
    assert tl.scene_alignment(segs)["status"] == "PASS"
    labels = [s["label"] for s in segs]
    assert math.isclose(segs[labels.index("B2-hook-down")]["t0"], tl.word_start(2, "the", 2))   # "...so | the jet drops a hook"
    assert math.isclose(segs[labels.index("E2-valve-heat")]["t0"], tl.word_start(5, "forces"))
    assert segs[1]["t0"] <= 3.6                                                # opening held, cut before 3.6 s
    reveals = [s for s in segs if s["flags"].get("reveal")]
    assert len(reveals) == 1 and reveals[0]["flags"].get("xray")


def test_caption_look_highlights_numbers_and_fits():
    text = (tl.AUDIO.parent / "film.ass").read_text(encoding="utf8")
    styled = captions.restyle(text)
    assert captions.STYLE in styled and captions.FONT_NAME in styled
    assert captions.YELLOW + "fifty" in styled and captions.YELLOW + "four" in styled
    assert captions.widest_line_px(styled) <= captions.MAX_LINE_PX
    assert not captions.is_number("pulleys") and captions.is_number("twenty-five") and captions.is_number("fifty-thousand-pound")
