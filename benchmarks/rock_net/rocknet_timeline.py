"""EP.21 film timeline (pure data), built like EP.20: frame 1 is the boulder already in the ring net, the net bulging down the slope
around it, posts leaning, chips and dust in the air, the whole middle span in frame, held through the first line (hook rule).
Simulated time t: seconds after the rock first touches the net (variant "catch"); in the "restore" time-lapse t is the fraction of
the clean-up done (0..1). rel "world" only."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.rock_net import rocknet_motion as rm

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.16
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep21-audio/audio-validation.json"
XB, ZB = rm.X_B, rm.Z_B

A1 = {"rel": "world", "loc": (14.2, -7.0, 15.4), "target": (19.9, 0.3, 14.8), "lens": 20.0, "fstop": 8.0}        # hero: the boulder in the net pocket, the whole span
A1_B = {"rel": "world", "loc": (14.6, -6.6, 15.35), "target": (19.9, 0.3, 14.8), "lens": 20.0, "fstop": 8.0}
B = {"rel": "world", "loc": (-14.0, -30.0, 9.0), "target": (12.0, 0.0, 15.5), "lens": 28.0, "fstop": 8.0}
B_B = {"rel": "world", "loc": (-13.0, -27.0, 9.0), "target": (12.0, 0.0, 15.5), "lens": 28.0, "fstop": 8.0}
C = {"rel": "world", "loc": (XB - 1.3, 1.4, ZB + 2.2), "target": (XB, 0.6, ZB + 2.6), "lens": 30.0, "fstop": 4.0}
C_B = {"rel": "world", "loc": (XB - 1.1, 1.3, ZB + 2.25), "target": (XB, 0.5, ZB + 2.6), "lens": 30.0, "fstop": 4.0}
D = {"rel": "world", "loc": (XB - 6.5, -15.0, ZB + 2.5), "target": (XB - 4.0, 0.0, ZB + 0.5), "lens": 26.0, "fstop": 8.0}
D_B = {"rel": "world", "loc": (XB - 6.5, -14.0, ZB + 2.4), "target": (XB - 4.0, 0.0, ZB + 0.5), "lens": 26.0, "fstop": 8.0}
E = {"rel": "world", "loc": (XB - 3.0, -10.0, ZB + 9.0), "target": (XB - 4.5, 0.0, ZB + 0.5), "lens": 26.0, "fstop": 8.0}
E_B = {"rel": "world", "loc": (XB - 3.0, -9.0, ZB + 8.6), "target": (XB - 4.5, 0.0, ZB + 0.5), "lens": 26.0, "fstop": 8.0}
F = {"rel": "world", "loc": (24.5, -9.5, 19.2), "target": (26.0, -5.0, 18.9), "lens": 24.0, "fstop": 8.0}          # retaining rope down to its brake
F_B = {"rel": "world", "loc": (25.0, -9.2, 19.3), "target": (26.4, -5.0, 18.95), "lens": 24.0, "fstop": 8.0}
G = {"rel": "world", "loc": (27.6, -6.3, 19.4), "target": (27.6, -5.0, 19.25), "lens": 45.0, "fstop": 5.6}         # the brake loop face-on
G_B = {"rel": "world", "loc": (27.6, -6.15, 19.38), "target": (27.6, -5.0, 19.22), "lens": 45.0, "fstop": 5.6}
H = {"rel": "world", "loc": (XB - 9.5, -8.5, ZB + 1.5), "target": (XB - 3.5, 0.0, ZB + 0.8), "lens": 24.0, "fstop": 8.0}
H_B = {"rel": "world", "loc": (XB - 9.0, -7.8, ZB + 1.6), "target": (XB - 3.5, 0.0, ZB + 0.8), "lens": 24.0, "fstop": 8.0}
I = {"rel": "world", "loc": (14.0, -4.8, 10.8), "target": (17.6, 0.2, 13.4), "lens": 20.0, "fstop": 8.0}         # below the caught rock, looking up
I_B = {"rel": "world", "loc": (14.3, -4.4, 10.9), "target": (17.6, 0.2, 13.5), "lens": 20.0, "fstop": 8.0}
J = {"rel": "world", "loc": (XB - 8.0, -9.0, ZB + 3.0), "target": (XB - 1.0, 0.0, ZB + 2.0), "lens": 24.0, "fstop": 8.0}
J_B = {"rel": "world", "loc": (XB - 7.5, -8.2, ZB + 3.0), "target": (XB - 1.0, 0.0, ZB + 2.0), "lens": 24.0, "fstop": 8.0}
K = {"rel": "world", "loc": (9.0, -11.0, 13.0), "target": (19.5, 0.0, 15.0), "lens": 22.0, "fstop": 8.0}         # loop into A1

CAR = {"y0": 26.0, "v": -14.0}
# label, variant, start line, knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-boulder-in-the-net", "catch", 1, [(0.0, OPEN_SIM), (2.309, 0.58)], A1, A1_B, {}, (1,)),          # held through line 1 (hook rule)
    ("B-nets-above-the-road", "catch", 2, [(0.0, -2.6), (3.043, -0.2)], B, B_B, {"car": CAR}, (2,)),
    ("C-chain-mail-rings", "catch", 3, [(0.0, -0.55), (3.147, -0.12)], C, C_B, {}, (3,)),
    ("D-not-stopped-dead", "catch", 4, [(0.0, -0.25), (3.134, 0.42)], D, D_B, {}, (4,)),
    ("E-stretches-twenty-feet", "catch", 5, [(0.0, 0.02), (3.134, 0.62)], E, E_B, {"ghost": True}, (5,)),
    ("F-brake-rings", "catch", 6, [(0.0, 0.04), (2.657, 0.20)], F, F_B, {}, (6,)),
    ("G-loops-shrink-heat", "catch", 7, [(0.0, 0.12), (4.203, 0.56)], G, G_B, {}, (7,)),
    ("H-nothing-snaps", "catch", 8, [(0.0, 0.40), (3.559, 1.6)], H, H_B, {}, (8,)),
    ("I-twenty-tons-sixty-mph", "catch", 9, [(0.0, 1.8), (3.507, 4.0)], I, I_B, {}, (9,)),
    ("J-replace-the-brakes", "restore", 10, [(0.0, 0.0), (0.3, 0.0), (3.3, 1.0)], J, J_B, {}, (10,)),
    ("K-loop", "catch", 11, [(0.0, -0.75), (2.9755, OPEN_SIM - 0.0002)], K, A1, {"loop": True, "car": CAR}, (11,)),   # last frame = the opening
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
    t = [s[r[2] - 1] for r in ROWS] + [total]
    out = []
    for i, (label, variant, _, knots, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        seg = {"label": label, "variant": variant, "t0": t0, "t1": t1, "knots": knots, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines}
        seg["sim0"], seg["sim1"] = sim_time(seg, t0), sim_time(seg, t1 - 1e-6)
        seg["time_scale"] = round((seg["sim1"] - seg["sim0"]) / (t1 - t0), 6)
        out.append(seg)
    return out


def sim_time(seg: dict, film_t: float) -> float:
    """Piecewise-linear map through the shot's knots, extended with the last slope (held for the restore fraction)."""
    tau = film_t - seg["t0"]
    k = seg["knots"]
    if tau <= k[0][0]:
        return k[0][1]
    for (a, sa), (b, sb) in zip(k[:-1], k[1:]):
        if tau <= b:
            return sa + (sb - sa) * (tau - a) / (b - a)
    if seg["variant"] == "restore":
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
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": cam, "u": u, "shot_sim0": seg["sim0"]}
    st.update(seg["flags"])
    return st


def car_y(sh: dict) -> float | None:
    c = sh.get("car")
    if not c:
        return None
    return c["y0"] + c["v"] * (sh["t"] - sh["shot_sim0"]) if sh["variant"] == "catch" else None


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
