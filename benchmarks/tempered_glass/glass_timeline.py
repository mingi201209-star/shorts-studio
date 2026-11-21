"""EP.14 film timeline (pure data). Applies the competitor research (docs/competitor-analysis-2026-11-21.md): first cut at 1.3 s, a new
shot about every 2.5 s, one question, narration about 170 words a minute, an everyday mystery, no text on the picture but the captions.
Every shot maps film time to simulated time through its own knots (film seconds from the shot start -> simulated seconds after the hit),
so one shot can run the crack front at 1/6,000 speed and the next one the falling cubes at a third of real time. The last shot runs the
hammer into the glass from the opening camera and ends on the opening moment, so the Short loops."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.020
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep14-audio/audio-validation.json"
LAB = (200.0, 0.0, 0.0)                 # the factory and test rigs, far from the car

# rel "car" = car frame (the car stands still at the origin); rel "lab", "slab", "rig" = lab sites
A1 = {"rel": "car", "loc": (-1.40, -0.20, 1.12), "target": (-0.62, 0.36, 1.00), "lens": 30.0, "fstop": 4.0}
A1_B = {"rel": "car", "loc": (-1.28, -0.10, 1.10), "target": (-0.62, 0.36, 1.00), "lens": 31.0, "fstop": 4.0}
A2 = {"rel": "car", "loc": (-1.55, -0.45, 0.22), "target": (-0.85, 0.40, 0.42), "lens": 28.0, "fstop": 3.5}
A2_B = {"rel": "car", "loc": (-1.45, -0.25, 0.20), "target": (-0.85, 0.45, 0.40), "lens": 29.0, "fstop": 3.5}
B = {"rel": "lab", "loc": (0.95, 1.30, 0.98), "target": (0.0, 0.25, 0.46), "lens": 26.0, "fstop": 5.6}
B_B = {"rel": "lab", "loc": (0.85, 1.20, 0.90), "target": (0.0, 0.40, 0.46), "lens": 27.0, "fstop": 5.6}
C = {"rel": "slab", "loc": (0.55, -1.75, 1.15), "target": (0.0, 0.0, 0.80), "lens": 35.0, "fstop": 8.0}
C_B = {"rel": "slab", "loc": (0.35, -1.55, 1.05), "target": (0.0, 0.0, 0.80), "lens": 36.0, "fstop": 8.0}
D = {"rel": "rig", "loc": (0.62, -0.52, 0.86), "target": (0.0, 0.0, 0.78), "lens": 34.0, "fstop": 5.6}
D_B = {"rel": "rig", "loc": (0.55, -0.46, 0.82), "target": (0.0, 0.0, 0.76), "lens": 35.0, "fstop": 5.6}
E1 = {"rel": "car", "loc": (-1.05, 0.02, 1.05), "target": (-0.60, 0.33, 1.02), "lens": 32.0, "fstop": 4.0}
E1_B = {"rel": "car", "loc": (-0.95, 0.10, 1.04), "target": (-0.60, 0.33, 1.02), "lens": 34.0, "fstop": 4.0}
E2 = {"rel": "car", "loc": (-0.90, 0.20, 1.06), "target": (-0.60, 0.31, 1.02), "lens": 40.0, "fstop": 2.8}
E2_B = {"rel": "car", "loc": (-0.86, 0.23, 1.05), "target": (-0.60, 0.31, 1.02), "lens": 42.0, "fstop": 2.8}
F = {"rel": "car", "loc": (-2.6, 0.45, 1.06), "target": (-0.60, 0.40, 1.02), "lens": 40.0, "fstop": 8.0}
F_B = {"rel": "car", "loc": (-2.2, 0.42, 1.04), "target": (-0.60, 0.40, 1.02), "lens": 42.0, "fstop": 8.0}
G1 = {"rel": "car", "loc": (-2.75, 0.20, 0.13), "target": (-1.55, 0.45, 0.03), "lens": 45.0, "fstop": 2.8}
G1_B = {"rel": "car", "loc": (-2.60, 0.30, 0.12), "target": (-1.50, 0.45, 0.03), "lens": 47.0, "fstop": 2.8}
G2 = {"rel": "car", "loc": (-2.0, 1.25, 1.2), "target": (-0.70, 0.35, 0.85), "lens": 30.0, "fstop": 5.6}
G2_B = {"rel": "car", "loc": (-1.85, 1.10, 1.15), "target": (-0.70, 0.35, 0.85), "lens": 31.0, "fstop": 5.6}
H = {"rel": "car", "loc": (1.30, 2.90, 1.45), "target": (0.25, 0.70, 1.05), "lens": 35.0, "fstop": 5.6}
H_B = {"rel": "car", "loc": (1.15, 2.60, 1.40), "target": (0.25, 0.70, 1.05), "lens": 37.0, "fstop": 5.6}
I = {"rel": "car", "loc": (-1.08, -0.08, 1.08), "target": (-0.60, 0.33, 1.02), "lens": 34.0, "fstop": 4.0}
I_B = {"rel": "car", "loc": (-1.00, -0.02, 1.07), "target": (-0.60, 0.33, 1.02), "lens": 35.0, "fstop": 4.0}
N = {"rel": "car", "loc": (-1.55, -0.32, 1.14), "target": (-0.62, 0.36, 1.00), "lens": 29.0, "fstop": 4.0}

# label, variant, start (line number, or (line, absolute second)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-burst", "tempered", 1, [(0.0, OPEN_SIM), (1.3, 0.080)], A1, A1_B, {}, (1,)),
    ("A2-raining-cubes", "tempered", (1, 1.30), [(0.0, 0.080), (1.67, 0.70)], A2, A2_B, {}, (1,)),
    ("B-tempering", "quench", 2, [(0.0, -0.9), (4.18, 2.6)], B, B_B, {}, (2,)),
    ("C1-surface-sets", "section", 3, [(0.0, 0.0), (1.78, 0.75)], C, C_B, {}, (3,)),
    ("C2-core-squeezes", "section", (3, 8.93), [(0.0, 0.75), (4.03, 6.0)], C_B, C, {"arrows": True}, (3,)),
    ("D-four-times", "ball", 4, [(0.0, 0.15), (3.55, 1.35)], D, D_B, {}, (4,)),
    ("E1-locked-in", "tempered", 5, [(0.0, -0.40), (2.27, -0.06)], E1, E1_B, {"stress_glow": True}, (5,)),
    ("E2-lets-go", "tempered", (5, 18.78), [(0.0, -0.06), (0.8, 0.0), (2.84, 0.00034)], E2, E2_B, {"cracks": True}, (5,)),
    ("F-mile-per-second", "tempered", 6, [(0.0, 0.0), (2.2, 0.00032), (3.34, 0.004)], F, F_B, {"cracks": True}, (6,)),
    ("G1-blunt-cubes", "tempered", 7, [(0.0, 0.25), (1.9, 0.95)], G1, G1_B, {}, (7,)),
    ("G2-knife-shards", "annealed", (7, 26.86), [(0.0, 0.03), (1.23, 0.50)], G2, G2_B, {}, (7,)),
    ("H-windshield", "windshield", 8, [(0.0, -0.03), (0.8, 0.0), (3.6, 0.00026), (4.54, 0.0003)], H, H_B, {}, (8,)),
    ("I-hammer", "tempered", 9, [(0.0, -0.55), (2.14, -0.15)], I, I_B, {}, (9,)),
    ("N-loop-run-in", "tempered", (9, None), [(0.0, -0.10), (0.6, 0.0), (1.0, 0.020)], N, A1, {"loop": True}, (9,)),
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
            starts.append(total - 1.0)          # loop run-in: the last second
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
    """The research rules as a gate: first cut by 1.5 s, at least 18 cuts a minute, 160-200 words a minute, at most 40 s."""
    a = _audio()
    words = sum(len(b["narration_en"].split()) for b in a["beats"])
    secs = total_seconds()
    wpm = 60 * words / a["seconds"]
    cuts = 60 * len(segs) / secs
    problems = []
    if segs[1]["t0"] > 1.5:
        problems.append(f"first cut at {segs[1]['t0']:.2f} s (rule: by 1.5 s)")
    if cuts < 18:
        problems.append(f"{cuts:.0f} cuts a minute (rule: at least 18)")
    if not 160 <= wpm <= 200:
        problems.append(f"narration at {wpm:.0f} words a minute (rule: 160-200)")
    if secs > 40:
        problems.append(f"{secs:.1f} s long (rule: at most 40)")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_cut_s": round(segs[1]["t0"], 2), "cuts_per_min": round(cuts, 1),
            "wpm": round(wpm), "seconds": secs}
