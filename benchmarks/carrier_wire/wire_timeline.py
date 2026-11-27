"""EP.35 film timeline (pure data), built like EP.18-EP.34. Frame 1 is a jet already caught on a carrier's third arresting wire:
the wire stretched into a V behind it, sparks at the hook, the deck and the sea around. The shot is held until 3.6 s; line 1 runs
3.5 s, so the first cut falls just before line 2. Simulated time t is seconds after the hook catches the wire (wire_motion).

Variants: jet (the arrest) and crew (the deck crew changing the wire, no jet).
Flags:
- xray: the channel's reveal look, everything blueprint blue but the mechanism (wire, purchase cables, sheaves, crosshead, ram,
  cylinder, valve, oil line) glowing orange;
- reveal: the channel's signature cut, whose sting plays at the cut;
- hook_drop: the tailhook swings down during the shot;
- field: a football field laid over the runout;
- throttle: the engines at full power, nozzles glowing;
- cockpit: the cockpit lit, Bumper (the channel's dummy) at the controls.
A row may start at a word inside its line (start = (line, word) or (line, word, k) for the k-th cue opening with that word) or at
a fixed film time (a float)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.carrier_wire import wire_motion as m
from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.22
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep35-audio/audio-validation.json"
Y3 = m.wire_y()[m.CAUGHT]


def cam(loc, target, lens, fstop=11.0, rel="world"):
    """rel "world": coordinates as given; rel "hook": y measured from the jet's hook (a tracking shot)."""
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((-10.0, -5.0, 6.0), (0.0, 8.5, 1.4), 26.0, rel="hook")          # behind-left: the jet held by the V of the wire
A1_B = cam((-9.6, -4.4, 5.7), (0.0, 8.8, 1.4), 26.0, rel="hook")
B1 = cam((-7.0, -40.0, 11.0), (0.0, 150.0, -12.0), 28.0, rel="hook")      # chasing the jet in: the short deck ahead
B1_B = cam((-6.0, -34.0, 9.5), (0.0, 150.0, -12.0), 28.0, rel="hook")
B2 = cam((-5.2, -0.5, 3.4), (0.0, 1.6, 1.4), 30.0, rel="hook")           # beside the tail: the hook swings down
B2_B = cam((-5.0, 0.0, 3.2), (0.0, 1.8, 1.3), 30.0, rel="hook")
C = cam((-9.0, Y3 - 7.5, 0.9), (0.0, Y3 + 1.5, 0.4), 28.0)               # low on the deck: four wires, the hook snags the third
C_B = cam((-9.0, Y3 - 5.5, 0.9), (0.0, Y3 + 3.5, 0.5), 28.0)
D = cam((-17.0, Y3 + 3.0, 6.5), (0.0, Y3 - 9.0, -7.0), 24.0)             # x-ray: the deck see-through, the cable down to the engine
D_B = cam((-15.5, Y3 + 2.0, 5.5), (0.0, Y3 - 10.0, -7.5), 24.0)
E1 = cam((-7.5, Y3 - 9.0, -5.8), (0.0, Y3 - 17.0, -8.5), 26.0)           # x-ray, below deck: the crosshead drives the ram in
E1_B = cam((-7.0, Y3 - 10.0, -6.0), (0.0, Y3 - 16.5, -8.5), 26.0)
E2 = cam((-3.8, Y3 - 3.2, -6.9), (1.2, Y3 - 7.6, -8.2), 28.0)            # x-ray: oil forced through the valve, glowing with heat
E2_B = cam((-3.5, Y3 - 3.6, -7.0), (1.3, Y3 - 7.7, -8.2), 28.0)
F = cam((0.0, Y3 + 55.0, 190.0), (0.0, Y3 + 55.2, 0.0), 70.0)            # straight down: the runout against a football field
F_B = cam((0.0, Y3 + 56.0, 182.0), (0.0, Y3 + 56.2, 0.0), 70.0)
G = cam((-2.6, -5.8, 2.4), (0.0, 3.0, 1.8), 26.0, rel="hook")            # behind the jet: both nozzles blazing at full power
G_B = cam((-2.3, -5.2, 2.3), (0.0, 3.0, 1.8), 26.0, rel="hook")
H = cam((-1.15, 16.1, 3.5), (0.0, 14.75, 3.1), 30.0, rel="hook")         # the cockpit: Bumper thrown into the straps, then a thumbs up
H_B = cam((-1.05, 16.0, 3.45), (0.0, 14.75, 3.1), 30.0, rel="hook")
I1 = cam((-20.8, Y3 - 3.4, 2.2), (-17.3, Y3 + 1.4, 0.6), 30.0)           # the deck crew unhooking the worn wire
I1_B = cam((-20.4, Y3 - 3.0, 2.1), (-17.5, Y3 + 1.4, 0.6), 30.0)
I2 = cam((-19.0, Y3 - 9.0, 4.0), (-23.0, Y3 + 1.5, 0.5), 28.0)           # ...and dragging it away
I2_B = cam((-25.0, Y3 - 8.5, 3.8), (-31.0, Y3 + 1.5, 0.5), 28.0)

