"""EP.25 film timeline (pure data), built like EP.20-EP.24: frame 1 is the road standing straight up in front of the waiting cars,
a sailboat's mast passing between the two raised leaves, held through the first line (hook rule). Each row's knots are (share of the
shot, story time); the loop row's last knot lands exactly on the film's last frame. Story time t (bascule_motion): the gates come
down at -18 s, the leaves rise from 0 to 60 s, the sailboat passes from 62 to 152 s, the leaves come down from 160 s. Section shots
look at the street and the pit cut open along the bridge's middle (y = 0), with everything on the camera's side of the cut taken
away. Cameras are in render-world coordinates (the river along +y, the hero bridge across it along x at y = 0)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.bascule_bridge import bascule_motion as bm
from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 100.0
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep25-audio/audio-validation.json"


def cam(loc, target, lens, fstop=8.0):
    return {"rel": "world", "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((62.0, -3.5, 2.6), (20.0, 2.0, 12.0), 24.0, 11.0)                    # behind the waiting cars: the road stands up, the mast between
A1_B = cam((60.5, -3.4, 2.5), (20.0, 2.0, 12.5), 24.0, 11.0)
B = cam((46.0, -70.0, 22.0), (27.0, 80.0, 14.0), 26.0, 11.0)                   # three drawbridges up along the river, roads standing up
B_B = cam((46.0, -62.0, 21.0), (27.0, 86.0, 14.0), 26.0, 11.0)
C = cam((22.0, -26.0, -4.2), (31.0, 0.0, 14.0), 22.0, 11.0)                   # from the water: the leaf's steel above
C_B = cam((21.0, -24.5, -4.2), (31.0, 0.0, 15.0), 22.0, 11.0)
D = cam((14.0, -62.0, 4.0), (30.0, 0.0, 9.0), 26.0, 11.0)                     # time-lapse: up in about a minute
D_B = cam((14.5, -58.0, 4.0), (30.0, 0.0, 10.0), 26.0, 11.0)
E = cam((40.5, -24.0, 3.5), (40.0, 0.0, -4.0), 24.0, 8.0)                     # cut open: the pit under the street
E_B = cam((40.0, -21.0, -2.0), (39.5, 0.0, -6.0), 24.0, 8.0)
F = cam((37.0, -22.0, -3.0), (36.5, 0.0, -2.5), 22.0, 8.0)                    # the counterweight behind the pivot
F_B = cam((36.5, -21.0, -2.8), (36.0, 0.0, -1.8), 22.0, 8.0)
G = cam((26.0, -38.0, 1.0), (31.0, 0.0, 1.5), 22.0, 11.0)                     # one seesaw: the leaf and the counterweight
G_B = cam((26.5, -36.0, 1.0), (31.0, 0.0, 2.0), 22.0, 11.0)
H = cam((32.9, 3.0, -7.6), (33.2, 8.6, -10.1), 30.0, 4.0)                     # the pinion and the rack: only a nudge
H_B = cam((32.95, 3.3, -7.7), (33.2, 8.6, -10.1), 30.0, 4.0)
I = cam((33.0, -34.0, -3.0), (35.0, 0.0, -1.0), 22.0, 11.0)                   # time-lapse: the counterweight swings down into the pit
I_B = cam((33.5, -33.0, -3.5), (35.0, 0.0, -1.5), 22.0, 11.0)
J = cam((5.0, -95.0, 5.0), (0.0, 0.0, 18.0), 30.0, 11.0)                      # both leaves up like two seesaws, the boat between
J_B = cam((4.0, -88.0, 5.0), (0.0, 0.0, 18.0), 30.0, 11.0)
K = cam((72.0, -4.0, 3.0), (20.0, 2.0, 6.0), 24.0, 11.0)                      # loop: closed, then up it goes again
SECTION = {"section": True}

# label, variant, start line, knots [(share of the shot, story s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-road-stands-up", "story", 1, [(0.0, OPEN_SIM), (1.0, OPEN_SIM + 6.0)], A1, A1_B, {}, (1,)),       # held through line 1
    ("B-chicago-drawbridges", "story", 2, [(0.0, 108.0), (1.0, 118.0)], B, B_B, {}, (2,)),
    ("C-thousands-of-tons", "story", 3, [(0.0, 118.0), (1.0, 124.0)], C, C_B, {}, (3,)),
    ("D-up-in-a-minute", "story", 4, [(0.0, -2.0), (1.0, 62.0)], D, D_B, {}, (4,)),
    ("E-pit-under-the-street", "story", 5, [(0.0, -9.0), (1.0, -4.0)], E, E_B, SECTION, (5,)),
    ("F-counterweight-behind-pivot", "story", 6, [(0.0, 6.0), (1.0, 18.0)], F, F_B, SECTION, (6,)),
    ("G-balanced-like-a-seesaw", "story", 7, [(0.0, 18.0), (1.0, 32.0)], G, G_B, SECTION, (7,)),
    ("H-only-a-nudge", "story", 8, [(0.0, 26.0), (1.0, 29.0)], H, H_B, SECTION, (8,)),
    ("I-swings-down-into-the-pit", "story", 9, [(0.0, 0.0), (1.0, 60.0)], I, I_B, SECTION, (9,)),
    ("J-bascule-seesaw", "story", 10, [(0.0, 124.0), (1.0, 132.0)], J, J_B, {}, (10,)),
    ("K-loop", "story", 11, [(0.0, -6.0), (0.5, 40.0), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),   # last frame = the opening
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
    last_frame_t = (frame_count() - 1) / FPS
    t = [s[r[2] - 1] for r in ROWS] + [total]
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
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": c, "u": u}
    st.update(seg["flags"])
    return st


def cam_world(sh: dict) -> tuple[float, float, float]:
    return tuple(sh["cam"]["loc"])


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
