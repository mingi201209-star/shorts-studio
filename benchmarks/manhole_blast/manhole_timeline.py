"""EP.23 film timeline (pure data), built like EP.20-EP.22: frame 1 is the cover already in the air above the street, flame and smoke
bursting out of the hole under it, held through the first line (hook rule). Each row's knots are (share of the shot, simulated time);
the loop row's last knot lands exactly on the film's last frame. Simulated time t: in 'smoulder' and 'vented', seconds since the
insulation began to burn (negative: before, the vault as it normally is); in 'blast' and 'latched', seconds after the spark.
Cameras: rel 'world' = render world (the street along +y, the manhole at (MX, MY)); 'section' shots look at the street cut open along
the vault's long axis (x = MX), with everything nearer the camera than the cut taken away."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.manhole_blast import manhole_motion as mm

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.40
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep23-audio/audio-validation.json"
X, Y = mm.MX, mm.MY


def cam(loc, target, lens, fstop=8.0):
    return {"rel": "world", "loc": (X + loc[0], Y + loc[1], loc[2]), "target": (X + target[0], Y + target[1], target[2]), "lens": lens, "fstop": fstop}


A1 = cam((-1.6, -5.0, 0.45), (0.1, 0.2, 2.4), 26.0, 8.0)                      # hero: the cover in the air against the sky, fire under it
A1_B = cam((-1.5, -4.7, 0.45), (0.1, 0.2, 2.6), 26.0, 8.0)
B = cam((-4.6, -1.5, -0.7), (0.4, 0.1, -1.1), 24.0, 11.0)                      # the street cut open: cars above, the vault below
B_B = cam((-4.0, -1.1, -0.85), (0.4, 0.05, -1.2), 24.0, 11.0)
C = cam((-1.75, -0.95, -0.55), (0.35, 0.05, -1.0), 24.0, 5.6)                  # meltwater dripping through the cover onto the cables
C_B = cam((-1.6, -0.75, -0.62), (0.35, 0.05, -1.05), 24.0, 5.6)
D = cam((-0.55, -0.95, -1.25), (0.72, 0.12, -1.55), 30.0, 4.0)                 # the splice: salt, cracks, arcs
D_B = cam((-0.45, -0.75, -1.32), (0.72, 0.13, -1.55), 30.0, 4.0)
E = cam((-3.0, -0.75, -1.3), (0.45, 0.0, -1.5), 24.0, 8.0)                    # the vault filling with gas
E_B = cam((-2.7, -0.35, -1.35), (0.45, 0.0, -1.5), 24.0, 8.0)
F = cam((-3.2, -1.0, -0.9), (0.35, 0.05, -0.55), 22.0, 8.0)                    # the spark, the flame through the vault, the cover going
F_B = cam((-3.4, -0.85, -0.8), (0.35, 0.05, -0.3), 22.0, 8.0)
G = cam((1.0, 4.2, 0.35), (-0.3, -0.5, 3.2), 20.0, 8.0)                        # 300 lb going up, against the low sun
G_B = cam((1.2, 4.6, 0.38), (-0.25, -0.45, 3.5), 20.0, 8.0)
G2 = cam((1.6, -4.6, 0.45), (1.3, 0.4, 0.9), 26.0, 5.6)                         # ... and down on the street beside the hole
G2_B = cam((1.5, -4.2, 0.42), (1.35, 0.45, 0.6), 26.0, 5.6)
H = cam((-1.25, -1.55, 0.85), (0.0, 0.05, 0.15), 28.0, 5.6)                   # a vented cover breathing out
H_B = cam((-1.05, -1.3, 0.72), (0.0, 0.05, 0.2), 28.0, 5.6)
I = cam((-3.9, 0.9, -0.75), (0.35, 0.0, -0.75), 22.0, 8.0)                     # the gas leaving through the holes
I_B = cam((-3.6, 1.2, -0.6), (0.35, 0.0, -0.6), 22.0, 8.0)
J = cam((-1.55, -1.15, 0.30), (0.0, 0.0, 0.10), 35.0, 5.6)                    # a latched cover pops up and drops back
J_B = cam((-1.45, -1.05, 0.29), (0.0, 0.0, 0.10), 35.0, 5.6)
K = cam((-6.2, -8.5, 1.15), (-1.0, -3.0, 0.4), 30.0, 8.0)                     # loop: the street, holes in a cover, back to the blast

# label, variant, start line, knots [(share of the shot, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-cover-in-the-air", "blast", 1, [(0.0, OPEN_SIM), (1.0, 0.78)], A1, A1_B, {}, (1,)),                 # held through line 1 (hook rule)
    ("B-vaults-under-streets", "smoulder", 2, [(0.0, -400.0), (1.0, -372.0)], B, B_B, {"section": True}, (2,)),
    ("C-salty-meltwater", "smoulder", 3, [(0.0, -60.0), (1.0, -55.5)], C, C_B, {"section": True}, (3,)),
    ("D-insulation-arcs", "smoulder", 4, [(0.0, 0.2), (1.0, 6.2)], D, D_B, {"section": True}, (4,)),
    ("E-gas-fills-the-vault", "smoulder", 5, [(0.0, 20.0), (1.0, mm.T_IGNITE - 4.0)], E, E_B, {"section": True}, (5,)),
    ("F-one-spark", "blast", 6, [(0.0, -0.075), (0.102, -0.05), (0.609, -0.002), (1.0, 0.17)], F, F_B, {"section": True}, (6,)),   # spark on "spark", blast on "explodes"
    ("G-three-hundred-pounds", "blast", 7, [(0.0, 0.17), (1.0, 1.05)], G, G_B, {}, (7,)),
    ("G2-crashes-down", "blast", 7.5, [(0.0, 1.5), (1.0, 3.6)], G2, G2_B, {}, (7,)),
    ("H-covers-with-vents", "vented", 8, [(0.0, 300.0), (1.0, 330.0)], H, H_B, {}, (8,)),
    ("I-gas-escapes", "vented", 9, [(0.0, 200.0), (1.0, 560.0)], I, I_B, {"section": True}, (9,)),
    ("J-latched-covers", "latched", 10, [(0.0, -0.30), (0.266, 0.0), (0.629, 0.25), (0.858, 0.47), (1.0, 0.62)], J, J_B, {}, (10,)),   # "pop up", "vent", "drop back"
    ("K-loop", "blast", 11, [(0.0, -0.9), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),   # last frame = the opening
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
    """Shot start: a line's start, or part of the way through a line for a second shot on the same line (e.g. 7.5)."""
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
    uc = 0.5 * u + 0.5 * (1 - (1 - u) ** 2) if seg["flags"].get("loop") else _smooth(u)
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
