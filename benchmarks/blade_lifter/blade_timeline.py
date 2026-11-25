"""EP.29 film timeline (pure data), built like EP.20-EP.28: frame 1 is the rig in the sharp right bend with the blade raised to 60
degrees and swung toward the road, held through the first line (hook rule). Each row's knots are (share of the shot, story time);
the loop row's last knot lands exactly on the film's last frame. Story time t (s): the lifter is at arc length s = S_START + V t
(blade_motion); the left bend is passed at about t = -3..4, the right bend at about t = 17..24. Flags: 'ghost' adds the translucent
flat blade, 'wind' stops the rig at WIND_S in a gale. Cameras: rel 'world', or 'rig' (offset by the lifter's place, world axes)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.blade_lifter import blade_motion as bm
from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 19.0
WIND_S = 300.0
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep29-audio/audio-validation.json"


def rp(s: float, d: float, z: float) -> tuple[float, float, float]:
    """A world point at arc length s along the road, d metres right of the centre line, z up."""
    p, h = bm.at(s)
    off = d - bm.LANE_OFF
    return (round(float(p[0] + off * math.cos(h)), 3), round(float(p[1] - off * math.sin(h)), 3), z)


def cam(loc, target, lens, fstop=8.0, rel="world"):
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam(rp(278.0, -2.2, 2.2), rp(214.0, 1.0, 30.0), 26.0, 11.0)              # ahead of the bend: the rig coming round, blade at the sky
A1_B = cam(rp(276.0, -2.2, 2.3), rp(218.0, 1.0, 31.0), 26.0, 11.0)
B = cam(rp(245.0, 60.0, 70.0), rp(215.0, -10.0, 15.0), 28.0, 11.0)             # the winding mountain road from the air
B_B = cam(rp(252.0, 58.0, 68.0), rp(222.0, -10.0, 15.0), 28.0, 11.0)
C = cam(rp(128.0, 14.0, 92.0), rp(129.0, 14.0, 0.0), 24.0, 11.0)             # from above: lying flat, it hangs off the bend into the trees
C_B = cam(rp(131.0, 14.0, 90.0), rp(132.0, 14.0, 0.0), 24.0, 11.0)
D = cam(rp(-52.0, 100.0, 20.0), rp(-48.0, 0.0, 30.0), 32.0, 11.0)             # the trailer tilts the blade up from 35 to 58 degrees
D_B = cam(rp(-46.0, 98.0, 21.0), rp(-43.0, 0.0, 33.0), 32.0, 11.0)
E = cam(rp(92.0, 75.0, 18.0), rp(92.0, 0.0, 20.0), 26.0, 11.0)               # side by side: tilted, it sticks out half as far
E_B = cam(rp(94.0, 74.0, 18.0), rp(94.0, 0.0, 20.0), 26.0, 11.0)
F1 = cam(rp(150.0, -30.0, 50.0), rp(196.0, 0.0, 25.0), 26.0, 11.0)             # behind the rig: it swings the blade toward the road ahead
F1_B = cam(rp(157.0, -30.0, 50.0), rp(203.0, 0.0, 25.0), 26.0, 11.0)
F2 = cam(rp(222.0, 45.0, 26.0), rp(222.0, -14.0, 18.0), 24.0, 11.0)            # over the rock cut and the trees
F2_B = cam(rp(226.0, 44.0, 26.0), rp(226.0, -14.0, 18.0), 24.0, 11.0)
G = cam(rp(282.0, 72.0, 16.0), rp(282.0, 0.0, 20.0), 26.0, 11.0)               # the whole rig: a blade almost as long as a football field
G_B = cam(rp(286.0, 71.0, 16.0), rp(286.0, 0.0, 20.0), 26.0, 11.0)
H = cam((7.0, 30.0, 1.6), (-2.0, -6.0, 3.0), 26.0, 8.0, rel="rig")             # crawling along behind its escort
H_B = cam((7.0, 29.0, 1.7), (-2.0, -6.0, 3.0), 26.0, 8.0, rel="rig")
I = cam(rp(WIND_S + 28.0, -3.6, 2.0), rp(WIND_S + 5.0, 2.0, 18.0), 24.0, 11.0)  # a gale: the trip stops
I_B = cam(rp(WIND_S + 27.0, -3.6, 2.1), rp(WIND_S + 5.0, 2.0, 19.0), 24.0, 11.0)
J = cam(rp(104.0, -60.0, 75.0), rp(104.0, 0.0, 10.0), 26.0, 11.0)              # the road as it is, not rebuilt
J_B = cam(rp(108.0, -58.0, 73.0), rp(108.0, 0.0, 10.0), 26.0, 11.0)
K = cam(rp(300.0, -2.6, 6.0), rp(205.0, 0.0, 20.0), 28.0, 11.0)               # loop: into frame 1

# label, start line, knots [(share of the shot, story s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-blade-at-the-sky", 1, [(0.0, OPEN_SIM), (1.0, 22.0)], A1, A1_B, {}, (1,)),                     # held through line 1
    ("B-mountain-road", 2, [(0.0, 24.0), (1.0, 30.0)], B, B_B, {}, (2,)),
    ("C-flat-would-hit", 3, [(0.0, 1.0), (1.0, 4.0)], C, C_B, {"ghost": True, "flat_only": True}, (3,)),
    ("D-tilts-to-60", 4, [(0.0, -32.2), (1.0, -30.2)], D, D_B, {}, (4,)),
    ("E-half-as-far", 5, [(0.0, -9.0), (1.0, -6.0)], E, E_B, {"ghost": True}, (5,)),
    ("F1-swings-sideways", 6, [(0.0, 12.6), (1.0, 15.9)], F1, F1_B, {}, (6,)),
    ("F2-clears-cliffs-trees", 6.5, [(0.0, 20.0), (1.0, 24.0)], F2, F2_B, {}, (6,)),
    ("G-football-field-long", 7, [(0.0, 26.0), (1.0, 30.0)], G, G_B, {}, (7,)),
    ("H-twelve-mph", 8, [(0.0, 26.0), (1.0, 30.0)], H, H_B, {}, (8,)),
    ("I-wind-stops-it", 9, [(0.0, 40.0), (1.0, 44.0)], I, I_B, {"wind": True}, (9,)),
    ("J-roads-not-rebuilt", 10, [(0.0, -1.0), (1.0, 5.0)], J, J_B, {}, (10,)),
    ("K-loop", 11, [(0.0, 12.0), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),               # last frame = the opening
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
    """Shot start: a line's start, or part of the way through a line for a second shot on the same line (6.5: "to clear cliffs")."""
    k = int(line)
    if line == k:
        return s[k - 1]
    nxt = s[k] if k < len(s) else total_seconds()
    return s[k - 1] + (line - k) * (nxt - s[k - 1])


def segments() -> list[dict]:
    s = line_starts()
    total = total_seconds()
    last_frame_t = (frame_count() - 1) / FPS
    t = [_start(s, r[1]) for r in ROWS] + [total]
    out = []
    for i, (label, _, knots, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        span = (last_frame_t - t0) if flags.get("loop") else (t1 - t0)
        kn = [(round(u * span, 6), sim) for u, sim in knots]
        seg = {"label": label, "t0": t0, "t1": t1, "knots": kn, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines}
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
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim, "cam": c, "u": u}
    st.update(seg["flags"])
    return st


def rig_s(sh: dict) -> float:
    return WIND_S if sh.get("wind") else bm.s_of(sh["t"])


def cam_world(sh: dict) -> tuple[float, float, float]:
    x, y, z = sh["cam"]["loc"]
    if sh["cam"]["rel"] == "rig":
        p, _ = bm.at(rig_s(sh))
        return x + float(p[0]), y + float(p[1]), z
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


def blade_points(sh: dict, n: int = 30) -> np.ndarray:
    s = rig_s(sh)
    a = bm.alpha(s)
    return bm.blade_axis(s, a, bm.psi(s, a), n)
