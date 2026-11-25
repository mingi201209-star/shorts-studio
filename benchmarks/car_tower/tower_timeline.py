"""EP.28 film timeline (pure data), built like EP.20-EP.27: frame 1 is the hero silo from outside, a carriage carrying the red car
up the glass tower full of new cars, held through the first line (hook rule). Each row's knots are (share of the shot, story time);
the loop row's last knot lands exactly on the film's last frame. Story time t (s): the red car arrives on the fork at t = 0
(tower_motion), climbs to floor 16 and is slid into its bay by t = 42; its buyer arrives at t = 200 and it is back down by t = 265.
Cameras: rel 'world', or 'carriage' (rides up and down with the hero carriage: z offset by the carriage's height)."""
from __future__ import annotations

import json
import math
from pathlib import Path

from benchmarks.car_tower import tower_motion as tm
from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 4.0
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep28-audio/audio-validation.json"
_SLOT = math.radians((tm.SLOT_BAY + 0.5) * 360.0 / tm.N_BAYS)
SLOT_XY = (tm.R_BAY * math.cos(_SLOT), tm.R_BAY * math.sin(_SLOT))


def cam(loc, target, lens, fstop=8.0, rel="world"):
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((-46.0, -14.0, 6.0), (0.0, 0.0, 21.0), 30.0, 11.0)                    # from outside: the red car riding up the glass silo
A1_B = cam((-45.0, -13.0, 6.5), (0.0, 0.0, 22.0), 30.0, 11.0)
B = cam((-95.0, -110.0, 70.0), (12.0, 40.0, 18.0), 30.0, 11.0)                 # the two silos, the hall, the canal, the factory
B_B = cam((-88.0, -102.0, 66.0), (12.0, 44.0, 18.0), 30.0, 11.0)
C = cam((1.7, -9.0, -1.9), (0.0, -40.0, -3.0), 28.0, 5.6)                      # in the tunnel: the car rolls in from the factory
C_B = cam((1.6, -8.8, -2.0), (0.0, -36.0, -3.0), 28.0, 5.6)
D = cam((5.6, -6.6, -1.9), (0.0, -4.0, -2.6), 24.0, 5.6)                       # the transfer station: the arm takes the car up
D_B = cam((5.4, -6.4, -1.6), (0.0, -4.0, -1.8), 24.0, 5.6)
E1 = cam((-16.0, 2.6, 1.8), (0.0, 0.0, 0.3), 30.0, 8.0, rel="carriage")       # through the open column: it turns to face a bay
E1_B = cam((-15.4, 2.4, 1.8), (0.0, 0.0, 0.3), 30.0, 8.0, rel="carriage")
E2 = cam((SLOT_XY[0], SLOT_XY[1], 45.5), (0.0, 0.0, 8.0), 22.0, 8.0)            # from high in the open column: it races up at us
E2_B = cam((SLOT_XY[0], SLOT_XY[1], 45.5), (0.0, 0.0, 12.0), 22.0, 8.0)
F = cam((-6.6, 12.9, tm.floor_z(16) + 1.2), (-2.0, 3.9, tm.floor_z(16) + 0.7), 32.0, 5.6)   # from outside, straight into its bay
F_B = cam((-6.4, 12.6, tm.floor_z(16) + 1.15), (-2.0, 3.9, tm.floor_z(16) + 0.7), 32.0, 5.6)
G = cam((-22.0, -7.0, 2.0), (-6.0, 2.0, 30.0), 22.0, 11.0)                     # up the facade: floor on floor of cars, no ramps
G_B = cam((-21.6, -6.4, 2.0), (-6.0, 2.6, 32.0), 22.0, 11.0)
H = cam((-70.0, -58.0, 18.0), (14.0, 8.0, 24.0), 26.0, 11.0)                   # 400 cars on 20 floors, the twin beside it
H_B = cam((-66.0, -62.0, 20.0), (14.0, 8.0, 24.0), 26.0, 11.0)
I = cam((-40.0, 10.0, 22.0), (0.0, 0.0, 20.0), 26.0, 11.0)                     # fetched for its buyer: up, out of its bay, down
I_B = cam((-39.0, 12.0, 21.0), (0.0, 0.0, 19.0), 26.0, 11.0)
J = cam((SLOT_XY[0] * 1.02, SLOT_XY[1] * 1.02, 1.6), (0.0, 0.0, -0.6), 22.0, 8.0, rel="carriage")   # riding down with it
J_B = cam((SLOT_XY[0] * 1.02, SLOT_XY[1] * 1.02, 1.9), (0.0, 0.0, -0.9), 22.0, 8.0, rel="carriage")
K = cam((-80.0, -40.0, 14.0), (0.0, 0.0, 20.0), 30.0, 11.0)                    # loop: into frame 1

# label, start line, knots [(share of the shot, story s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-car-up-the-tower", 1, [(0.0, OPEN_SIM), (1.0, 14.0)], A1, A1_B, {}, (1,)),                     # held through line 1
    ("B-wolfsburg-towers", 2, [(0.0, 60.0), (1.0, 110.0)], B, B_B, {}, (2,)),
    ("C-tunnel-from-factory", 3, [(0.0, -24.0), (1.0, -6.0)], C, C_B, {}, (3,)),
    ("D-arm-picks-it-up", 4, [(0.0, -3.0), (1.0, 3.0)], D, D_B, {}, (4,)),
    ("E1-turns-to-a-bay", 5, [(0.0, 2.6), (1.0, 7.6)], E1, E1_B, {}, (5,)),
    ("E2-climbs-fast", 5.45, [(0.0, 8.0), (1.0, 22.0)], E2, E2_B, {}, (5,)),
    ("F-slides-into-bay", 6, [(0.0, 23.0), (1.0, 41.0)], F, F_B, {}, (6,)),
    ("G-packed-tight", 7, [(0.0, 50.0), (1.0, 70.0)], G, G_B, {}, (7,)),
    ("H-400-cars-20-floors", 8, [(0.0, 70.0), (1.0, 100.0)], H, H_B, {}, (8,)),
    ("I-fetched-for-buyer", 9, [(0.0, 200.0), (1.0, 266.0)], I, I_B, {}, (9,)),
    ("J-fastest-in-world", 10, [(0.0, 243.0), (1.0, 262.0)], J, J_B, {}, (10,)),
    ("K-loop", 11, [(0.0, -2.0), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),             # last frame = the opening
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
    """Shot start: a line's start, or part of the way through a line for a second shot on the same line (5.45: "and climbs")."""
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


def cam_world(sh: dict) -> tuple[float, float, float]:
    x, y, z = sh["cam"]["loc"]
    if sh["cam"]["rel"] == "carriage":
        z += tm.carriage(sh["t"])["z"]
    return x, y, z


def subject_box(sh: dict) -> tuple[tuple, tuple]:
    """The subject: the hero silo (glass cylinder) as a world box."""
    top = tm.floor_z(tm.N_FLOORS - 1) + tm.FLOOR_H + 1.5
    return (-tm.R_GLASS, -tm.R_GLASS, 0.0), (tm.R_GLASS, tm.R_GLASS, top)


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
