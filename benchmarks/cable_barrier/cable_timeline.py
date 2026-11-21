"""EP.15 film timeline (pure data), built like EP.14 (docs/episode-playbook.md): first cut at 1.3 s, a shot about every 3 s, one
question, no text but the captions. Simulated time t = seconds after the car's front corner first touches the ropes; every shot maps
film time to simulated time through its own knots. World coordinates are the model's mirrored in x (the car's lanes on the right of the
median, as on a US divided highway). The last shot runs a fresh barrier into the opening moment from the opening camera (loop)."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.12
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep15-audio/audio-validation.json"

# rel "world" = render world; rel "car" = car centre (no rotation)
A1 = {"rel": "world", "loc": (-2.3, 6.4, 0.85), "target": (-0.6, 2.6, 0.62), "lens": 40.0, "fstop": 4.0}
A1_B = {"rel": "world", "loc": (-2.2, 6.9, 0.80), "target": (-0.8, 3.2, 0.62), "lens": 40.0, "fstop": 4.0}
A2 = {"rel": "world", "loc": (-7.5, 15.5, 5.2), "target": (-0.3, 4.5, 0.4), "lens": 26.0, "fstop": 8.0}
A2_B = {"rel": "world", "loc": (-7.0, 14.0, 4.6), "target": (-0.4, 5.5, 0.4), "lens": 27.0, "fstop": 8.0}
B = {"rel": "car", "loc": (4.0, -10.0, 4.2), "target": (-5.0, 14.0, 0.3), "lens": 24.0, "fstop": 11.0}
B_B = {"rel": "car", "loc": (3.4, -8.5, 3.6), "target": (-10.0, 12.0, 0.3), "lens": 25.0, "fstop": 11.0}
C = {"rel": "world", "loc": (1.3, 22.0, 0.75), "target": (0.0, 32.0, 0.6), "lens": 30.0, "fstop": 4.0}
C_B = {"rel": "world", "loc": (1.1, 17.0, 0.70), "target": (0.0, 27.0, 0.6), "lens": 30.0, "fstop": 4.0}
D = {"rel": "world", "loc": (-2.3, -2.2, 0.60), "target": (0.6, 2.6, 0.50), "lens": 24.0, "fstop": 4.0}
D_B = {"rel": "world", "loc": (-2.2, -1.8, 0.55), "target": (0.3, 3.2, 0.50), "lens": 25.0, "fstop": 4.0}
E = {"rel": "world", "loc": (-6.0, 1.0, 9.0), "target": (-0.5, 6.5, 0.0), "lens": 28.0, "fstop": 11.0}
E_B = {"rel": "world", "loc": (-6.5, 3.0, 9.5), "target": (-0.5, 7.0, 0.0), "lens": 28.0, "fstop": 11.0}
F = {"rel": "car", "loc": (-5.2, 2.5, 1.6), "target": (0.0, 1.5, 0.6), "lens": 28.0, "fstop": 5.6}
F_B = {"rel": "car", "loc": (-5.0, 3.5, 1.5), "target": (0.0, 2.0, 0.6), "lens": 29.0, "fstop": 5.6}
G = {"rel": "car", "loc": (-10.0, -7.0, 8.5), "target": (0.0, 4.0, 0.0), "lens": 26.0, "fstop": 11.0}
G_B = {"rel": "car", "loc": (-10.5, -4.0, 8.0), "target": (0.0, 5.0, 0.0), "lens": 26.0, "fstop": 11.0}
H = {"rel": "world", "loc": (-3.0, 17.0, 1.1), "target": (-0.8, 9.0, 0.6), "lens": 32.0, "fstop": 4.0}
H_B = {"rel": "world", "loc": (-2.6, 15.6, 0.9), "target": (-0.9, 10.0, 0.6), "lens": 34.0, "fstop": 4.0}
I = {"rel": "world", "loc": (-6.0, 22.0, 2.4), "target": (2.0, -6.0, 0.5), "lens": 24.0, "fstop": 8.0}

# label, variant, start (line, or (line, absolute second)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-caught", "crash", 1, [(0.0, OPEN_SIM), (1.3, 0.22)], A1, A1_B, {}, (1,)),
    ("A2-slingshot", "crash", (1, 1.30), [(0.0, 0.22), (1.95, 0.45)], A2, A2_B, {}, (1,)),
    ("B-oncoming", "crash", 2, [(0.0, -2.2), (3.93, -0.12)], B, B_B, {}, (2,)),
    ("C-ropes", "crash", 3, [(0.0, -8.0), (3.55, -7.5)], C, C_B, {}, (3,)),
    ("D-posts-fold", "crash", 4, [(0.0, -0.06), (2.77, 0.14)], D, D_B, {}, (4,)),
    ("E-eight-feet", "crash", 5, [(0.0, 0.0), (3.36, 0.44)], E, E_B, {}, (5,)),
    ("F-gently", "crash", 6, [(0.0, 0.15), (3.68, 1.2)], F, F_B, {}, (6,)),
    ("G-steers-back", "crash", 7, [(0.0, 0.9), (4.5, 5.0)], G, G_B, {}, (7,)),
    ("H-steel-net", "crash", 8, [(0.0, 0.36), (2.4, 0.50)], H, H_B, {}, (8,)),
    ("I-loop", "crash", 9, [(0.0, -2.4), (3.21, OPEN_SIM)], I, A1, {"loop": True}, (9,)),
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
