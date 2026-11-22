"""EP.22 film timeline (pure data), built like EP.20/EP.21: frame 1 is the jet already in the arrestor bed, both gears ploughing
through the blocks, chunks and dust flying, the whole aircraft in frame, held through the first line (hook rule). Simulated time t:
seconds after the main gear reaches the bed (variant "overrun"); in the "restore" time-lapse t is the fraction of the clean-up done.
rel "plane" = the main-gear point on the centreline at ground level; rel "world" = render world."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.runway_emas import emas_motion as em

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.9
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep22-audio/audio-validation.json"

A1 = {"rel": "plane", "loc": (-21.0, -28.0, 14.0), "target": (1.0, 2.0, 1.0), "lens": 22.0, "fstop": 8.0}         # hero: the jet ploughing, dust, the ruts behind
A1_B = {"rel": "plane", "loc": (-19.5, -26.0, 13.3), "target": (1.0, 2.0, 1.0), "lens": 22.0, "fstop": 8.0}
B = {"rel": "world", "loc": (-14.0, 8.0, 1.6), "target": (0.0, -60.0, 3.0), "lens": 32.0, "fstop": 8.0}
B_B = {"rel": "world", "loc": (-14.5, 9.0, 1.7), "target": (0.0, -50.0, 3.0), "lens": 32.0, "fstop": 8.0}
C = {"rel": "world", "loc": (-34.0, -10.0, 40.0), "target": (0.0, 55.0, 0.0), "lens": 26.0, "fstop": 11.0}
C_B = {"rel": "world", "loc": (-32.0, -6.0, 38.0), "target": (0.0, 58.0, 0.0), "lens": 26.0, "fstop": 11.0}
D = {"rel": "world", "loc": (-3.2, 11.25, 0.45), "target": (-2.6, 12.4, 0.22), "lens": 40.0, "fstop": 5.6}       # the foam inside the blocks
D_B = {"rel": "world", "loc": (-3.15, 11.35, 0.44), "target": (-2.6, 12.4, 0.22), "lens": 40.0, "fstop": 5.6}
E = {"rel": "plane", "loc": (-8.5, 6.0, 1.05), "target": (-2.86, 0.0, 0.5), "lens": 26.0, "fstop": 5.6}        # the left main gear crushing in
E_B = {"rel": "plane", "loc": (-8.2, 5.4, 1.05), "target": (-2.86, 0.0, 0.5), "lens": 26.0, "fstop": 5.6}
F = {"rel": "plane", "loc": (-9.0, -3.5, 1.0), "target": (-2.86, 0.5, 0.45), "lens": 30.0, "fstop": 5.6}        # wheels sunk in the bed
F_B = {"rel": "plane", "loc": (-8.7, -3.0, 1.0), "target": (-2.86, 0.5, 0.45), "lens": 30.0, "fstop": 5.6}
G = {"rel": "plane", "loc": (-14.0, -40.0, 22.0), "target": (0.0, 0.0, 1.0), "lens": 26.0, "fstop": 8.0}
G_B = {"rel": "plane", "loc": (-12.0, -36.0, 20.0), "target": (0.0, 0.0, 1.0), "lens": 26.0, "fstop": 8.0}
H = {"rel": "world", "loc": (-46.0, 96.0, 4.0), "target": (0.0, 98.0, 3.0), "lens": 26.0, "fstop": 8.0}
H_B = {"rel": "world", "loc": (-44.0, 97.0, 4.0), "target": (0.0, 99.0, 3.0), "lens": 26.0, "fstop": 8.0}
I = {"rel": "world", "loc": (-20.0, 140.0, 2.2), "target": (0.0, 112.0, 3.4), "lens": 26.0, "fstop": 8.0}
I_B = {"rel": "world", "loc": (-18.5, 138.0, 2.3), "target": (0.0, 112.0, 3.4), "lens": 26.0, "fstop": 8.0}
J = {"rel": "world", "loc": (-30.0, 60.0, 18.0), "target": (0.0, 75.0, 0.0), "lens": 24.0, "fstop": 11.0}
J_B = {"rel": "world", "loc": (-28.0, 62.0, 17.0), "target": (0.0, 75.0, 0.0), "lens": 24.0, "fstop": 11.0}
K = {"rel": "plane", "loc": (-28.0, -40.0, 18.0), "target": (0.0, 3.0, 1.0), "lens": 22.0, "fstop": 8.0}         # loop into A1

# label, variant, start line, knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-jet-in-the-bed", "overrun", 1, [(0.0, OPEN_SIM), (2.515, 2.2)], A1, A1_B, {}, (1,)),              # held through line 1 (hook rule)
    ("B-runs-off-the-end", "overrun", 2, [(0.0, -3.2), (2.876, -0.62)], B, B_B, {}, (2,)),
    ("C-crushable-blocks", "overrun", 3, [(0.0, -0.6), (3.404, 1.2)], C, C_B, {}, (3,)),
    ("D-full-of-bubbles", "overrun", 4, [(0.0, -1.2), (3.43, -0.35)], D, D_B, {"cut": True}, (4,)),
    ("E-blocks-crush", "overrun", 5, [(0.0, -0.05), (2.722, 0.55)], E, E_B, {"nodust": True}, (5,)),
    ("F-tires-sink-in", "overrun", 6, [(0.0, 1.0), (3.159, 2.0)], F, F_B, {"nodust": True}, (6,)),
    ("G-every-block", "overrun", 7, [(0.0, 1.6), (2.786, 3.6)], G, G_B, {}, (7,)),
    ("H-eighty-mph", "overrun", 8, [(0.0, 3.0), (3.546, 6.2)], H, H_B, {}, (8,)),
    ("I-two-dozen-planes", "overrun", 9, [(0.0, 7.0), (4.203, 10.5)], I, I_B, {}, (9,)),
    ("J-replace-blocks", "restore", 10, [(0.0, 0.0), (0.2, 0.0), (2.8, 1.0)], J, J_B, {}, (10,)),
    ("K-loop", "overrun", 11, [(0.0, -0.8), (2.8625, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),   # last frame = the opening
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
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": cam, "u": u}
    st.update(seg["flags"])
    return st


def plane_y(sh: dict) -> float:
    """Main-gear y for the frame (the restore time-lapse tows the jet back out of the bed)."""
    if sh["variant"] == "restore":
        f = min(1.0, max(0.0, sh["t"]))
        k = min(1.0, f / 0.45)
        return em.main_y(60.0) + (-60.0 - em.main_y(60.0)) * (k * k * (3 - 2 * k))
    return em.main_y(sh["t"])


def cam_world(sh: dict) -> tuple[float, float, float]:
    x, y, z = sh["cam"]["loc"]
    if sh["cam"]["rel"] == "plane":
        return x, y + plane_y(sh), z
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
