"""EP.24 film timeline (pure data), built like EP.20-EP.23: frame 1 is the red sedan already on the grooves, the tune playing, held
through the first line (hook rule). Each row's knots are (share of the shot, simulated time); the loop row's last knot lands exactly
on the film's last frame. Simulated time t: seconds since the front tyres reached the first groove, for a car at 55 mph on the road as
built ('built'), as designed ('design', 'compare' adds the planned grooves as blue lines between the built ones) or at 35 mph on the
designed road ('slow'); in 'gap' t is the share of the spacing-mistake demonstration. Shots that show pitch run in real time so the
sound is the true pitch; only the thump demonstration (C, D) is slowed. Cameras: rel 'car' = from the car's reference point,
rel 'world' = render world (the road along +y, the musical lane at x 0.15-3.45)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.musical_road import musical_motion as mm

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.35
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep24-audio/audio-validation.json"


def cam(rel, loc, target, lens, fstop=8.0):
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam("car", (-1.7, 3.9, 0.34), (0.1, -0.5, 0.6), 28.0, 8.0)                # hero: low, ahead of the car, the grooves streaming under it
A1_B = cam("car", (-1.65, 3.75, 0.33), (0.1, -0.5, 0.6), 28.0, 8.0)
B = cam("world", (0.55, 26.0, 0.85), (2.2, 16.0, 0.0), 26.0, 8.0)               # the grooves like a record, the car coming over them
B_B = cam("world", (0.55, 26.5, 0.80), (2.2, 16.8, 0.0), 26.0, 8.0)
C = cam("car", (-2.05, 1.6, 0.18), (-0.72, 1.087, 0.2), 30.0, 4.0)              # the front tyre, slowed down: one thump per groove
C_B = cam("car", (-2.0, 1.45, 0.18), (-0.72, 1.087, 0.18), 30.0, 4.0)
D = cam("car", (-2.0, 1.45, 0.18), (-0.72, 1.087, 0.18), 30.0, 4.0)             # ... speeding up until the thumps are a note
D_B = cam("car", (-3.4, 2.6, 0.5), (-0.5, 0.6, 0.3), 26.0, 5.6)
E = cam("car", (0.0, 1.5, 12.0), (0.0, 4.5, 0.0), 30.0, 8.0)                    # from above: wide gaps low, close grooves high
E_B = cam("car", (0.0, 2.5, 12.5), (0.0, 5.5, 0.0), 30.0, 8.0)
F = cam("car", (-6.5, 12.0, 7.0), (0.0, -2.0, 0.0), 24.0, 8.0)                  # a drone ahead of the car: the grooves it just played glow
F_B = cam("car", (-5.5, 10.0, 7.5), (0.0, -4.0, 0.0), 24.0, 8.0)
G = cam("car", (-5.5, 1.0, 1.1), (0.0, 0.6, 0.6), 30.0, 8.0)                    # slower: the song slower and lower
G_B = cam("car", (-5.2, 0.4, 1.0), (0.0, 0.4, 0.6), 30.0, 8.0)
H = cam("car", (5.0, 9.0, 3.0), (0.0, 0.0, 0.7), 26.0, 11.0)                     # the desert road in California
H_B = cam("car", (4.6, 8.0, 2.6), (0.0, 0.0, 0.7), 26.0, 11.0)
I = cam("world", (2.05, -39.62, 0.48), (2.05, -39.75, 0.0), 30.0, 5.6)          # the gap the crew measured against groove to groove
I_B = cam("world", (2.05, -39.6, 0.44), (2.05, -39.74, 0.0), 30.0, 5.6)
J = cam("world", (4.2, 52.0, 0.28), (1.8, 38.0, 0.0), 28.0, 8.0)                # built grooves against the planned blue lines
J_B = cam("world", (4.2, 52.5, 0.26), (1.8, 38.5, 0.0), 28.0, 8.0)
K = cam("car", (-4.5, 14.0, 1.2), (0.0, 2.0, 0.5), 26.0, 8.0)                   # loop: back to the opening view

# label, variant, start line, knots [(share of the shot, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-car-on-the-grooves", "built", 1, [(0.0, OPEN_SIM), (1.0, None)], A1, A1_B, {}, (1,)),        # real time, held through line 1
    ("B-like-a-record", "design", 2, [(0.0, -1.6), (1.0, None)], B, B_B, {}, (2,)),
    ("C-one-thump", "design", 3, [(0.0, 0.302), (1.0, 0.375)], C, C_B, {"rings": True}, (3,)),
    ("D-thumps-to-a-note", "design", 4, [(0.0, 0.375), (0.45, 0.42), (1.0, 2.0)], D, D_B, {"rings": True}, (4,)),
    ("E-close-high-wide-low", "design", 5, [(0.0, 0.25), (1.0, None)], E, E_B, {"glow": True}, (5,)),
    ("F-plays-a-melody", "design", 6, [(0.0, -0.2), (1.0, None)], F, F_B, {"glow": True}, (6,)),
    ("G-slower-lower", "slow", 7, [(0.0, -0.1), (1.0, None)], G, G_B, {}, (7,)),
    ("H-california", "built", 8, [(0.0, -0.4), (1.0, None)], H, H_B, {}, (8,)),
    ("I-the-gap", "gap", 9, [(0.0, 0.0), (1.0, 1.0)], I, I_B, {}, (9,)),
    ("J-every-note-flat", "compare", 10, [(0.0, -0.55), (1.0, None)], J, J_B, {}, (10,)),
    ("K-loop", "built", 11, [(0.0, -2.3), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),  # last frame = the opening
]
REAL_TIME = {"built": 1.0, "design": 1.0, "slow": 1.0, "compare": 1.0}


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
        kn = []
        for u, sim in knots:
            if sim is None:                                                   # real time from the previous knot
                pu, ps = kn[-1]
                sim = ps + (u * span - pu)
            kn.append((round(u * span, 6), sim))
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
    if seg["variant"] == "gap":
        return k[-1][1]
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


def car_state(sh: dict) -> dict:
    """Where the car is and what its front tyres are playing at the frame's simulated time."""
    v = sh["variant"]
    if v == "gap":
        return {"y": -400.0, "speed": "design", "wheel_angle": 0.0, "bounce": 0.0, "visible": False, "note": None, "thump_rate": 0.0}
    speed = "slow" if v == "slow" else "design"
    version = "built" if v in ("built", "compare") else "design"
    vel = mm.V_SLOW if speed == "slow" else mm.V_DESIGN
    t = sh["t"]
    return {"y": mm.car_y(t, vel), "speed": speed, "wheel_angle": mm.wheel_angle(t, vel), "bounce": mm.bounce(t, version, speed), "visible": True,
            "note": mm.note_at(t, version, speed), "thump_rate": mm.thump_rate(t, version, speed)}


def cam_world(sh: dict) -> tuple[float, float, float]:
    x, y, z = sh["cam"]["loc"]
    if sh["cam"]["rel"] == "car":
        return x + mm.CAR_X, y + car_state(sh)["y"], z
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