JET, CREW = "jet", "crew"
XR = {"xray": True}
# label, start, knots [(film s from shot start, simulated s)], cam a, cam b, variant, flags, lines
ROWS = [
    ("A1-caught", 1, [(0.0, OPEN_SIM), (3.6, 0.60)], A1, A1_B, JET, {}, (1,)),                     # held until 3.6 s (hook rule)
    ("B1-short-deck", 3.6, [(0.0, -4.0), (2.41, -2.0)], B1, B1_B, JET, {}, (1, 2)),
    ("B2-hook-down", (2, "the", 2), [(0.0, -1.7), (1.34, -1.25)], B2, B2_B, JET, {"hook_drop": True}, (2,)),
    ("C-snags-third", 3, [(0.0, -0.55), (3.59, 0.55)], C, C_B, JET, {}, (3,)),
    ("D-below-deck", 4, [(0.0, 0.45), (4.75, 1.15)], D, D_B, JET, dict(XR, reveal=True), (4,)),
    ("E1-piston", 5, [(0.0, 0.9), (2.6, 1.7)], E1, E1_B, JET, dict(XR), (5,)),
    ("E2-valve-heat", (5, "forces"), [(0.0, 1.5), (3.77, 2.5)], E2, E2_B, JET, dict(XR, heat=True), (5,)),
    ("F-football-field", 6, [(0.0, 1.0), (3.88, 3.3)], F, F_B, JET, {"field": True}, (6,)),
    ("G-full-throttle", 7, [(0.0, 0.5), (3.09, 2.1)], G, G_B, JET, {"throttle": True}, (7,)),
    ("H-thats-me", 8, [(0.0, 2.35), (1.95, 3.7)], H, H_B, JET, {"cockpit": True, "throttle": True}, (8,)),
    ("I1-worn-wire", 9, [(0.0, 0.0), (2.28, 1.0)], I1, I1_B, CREW, {}, (9,)),
    ("I2-thrown-away", (9, "the"), [(0.0, 1.0), (1.97, 2.0)], I2, I2_B, CREW, {"drag": True}, (9,)),
]


def _audio() -> dict:
    return json.loads(AUDIO.read_text())


def line_starts() -> list[float]:
    return [b["start"] for b in _audio()["beats"]]


def total_seconds() -> float:
    return round(_audio()["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def word_start(line: int, word: str, k: int = 1) -> float:
    """Start of the k-th caption cue that opens with `word` inside narration line `line` (cue times are the voice's word timings)."""
    a = _audio()
    b = a["beats"][line - 1]
    hits = [c["start"] for c in a["cues"] if b["start"] - 1e-6 <= c["start"] < b["end"] and c["text"].split()[0].strip(".,!?").lower() == word.lower()]
    if len(hits) < k:
        raise ValueError(f"no cue number {k} starting with {word!r} in line {line}")
    return hits[k - 1]


def _start(st) -> float:
    if isinstance(st, float):
        return st
    return line_starts()[st - 1] if isinstance(st, int) else word_start(*st)


def segments() -> list[dict]:
    total = total_seconds()
    t = [_start(r[1]) for r in ROWS] + [total]
    out = []
    for i, (label, _, knots, ca, cb, variant, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        seg = {"label": label, "t0": t0, "t1": t1, "knots": list(knots), "cam_a": ca, "cam_b": cb, "variant": variant, "flags": flags,
               "lines": lines}
        seg["sim0"], seg["sim1"] = sim_time(seg, t0), sim_time(seg, t1 - 1e-6)
        seg["time_scale"] = round((seg["sim1"] - seg["sim0"]) / (t1 - t0), 6)
        out.append(seg)
    return out


def sim_time(seg: dict, film_t: float) -> float:
    """Piecewise-linear map through the shot's knots, extended with the last slope."""
    tau = film_t - seg["t0"]
    k = seg["knots"]
    if tau <= k[0][0]:
        return k[0][1]
    for (a, sa), (b, sb) in zip(k[:-1], k[1:]):
        if tau <= b:
            return sa + (sb - sa) * (tau - a) / (b - a)
    (a, sa), (b, sb) = k[-2], k[-1]
    return sb + (sb - sa) / (b - a) * (tau - b)


def _smooth(u):
    return 0.5 * u + 0.5 * u * u * (3 - 2 * u)


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    c = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
         "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
         "fstop": a.get("fstop", 8.0) + (b.get("fstop", 8.0) - a.get("fstop", 8.0)) * uc}
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim_time(seg, t), "variant": seg["variant"], "cam": c, "u": u}
    st.update(seg["flags"])
    return st


def scene_alignment(segs: list[dict]) -> dict:
    problems, rows = [], []
    for k, st in enumerate(line_starts(), 1):
        seg = next((s for s in segs if s["t0"] <= st + 0.05 < s["t1"]), None)
        rows.append({"line": k, "cue_s": round(st, 2), "segment": seg["label"] if seg else None})
        if seg is None or k not in seg["lines"]:
            problems.append(f"line {k} at {st:.2f}s shows {seg['label'] if seg else 'nothing'}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows}


def pace(segs: list[dict]) -> dict:
    """Pace rules as a gate: the opening shot held through the first line (benchmarks/hook_gate.py), at least 18 cuts a minute,
    160-200 words a minute, at most 40 s."""
    a = _audio()
    words = sum(len(b["narration_en"].split()) for b in a["beats"])
    secs = total_seconds()
    wpm = 60 * words / a["seconds"]
    cuts = 60 * len(segs) / secs
    problems = []
    problems += opening_rule(segs, line_starts()[1])
    if cuts < 18:
        problems.append(f"{cuts:.0f} cuts a minute (rule: at least 18)")
    if not 160 <= wpm <= 200:
        problems.append(f"narration at {wpm:.0f} words a minute (rule: 160-200)")
    if secs > 40:
        problems.append(f"{secs:.1f} s long (rule: at most 40)")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_cut_s": round(segs[1]["t0"], 2), "cuts_per_min": round(cuts, 1),
            "wpm": round(wpm), "seconds": secs}
