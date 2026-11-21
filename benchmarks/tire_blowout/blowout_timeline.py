"""EP.16 film timeline (pure data), built like EP.14/EP.15 (docs/episode-playbook.md) with the still-frame rule from EP.15's data: frame 1
is rubber already flying off the burst tyre against the sky, from a low side view. Simulated time t = seconds after the burst; every
shot maps film time to simulated time through its own knots. Long-before shots shift the car along the road (y_shift, a multiple of
the lane-dash spacing) so it stays near the scenery; the heat shots may run the car's pose at another rate than the tyre's ageing
(pose_rate). rel "wheel" = the front-left wheel centre (no rotation); rel "car" = car centre (no rotation)."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.12
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep16-audio/audio-validation.json"
DASH = 12.0

A1 = {"rel": "wheel", "loc": (-1.25, 0.60, 0.12), "target": (0.0, -0.35, 0.42), "lens": 24.0, "fstop": 4.0}
A1_B = {"rel": "wheel", "loc": (-1.15, 0.35, 0.15), "target": (0.0, -0.50, 0.45), "lens": 24.0, "fstop": 4.0}
A2 = {"rel": "car", "loc": (-6.0, 7.0, 2.6), "target": (0.0, -3.0, 0.3), "lens": 28.0, "fstop": 8.0}
A2_B = {"rel": "car", "loc": (-5.5, 5.5, 2.2), "target": (0.0, -4.0, 0.3), "lens": 28.0, "fstop": 8.0}
B = {"rel": "wheel", "loc": (-0.55, 1.45, -0.12), "target": (-0.05, 0.0, -0.10), "lens": 32.0, "fstop": 4.0}
B_B = {"rel": "wheel", "loc": (-0.75, 1.25, -0.12), "target": (-0.05, 0.0, -0.10), "lens": 32.0, "fstop": 4.0}
C1 = {"rel": "wheel", "loc": (-1.0, 0.0, 0.02), "target": (0.0, 0.0, -0.05), "lens": 40.0, "fstop": 4.0}
C1_B = {"rel": "wheel", "loc": (-0.95, 0.25, 0.06), "target": (0.0, 0.0, -0.06), "lens": 40.0, "fstop": 4.0}
C2 = {"rel": "wheel", "loc": (-0.60, 0.78, 0.12), "target": (-0.03, 0.18, -0.06), "lens": 32.0, "fstop": 4.0}
C2_B = {"rel": "wheel", "loc": (-0.50, 0.80, 0.08), "target": (-0.03, 0.18, -0.07), "lens": 34.0, "fstop": 4.0}
D1 = {"rel": "car", "loc": (-3.6, 3.2, 0.6), "target": (0.0, 1.3, 0.3), "lens": 30.0, "fstop": 5.6}
D1_B = {"rel": "car", "loc": (-3.3, 2.2, 0.55), "target": (0.0, 1.3, 0.3), "lens": 32.0, "fstop": 5.6}
D2 = {"rel": "wheel", "loc": (-1.1, -0.6, 0.08), "target": (0.0, 0.1, -0.02), "lens": 38.0, "fstop": 4.0}
D2_B = {"rel": "wheel", "loc": (-1.0, -0.35, 0.06), "target": (0.0, 0.1, -0.03), "lens": 38.0, "fstop": 4.0}
E = {"rel": "wheel", "loc": (-1.05, 0.85, 0.32), "target": (0.0, 0.05, 0.0), "lens": 34.0, "fstop": 4.0}
E_B = {"rel": "wheel", "loc": (-0.85, 0.80, 0.22), "target": (0.0, 0.08, 0.0), "lens": 36.0, "fstop": 4.0}
F = {"rel": "wheel", "loc": (-0.55, 0.62, 0.30), "target": (-0.02, 0.17, 0.12), "lens": 40.0, "fstop": 4.0}
F_B = {"rel": "wheel", "loc": (-0.48, 0.55, 0.26), "target": (-0.02, 0.19, 0.13), "lens": 42.0, "fstop": 4.0}
G1 = {"rel": "wheel", "loc": (-0.85, 0.75, 0.05), "target": (0.0, 0.0, 0.05), "lens": 30.0, "fstop": 4.0}
G1_B = {"rel": "wheel", "loc": (-0.80, 0.50, 0.05), "target": (0.0, 0.0, 0.05), "lens": 30.0, "fstop": 4.0}
G2 = {"rel": "wheel", "loc": (-1.6, 1.7, 0.75), "target": (0.0, -0.4, 0.35), "lens": 34.0, "fstop": 5.6}
G2_B = {"rel": "wheel", "loc": (-1.7, 1.3, 0.60), "target": (0.0, -0.7, 0.35), "lens": 34.0, "fstop": 5.6}
H = {"rel": "car", "loc": (-3.2, 3.6, 0.6), "target": (0.0, 1.3, 0.2), "lens": 32.0, "fstop": 5.6}
H_B = {"rel": "car", "loc": (-2.5, 2.7, 0.45), "target": (0.0, 1.3, 0.18), "lens": 34.0, "fstop": 5.6}
I1 = {"rel": "world", "loc": (-4.6, -6.0, 1.30), "target": (-3.4, -22.0, 0.0), "lens": 30.0, "fstop": 5.6}
I1_B = {"rel": "world", "loc": (-4.7, -7.5, 1.15), "target": (-3.2, -24.0, 0.0), "lens": 30.0, "fstop": 5.6}
I2 = {"rel": "wheel", "loc": (-1.9, 1.8, 0.30), "target": (0.0, -0.2, 0.40), "lens": 24.0, "fstop": 4.0}

CUT = {"cut": (50.0, 130.0)}
# label, variant, start (line, or (line, absolute second)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-burst", "road", 1, [(0.0, OPEN_SIM), (1.3, 0.22)], A1, A1_B, {}, (1,)),
    ("A2-debris", "road", (1, 1.30), [(0.0, 0.22), (2.1, 1.6)], A2, A2_B, {}, (1, 2)),
    ("B-a-little-low", "road", (2, 3.40), [(0.0, -40.0), (2.22, -38.0)], B, B_B, {}, (2,)),
    ("C1-sidewall-bends", "road", 3, [(0.0, -30.0), (2.38, -29.97)], C1, C1_B, {}, (3,)),
    ("C2-springs-back", "road", (3, 8.00), [(0.0, -20.0), (2.53, -19.965)], C2, C2_B, dict(CUT), (3,)),
    ("D1-sixty", "road", 4, [(0.0, -15.0), (2.07, -12.93)], D1, D1_B, {}, (4,)),
    ("D2-fifteen-a-second", "road", (4, 12.60), [(0.0, -10.0), (1.98, -9.9)], D2, D2_B, dict(CUT), (4,)),
    ("E-heat", "road", 5, [(0.0, -1500.0), (3.66, -120.0)], E, E_B, dict(CUT, heat=True, pose_rate=0.05), (5,)),
    ("F-cooks-the-glue", "road", 6, [(0.0, -3.0), (3.68, -0.62)], F, F_B, dict(CUT, heat=True, pose_rate=0.05), (6,)),
    ("G1-tread-peels", "road", 7, [(0.0, -0.5), (1.98, -0.05)], G1, G1_B, {}, (7,)),
    ("G2-bursts", "road", (7, 23.90), [(0.0, -0.05), (1.94, 0.22)], G2, G2_B, {}, (7,)),
    ("H-a-pound-a-month", "parked", 8, [(0.0, 0.0), (3.39, 11.0)], H, H_B, {}, (8,)),
    ("I1-shreds", "road", 9, [(0.0, -1.8), (1.4, -0.9)], I1, I1_B, {}, (9,)),
    ("I2-loop", "road", (9, 30.63), [(0.0, -0.75), (1.58, OPEN_SIM - 0.002)], I2, A1, {"loop": True}, (9,)),
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
        y0 = 26.8224 * seg["sim0"]
        seg["y_shift"] = 0.0 if seg["sim0"] > -3.0 or variant == "parked" else round((y0 + 60.0) / DASH) * DASH      # keep the car near the scenery
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
    sim = sim_time(seg, t)
    rate = seg["flags"].get("pose_rate")
    pose_t = sim if rate is None else seg["sim0"] + rate * (t - seg["t0"])
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "pose_t": pose_t, "y_shift": seg["y_shift"],
          "cam": cam, "u": u}
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
