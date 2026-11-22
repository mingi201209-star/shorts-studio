"""EP.20 film timeline (pure data), built like EP.16-EP.19 v2: frame 1 is the box truck already under the crash beam, its roof skin
rolling up against the beam, the whole truck in frame, held through the first line (hook rule). Simulated time t: seconds after the
front of the box meets the beam (variants "old" and "raised"); seconds after the box crosses the detector beam ("warned"); the raise
fraction 0..1 ("raising"). rel "truck" = the box front at road level (x = the lane centre); rel "world" = render world."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.can_opener import opener_motion as om
from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.40
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep20-audio/audio-validation.json"

A1 = {"rel": "world", "loc": (-2.5, -6.4, 4.85), "target": (1.5, -0.4, 3.0), "lens": 19.0, "fstop": 8.0}         # hero: whole truck, beam, bridge, the roof tearing open
A1_B = {"rel": "world", "loc": (-2.2, -5.9, 4.75), "target": (1.5, -0.2, 3.05), "lens": 19.0, "fstop": 8.0}
B = {"rel": "world", "loc": (-1.6, -14.5, 2.0), "target": (0.4, 0.0, 4.6), "lens": 28.0, "fstop": 8.0}         # rail bridge, train above, the truck drives in
B_B = {"rel": "world", "loc": (-1.6, -13.3, 2.05), "target": (0.4, 0.0, 4.6), "lens": 28.0, "fstop": 8.0}
C = {"rel": "world", "loc": (-3.6, -5.2, 5.6), "target": (1.6, -0.2, 3.8), "lens": 28.0, "fstop": 8.0}         # the beam takes the hit
C_B = {"rel": "world", "loc": (-3.3, -4.6, 5.4), "target": (1.6, -0.1, 3.8), "lens": 28.0, "fstop": 8.0}
D = {"rel": "truck", "loc": (-2.6, -8.4, 6.1), "target": (0.0, -3.2, 3.8), "lens": 30.0, "fstop": 8.0}         # x-ray roof: skin over bows
D_B = {"rel": "truck", "loc": (-2.2, -7.6, 5.7), "target": (0.0, -3.0, 3.8), "lens": 30.0, "fstop": 8.0}
E = {"rel": "world", "loc": (-1.3, -3.0, 5.0), "target": (0.6, -0.4, 4.0), "lens": 30.0, "fstop": 5.6}         # rivets pop, roof rolls
E_B = {"rel": "world", "loc": (-1.1, -2.6, 4.9), "target": (0.6, -0.3, 4.05), "lens": 30.0, "fstop": 5.6}
F = {"rel": "world", "loc": (-4.3, -3.6, 2.4), "target": (1.8, 1.2, 2.9), "lens": 20.0, "fstop": 8.0}          # the cab rolls under, headroom above it
F_B = {"rel": "world", "loc": (-4.2, -3.2, 2.4), "target": (1.8, 1.4, 2.9), "lens": 20.0, "fstop": 8.0}
G = {"rel": "world", "loc": (-3.0, -7.2, 3.56), "target": (1.8, -2.6, 3.56), "lens": 20.0, "fstop": 8.0}       # level with the beam: the glowing band is what cannot pass
G_B = {"rel": "world", "loc": (-3.0, -6.6, 3.56), "target": (1.8, -2.2, 3.56), "lens": 20.0, "fstop": 8.0}
H = {"rel": "world", "loc": (-2.0, -53.0, 6.0), "target": (1.6, -36.0, 3.8), "lens": 30.0, "fstop": 8.0}        # detector ray, warning, red light
H_B = {"rel": "world", "loc": (-1.9, -51.5, 5.8), "target": (1.6, -34.0, 3.8), "lens": 30.0, "fstop": 8.0}
I = {"rel": "world", "loc": (-3.2, -5.0, 2.8), "target": (-5.2, 1.0, 3.9), "lens": 24.0, "fstop": 8.0}         # the 2019 raise at the abutment
I_B = {"rel": "world", "loc": (-3.2, -4.6, 2.85), "target": (-5.2, 1.0, 3.95), "lens": 24.0, "fstop": 8.0}
J = {"rel": "world", "loc": (5.6, -9.0, 4.8), "target": (1.3, -0.6, 3.7), "lens": 26.0, "fstop": 8.0}          # still hits, 8 in
J_B = {"rel": "world", "loc": (5.3, -8.2, 4.6), "target": (1.3, -0.4, 3.7), "lens": 26.0, "fstop": 8.0}
K = {"rel": "world", "loc": (-3.6, -10.5, 5.6), "target": (1.2, -1.6, 3.0), "lens": 20.0, "fstop": 8.0}        # loop into A1

# label, variant, start (line, or (line, absolute second)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-peeled-like-a-can", "old", 1, [(0.0, OPEN_SIM), (2.489, 1.00)], A1, A1_B, {}, (1,)),        # held through line 1 (hook rule)
    ("B-rail-bridge", "old", 2, [(0.0, -3.4), (2.593, -0.807)], B, B_B, {"train": True, "sedan": True}, (2,)),
    ("C-beam-takes-the-hit", "old", 3, [(0.0, -0.45), (3.263, 0.55)], C, C_B, {}, (3,)),
    ("D-thinner-than-a-dime", "old", 4, [(0.0, -0.95), (2.85, -0.25)], D, D_B, {"xray": True}, (4,)),
    ("E-rivets-pop", "old", 5, [(0.0, 0.16), (3.868, 0.62)], E, E_B, {}, (5,)),
    ("F-cab-rolls-under", "old", 6, [(0.0, -0.35), (3.134, 1.15)], F, F_B, {}, (6,)),
    ("G-sixteen-inches", "old", 7, [(0.0, -1.0), (3.353, -0.25)], G, G_B, {"band": True, "ghost": True}, (7,)),
    ("H-sensor-turns-it-red", "warned", 8, [(0.0, -0.9), (3.404, 2.504)], H, H_B, {}, (8,)),
    ("I-raised-eight-inches", "raising", 9, [(0.0, 0.0), (0.4, 0.0), (3.2, 1.0)], I, I_B, {"ghost": True}, (9,)),
    ("J-still-hits", "raised", 10, [(0.0, -0.35), (2.141, 0.55)], J, J_B, {}, (10,)),
    ("K-loop", "old", 11, [(0.0, -0.9), (1.89, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),     # last frame = the opening's moment
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
    """Piecewise-linear map through the shot's knots, extended with the last slope (held for the raise fraction)."""
    tau = film_t - seg["t0"]
    k = seg["knots"]
    if tau <= k[0][0]:
        return k[0][1]
    for (a, sa), (b, sb) in zip(k[:-1], k[1:]):
        if tau <= b:
            return sa + (sb - sa) * (tau - a) / (b - a)
    if seg["variant"] == "raising":
        return k[-1][1]
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
    sim = sim_time(seg, t)
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": cam, "u": u}
    st.update(seg["flags"])
    return st


def cam_world(sh: dict) -> tuple[float, float, float]:
    """Camera position in render-world coordinates."""
    x, y, z = sh["cam"]["loc"]
    if sh["cam"]["rel"] == "truck":
        return x + om.X_LANE, y + om.box_front_y(sh["t"], sh["variant"]), z
    return x, y, z


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
