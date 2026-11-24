"""EP.26 film timeline (pure data), built like EP.20-EP.25: frame 1 is the red sedan already pressed into the yellow rollers, the
rollers spinning and squashing, held through the first line (hook rule). Each row's knots are (share of the shot, simulated time);
the loop row's last knot lands exactly on the film's last frame. Simulated time t: seconds from the car's first touch on the barrier
(roller_motion; before it, the straight approach); variant 'roller' is the rolling barrier, 'steel' the plain steel rail, 'still' a
quiet road (no car). Cameras: rel 'world' = render world (the road along +y, the barrier face at x = 4.05 by the crash), rel 'car' =
from the car's reference point (not turned with it)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.roller_barrier import roller_motion as rm

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.10
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep26-audio/audio-validation.json"


def cam(rel, loc, target, lens, fstop=8.0):
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam("world", (5.3, 6.6, 3.0), (3.9, 1.8, 0.5), 33.0, 8.0)               # above the barrier, ahead: the car pressed into the spinning rollers
A1_B = cam("world", (5.4, 9.4, 3.3), (3.8, 4.4, 0.5), 33.0, 8.0)
B = cam("car", (-5.0, -15.0, 8.0), (2.5, 20.0, 0.0), 26.0, 11.0)                # drone behind the car: the sharp bend ahead lined with rollers
B_B = cam("car", (-4.6, -14.0, 7.6), (2.5, 21.0, 0.0), 26.0, 11.0)
C = cam("world", (3.3, 7.8, 1.5), (4.0, 1.6, 0.55), 30.0, 8.0)                 # a plain steel rail scrapes and drags (sparks)
C_B = cam("world", (3.4, 10.5, 1.7), (3.9, 4.0, 0.55), 30.0, 8.0)
D = cam("world", (3.05, 1.55, 1.05), (4.225, 2.475, 0.58), 40.0, 4.0)           # cut open: a roller is a barrel of foam on a steel post
D_B = cam("world", (3.1, 1.6, 1.02), (4.225, 2.475, 0.58), 40.0, 4.0)
E = cam("world", (0.2, 5.0, 3.6), (3.4, 0.6, 0.45), 28.0, 8.0)                 # from above: the car slides in, the rollers spin
E_B = cam("world", (0.35, 5.3, 3.5), (3.5, 1.0, 0.45), 28.0, 8.0)
F = cam("world", (4.05, 1.9, 2.9), (4.05, 1.91, 0.0), 32.0, 8.0)               # straight down on the rollers: the foam squashing
F_B = cam("world", (4.05, 2.5, 2.9), (4.05, 2.51, 0.0), 32.0, 8.0)
G = cam("world", (3.55, -2.6, 0.95), (4.1, 4.0, 0.5), 30.0, 5.6)               # behind: a row of rollers whirling
G_B = cam("world", (3.5, -2.2, 0.95), (4.1, 4.6, 0.5), 30.0, 5.6)
H1 = cam("car", (-3.4, -6.0, 1.6), (1.3, 3.0, 0.6), 28.0, 8.0)                 # alongside: the car keeps rolling forward
H1_B = cam("car", (-3.2, -6.4, 1.6), (1.3, 3.0, 0.6), 28.0, 8.0)
H2 = cam("car", (-2.2, -5.0, 9.5), (0.4, 5.0, 0.0), 24.0, 8.0)                 # from above: steered back toward its lane
H2_B = cam("car", (-2.0, -5.5, 9.8), (0.4, 5.0, 0.0), 24.0, 8.0)
I = cam("world", (0.3, 0.3, 12.0), (0.3, 0.31, 0.0), 22.0, 11.0)              # the 62 mph test: straight down, like a crash-test camera
I_B = I
J = cam("world", (2.6, 58.0, 4.2), (2.0, 100.0, 0.4), 30.0, 11.0)              # flying along a bend lined with rollers
J_B = cam("world", (2.4, 66.0, 4.0), (-0.5, 106.0, 0.4), 30.0, 11.0)
K = cam("world", (5.6, 12.0, 3.4), (2.0, -8.0, 0.6), 33.0, 8.0)               # loop: the car coming down to the bend, into frame 1

# label, variant, start line, knots [(share of the shot, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-pressed-into-rollers", "roller", 1, [(0.0, OPEN_SIM), (1.0, 0.24)], A1, A1_B, {}, (1,)),          # held through line 1
    ("B-korean-curve", "roller", 2, [(0.0, -2.4), (1.0, -0.7)], B, B_B, {}, (2,)),
    ("C-steel-scrapes", "steel", 3, [(0.0, -0.05), (1.0, 0.32)], C, C_B, {"sparks": True}, (3,)),
    ("D-foam-on-posts", "still", 4, [(0.0, -9.0), (1.0, -8.0)], D, D_B, {"section": True}, (4,)),
    ("E-rollers-spin", "roller", 5, [(0.0, -0.06), (1.0, 0.12)], E, E_B, {}, (5,)),
    ("F-foam-squashes", "roller", 6, [(0.0, 0.03), (1.0, 0.13)], F, F_B, {}, (6,)),
    ("G-crash-into-rotation", "roller", 7, [(0.0, 0.12), (1.0, 0.40)], G, G_B, {}, (7,)),
    ("H1-keeps-rolling", "roller", 8, [(0.0, 0.18), (1.0, 0.75)], H1, H1_B, {}, (8,)),
    ("H2-back-to-its-lane", "roller", 8.5, [(0.0, 0.55), (1.0, 2.6)], H2, H2_B, {}, (8,)),
    ("I-62-mph-test", "roller", 9, [(0.0, -0.35), (1.0, 0.55)], I, I_B, {}, (9,)),
    ("J-sixty-miles", "still", 10, [(0.0, -9.0), (1.0, -8.0)], J, J_B, {}, (10,)),
    ("K-loop", "roller", 11, [(0.0, -1.3), (0.70, -0.10), (0.85, 0.05), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),   # ramps into the
    # opening's slow motion; last frame = the opening
]


def _audio() -> dict:
    return json.loads(AUDIO.read_text())


def line_starts() -> list[float]:
    return [b["start"] for b in _audio()["beats"]]


def total_seconds() -> float:
    return round(_audio()["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def _start(s: list[float], line: float) -> float:
    """Shot start: a line's start, or part of the way through a line for a second shot on the same line (8.5: at "and is steered")."""
    k = int(line)
    if line == k:
        return s[k - 1]
    nxt = s[k] if k < len(s) else total_seconds()
    return s[k - 1] + (line - k) * (nxt - s[k - 1])


