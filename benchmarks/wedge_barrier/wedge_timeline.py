"""EP.18 film timeline (pure data), built on what made EP.13 take off and the owner's brief for EP.18 ("dynamic like EP.13, a thing people
see and think: what the hell is that"): frame 1 is the red car already slamming into a steel wall that came out of the road, its nose
crushing, glass and plastic flying, sparks, the rear lifting. Simulated time t: seconds after the car's nose meets the raised face.
Variants: car (lane A), truck (lane B, the 15,000 lb test case). Flags: cut (cut-away of the pit), force (the load path glows)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.03
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep18-audio/audio-validation.json"

A1 = {"rel": "world", "loc": (-5.6, -3.4, 1.4), "target": (-1.9, -1.0, 0.8), "lens": 26.0, "fstop": 5.6}      # whole car, striped face, both plates
A1_B = {"rel": "world", "loc": (-5.1, -2.9, 1.3), "target": (-1.9, -1.0, 0.85), "lens": 26.0, "fstop": 5.6}
B = {"rel": "world", "loc": (-1.0, 4.2, 1.1), "target": (-1.9, -8.0, 0.6), "lens": 30.0, "fstop": 5.6}
B_B = {"rel": "world", "loc": (-1.0, 3.6, 1.0), "target": (-1.9, -8.0, 0.6), "lens": 32.0, "fstop": 5.6}
C1 = {"rel": "world", "loc": (-7.5, 1.2, 0.2), "target": (-1.9, 0.9, -0.45), "lens": 30.0, "fstop": 5.6}
C1_B = {"rel": "world", "loc": (-7.0, 0.6, 0.25), "target": (-1.9, 0.9, -0.45), "lens": 30.0, "fstop": 5.6}
C2 = {"rel": "world", "loc": (-5.2, 1.6, 0.15), "target": (-1.9, 1.3, -0.45), "lens": 34.0, "fstop": 5.6}
C2_B = {"rel": "world", "loc": (-4.9, 1.9, 0.12), "target": (-1.9, 1.4, -0.45), "lens": 34.0, "fstop": 5.6}
D = {"rel": "world", "loc": (-7.0, 0.5, 0.4), "target": (-1.9, 0.8, -0.2), "lens": 30.0, "fstop": 5.6}
D_B = {"rel": "world", "loc": (-6.6, 0.2, 0.45), "target": (-1.9, 0.8, -0.1), "lens": 30.0, "fstop": 5.6}
E = {"rel": "world", "loc": (-1.2, 4.0, 1.4), "target": (-1.9, -1.2, 0.6), "lens": 28.0, "fstop": 5.6}
E_B = {"rel": "world", "loc": (-1.1, 3.6, 1.3), "target": (-1.9, -1.2, 0.6), "lens": 28.0, "fstop": 5.6}
F = {"rel": "world", "loc": (-7.2, 0.0, 0.6), "target": (-1.9, 0.6, -0.2), "lens": 30.0, "fstop": 5.6}
F_B = {"rel": "world", "loc": (-6.8, 0.4, 0.5), "target": (-1.9, 0.7, -0.25), "lens": 30.0, "fstop": 5.6}
G = {"rel": "world", "loc": (-6.5, -1.4, 1.3), "target": (-1.9, -1.6, 0.9), "lens": 24.0, "fstop": 8.0}
G_B = {"rel": "world", "loc": (-6.2, -1.0, 1.25), "target": (-1.9, -1.5, 0.9), "lens": 24.0, "fstop": 8.0}
H = {"rel": "world", "loc": (10.0, -3.5, 2.0), "target": (1.9, -2.5, 1.3), "lens": 26.0, "fstop": 8.0}
H_B = {"rel": "world", "loc": (9.4, -3.0, 1.9), "target": (1.9, -2.4, 1.3), "lens": 26.0, "fstop": 8.0}
I = {"rel": "world", "loc": (3.6, 6.5, 2.6), "target": (-1.9, -2.5, 0.6), "lens": 26.0, "fstop": 8.0}

CUT = {"cut": True}
# label, variant, start (line, or (line, absolute second)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-slam", "car", 1, [(0.0, OPEN_SIM), (2.17, 0.55)], A1, A1_B, {}, (1,)),      # held through line 1 (hook rule): nose crushes, rear lifts
    ("B-rises-in-a-second", "car", 2, [(0.0, -4.4), (4.26, -0.14)], B, B_B, {}, (2,)),
    ("C1-pit", "car", 3, [(0.0, -9.0), (2.17, -8.0)], C1, C1_B, dict(CUT), (3,)),
    ("C2-hinge", "car", (3, 8.60), [(0.0, -8.0), (2.19, -7.0)], C2, C2_B, dict(CUT), (3,)),
    ("D-pistons", "car", 4, [(0.0, -1.45), (4.24, -0.15)], D, D_B, dict(CUT), (4,)),
    ("E-hits-the-steel", "car", 5, [(0.0, -0.12), (2.67, 0.09)], E, E_B, {}, (5,)),
    ("F-into-the-concrete", "car", 6, [(0.0, 0.0), (3.81, 0.07)], F, F_B, dict(CUT, force=True), (6,)),
    ("G-back-end-flips", "car", 7, [(0.0, 0.0), (3.5, 1.45)], G, G_B, {}, (7,)),
    ("H-truck", "truck", 8, [(0.0, -0.45), (3.62, 0.9)], H, H_B, {}, (8,)),
    ("I-loop", "car", 9, [(0.0, -2.2), (3.287, OPEN_SIM - 0.002)], I, A1, {"loop": True}, (9,)),
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
