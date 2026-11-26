"""Series tail (next-episode teaser after a Short): the frozen spoken line, its captions and the ducking of the next episode's effects."""
import json
import math
from pathlib import Path

import numpy as np

from benchmarks import series_tail as st
from benchmarks.guardrail_end.terminal_sfx import SR, db

ROOT = Path(__file__).resolve().parents[1]
TAIL = ROOT / "examples/episodes/ep32-audio/tail"


def test_frozen_line_is_intact_and_measured():
    cta, voice = st.load_cta(TAIL)
    assert cta["text"] == "Subscribe for part two: what stops a giant ship."
    assert len(voice) / SR > cta["words"][-1]["end"]
    starts = [w["start"] for w in cta["words"]]
    assert starts == sorted(starts) and all(w["end"] > w["start"] for w in cta["words"])


def test_line_fits_the_tail_with_a_breath_after_it():
    cta = json.loads((TAIL / "cta.json").read_text())
    a, b = st.voice_span(cta, 0.25)
    assert a == 0.25 and b <= 84 / st.FPS - 0.2


def test_captions_say_the_line_in_order_and_stay_to_the_end():
    cta = json.loads((TAIL / "cta.json").read_text())
    film_s, tail_s = 765 / st.FPS, 84 / st.FPS
    cues = st.cues(cta, film_s, 0.25, tail_s)
    assert " ".join(c["text"].replace(r"\N", " ") for c in cues) == cta["text"]
    assert math.isclose(cues[0]["start"], film_s + 0.25)                    # the first word is captioned when it is said
    assert all(c["end"] > c["start"] for c in cues)
    assert all(b["start"] >= a["end"] for a, b in zip(cues, cues[1:]))       # one caption at a time
    assert math.isclose(cues[-1]["end"], film_s + tail_s)                     # up to the last frame
    assert all(len(line) <= 24 for c in cues for line in c["text"].split(r"\N"))


def test_effects_duck_under_the_line_and_come_back():
    n = int(3.5 * SR)
    g = st.duck(n, [(0.25, 3.19)])
    t = np.arange(n) / SR
    assert np.allclose(g[t < 0.25 - st.RAMP_S], 1.0) and np.allclose(g[t > 3.19 + st.RAMP_S], 1.0)
    inside = g[(t >= 0.25) & (t <= 3.19)]
    assert np.allclose(inside, db(st.DUCK_DB))
    ramp = g[(t > 0.25 - st.RAMP_S) & (t < 0.25)]
    assert np.all(np.diff(ramp) <= 1e-12)                                    # glides down, no step
    assert g.min() >= db(st.DUCK_DB) - 1e-12


def test_tail_draws_no_text():
    assert st.no_scene_text()["status"] == "PASS"
