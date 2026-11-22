"""EP.17 film timeline (pure data), built like EP.13-EP.16 (docs/episode-playbook.md), copying what made EP.13 take off: frame 1 is
road hardware doing something strange and satisfying, already in motion (the machine "swallowing" the concrete wall, the wall
snaking through its open frame in an S, traffic flowing past). Simulated time t in seconds; the machine is at y = 5 mph * t.
Variants: day (wall moves over), morning (wall one lane over, rush-hour traffic, no machine), night (machine moves it back).
rel "machine" = (0, machine y, 0); rel "world" = render world."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep17-audio/audio-validation.json"

A1 = {"rel": "machine", "loc": (-6.5, 7.0, 9.0), "target": (1.8, -0.5, 0.3), "lens": 32.0, "fstop": 11.0}      # machine, S-curved wall and traffic in one view
A1_B = {"rel": "machine", "loc": (-5.8, 6.0, 8.4), "target": (1.8, -0.6, 0.3), "lens": 32.0, "fstop": 11.0}
B1 = {"rel": "machine", "loc": (-12.0, -28.0, 15.0), "target": (1.8, 6.0, 0.0), "lens": 26.0, "fstop": 11.0}
B1_B = {"rel": "machine", "loc": (-11.0, -25.0, 14.0), "target": (1.8, 6.0, 0.0), "lens": 26.0, "fstop": 11.0}
B2 = {"rel": "machine", "loc": (-7.4, -6.0, 1.1), "target": (-0.5, 10.0, 0.7), "lens": 28.0, "fstop": 5.6}
B2_B = {"rel": "machine", "loc": (-7.4, -4.0, 1.0), "target": (-0.5, 11.0, 0.7), "lens": 28.0, "fstop": 5.6}
C1 = {"rel": "machine", "loc": (-1.1, 13.0, 0.5), "target": (0.0, 26.0, 0.55), "lens": 28.0, "fstop": 4.0}
C1_B = {"rel": "machine", "loc": (-1.0, 13.5, 0.6), "target": (0.0, 26.0, 0.55), "lens": 28.0, "fstop": 4.0}
C2 = {"rel": "machine", "loc": (-0.75, 18.6, 0.85), "target": (0.0, 19.3, 0.55), "lens": 35.0, "fstop": 4.0}
C2_B = {"rel": "machine", "loc": (-0.70, 18.4, 0.80), "target": (0.0, 19.1, 0.55), "lens": 35.0, "fstop": 4.0}
D = {"rel": "machine", "loc": (1.5, 10.5, 0.85), "target": (0.4, 6.0, 0.6), "lens": 34.0, "fstop": 4.0}
D_B = {"rel": "machine", "loc": (1.4, 10.0, 0.9), "target": (0.5, 5.6, 0.62), "lens": 34.0, "fstop": 4.0}
E = {"rel": "machine", "loc": (3.2, 4.0, 0.9), "target": (1.0, 2.6, 0.75), "lens": 30.0, "fstop": 4.0}
E_B = {"rel": "machine", "loc": (3.2, 3.0, 0.9), "target": (1.2, 1.8, 0.78), "lens": 30.0, "fstop": 4.0}
F1 = {"rel": "machine", "loc": (-2.0, -9.0, 16.5), "target": (1.8, 1.5, 0.0), "lens": 40.0, "fstop": 11.0}      # from above: the S track
F1_B = {"rel": "machine", "loc": (-1.6, -8.2, 16.0), "target": (1.8, 1.2, 0.0), "lens": 40.0, "fstop": 11.0}
F2 = {"rel": "machine", "loc": (-0.5, -26.0, 7.0), "target": (1.8, 4.0, 0.0), "lens": 50.0, "fstop": 8.0}
F2_B = {"rel": "machine", "loc": (-0.3, -23.0, 6.4), "target": (1.8, 4.0, 0.0), "lens": 50.0, "fstop": 8.0}
G = {"rel": "machine", "loc": (-0.8, -12.5, 0.45), "target": (3.4, -10.0, 0.35), "lens": 30.0, "fstop": 4.0}
G_B = {"rel": "machine", "loc": (-0.7, -12.0, 0.5), "target": (3.4, -9.6, 0.35), "lens": 30.0, "fstop": 4.0}
H1 = {"rel": "world", "loc": (-16.0, -30.0, 14.0), "target": (0.0, 10.0, 0.0), "lens": 26.0, "fstop": 11.0}
H1_B = {"rel": "world", "loc": (-15.0, -26.0, 13.0), "target": (0.0, 12.0, 0.0), "lens": 26.0, "fstop": 11.0}
H2 = {"rel": "machine", "loc": (-7.0, 13.0, 4.5), "target": (1.8, 0.0, 0.3), "lens": 26.0, "fstop": 8.0}
H2_B = {"rel": "machine", "loc": (-6.5, 11.5, 4.0), "target": (1.8, 0.0, 0.3), "lens": 26.0, "fstop": 8.0}
I = {"rel": "machine", "loc": (-6.0, -18.0, 9.0), "target": (1.8, 3.0, 0.0), "lens": 32.0, "fstop": 11.0}

# label, variant, start (line, or (line, absolute second)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-swallowing", "day", 1, [(0.0, 0.0), (2.42, 2.42)], A1, A1_B, {}, (1,)),      # held through line 1 (hook rule)
    ("B1-one-lane-over", "day", 2, [(0.0, 3.0), (2.53, 5.53)], B1, B1_B, {}, (2,)),
    ("B2-traffic-flows", "day", (2, 4.95), [(0.0, 5.53), (1.66, 7.19)], B2, B2_B, {}, (2,)),
    ("C1-chain", "day", 3, [(0.0, 8.0), (2.09, 10.09)], C1, C1_B, {}, (3,)),
    ("C2-pins", "day", (3, 8.70), [(0.0, 10.1), (1.91, 12.01)], C2, C2_B, {}, (3,)),
    ("D-fifteen-hundred-pounds", "day", 4, [(0.0, 12.0), (2.54, 14.54)], D, D_B, {}, (4,)),
    ("E-wheels-grab", "day", 5, [(0.0, 14.5), (3.76, 18.26)], E, E_B, {}, (5,)),
    ("F1-s-track", "day", 6, [(0.0, 18.3), (2.64, 20.94)], F1, F1_B, {}, (6,)),
    ("F2-twelve-feet", "day", (6, 19.55), [(0.0, 21.0), (1.97, 22.97)], F2, F2_B, {}, (6,)),
    ("G-drop-back-down", "day", 7, [(0.0, 23.0), (3.6, 26.6)], G, G_B, {}, (7,)),
    ("H1-morning", "morning", 8, [(0.0, 0.0), (2.98, 2.98)], H1, H1_B, {}, (8,)),
    ("H2-night", "night", (8, 28.10), [(0.0, 10.0), (1.74, 11.74)], H2, H2_B, {"night": True}, (8,)),
    ("I-loop", "day", 9, [(0.0, -3.0), (3.06, -0.02)], I, A1, {"loop": True}, (9,)),
]


def _audio() -> dict:
    return json.loads(AUDIO.read_text())


def line_starts() -> list[float]:
    return [b["start"] for b in _audio()["beats"]]


def total_seconds() -> float:
    return round(_audio()["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def segments() -> list[dict]:
    s = line_starts()
    total = total_seconds()
    starts = []
    for r in ROWS:
        st = r[2]
        if isinstance(st, int):
            starts.append(s[st - 1])
        elif st[1] is None:
            starts.append(total - 1.0)
        else:
            starts.append(st[1])
    t = starts + [total]
    out = []
    for i, (label, variant, _, knots, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        seg = {"label": label, "variant": variant, "t0": t0, "t1": t1, "knots": knots, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines}
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
    uc = 0.5 * u + 0.5 * (1 - (1 - u) ** 2) if seg["flags"].get("loop") else _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    cam = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
           "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
           "fstop": a.get("fstop", 8.0) + (b.get("fstop", 8.0) - a.get("fstop", 8.0)) * uc}
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim_time(seg, t), "cam": cam, "u": u}
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
    """Pace rules as a gate: the opening shot held through the first line (benchmarks/hook_gate.py; replaces the competitor research's
    "first cut by 1.5 s", which cut away from the money shot), at least 18 cuts a minute, 160-200 words a minute, at most 40 s."""
    a = _audio()
    words = sum(len(b["narration_en"].split()) for b in a["beats"])
    secs = total_seconds()
    wpm = 60 * words / a["seconds"]
    cuts = 60 * len(segs) / secs
    problems = []
    problems += opening_rule(segs, line_starts()[1])          # hold the opening money shot through the first line (2026-11-22 data)
    if cuts < 18:
        problems.append(f"{cuts:.0f} cuts a minute (rule: at least 18)")
    if not 160 <= wpm <= 200:
        problems.append(f"narration at {wpm:.0f} words a minute (rule: 160-200)")
    if secs > 40:
        problems.append(f"{secs:.1f} s long (rule: at most 40)")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_cut_s": round(segs[1]["t0"], 2), "cuts_per_min": round(cuts, 1),
            "wpm": round(wpm), "seconds": secs}