def segments() -> list[dict]:
    s = line_starts()
    total = total_seconds()
    last_frame_t = (frame_count() - 1) / FPS
    t = [_start(s, r[2]) for r in ROWS] + [total]
    out = []
    for i, (label, variant, _, knots, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        span = (last_frame_t - t0) if flags.get("loop") else (t1 - t0)
        kn = [(round(u * span, 6), sim) for u, sim in knots]
        seg = {"label": label, "variant": variant, "t0": t0, "t1": t1, "knots": kn, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines}
        seg["sim0"], seg["sim1"] = sim_time(seg, t0), sim_time(seg, t1 - 1e-6)
        seg["time_scale"] = round((seg["sim1"] - seg["sim0"]) / (t1 - t0), 6)
        out.append(seg)
    return out


def sim_time(seg: dict, film_t: float) -> float:
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
    if seg["flags"].get("loop"):
        uc = min(1.0, max(0.0, (t - seg["t0"]) / ((frame_count() - 1) / FPS - seg["t0"])))
        uc = uc * uc * (3 - 2 * uc)
    a, b = seg["cam_a"], seg["cam_b"]
    c = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
         "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
         "fstop": a.get("fstop", 8.0) + (b.get("fstop", 8.0) - a.get("fstop", 8.0)) * uc}
    sim = sim_time(seg, t)
    rate = (sim_time(seg, min(t + 0.5 / FPS, seg["t1"] - 1e-6)) - sim_time(seg, max(t - 0.5 / FPS, seg["t0"]))) * FPS
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": c, "u": u, "time_scale": rate}
    st.update(seg["flags"])
    return st


def car_pose(sh: dict) -> dict:
    v = sh["variant"]
    if v == "still":
        return {"x": -60.0, "y": -400.0, "psi": 0.0, "speed": 0.0, "defl": 0.0, "in_contact": False, "visible": False}
    p = rm.pose(sh["t"], "steel" if v == "steel" else "roller")
    p = {k: (float(x) if not isinstance(x, bool) else x) for k, x in p.items()}
    p["visible"] = True
    return p


def cam_world(sh: dict) -> tuple[float, float, float]:
    x, y, z = sh["cam"]["loc"]
    if sh["cam"]["rel"] == "car":
        p = car_pose(sh)
        return x + p["x"], y + p["y"], z
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
