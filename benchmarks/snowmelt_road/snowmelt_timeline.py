"""EP.31 film timeline (pure data), built like EP.20-EP.30: frame 1 is the street spraying water in falling snow with a car coming
through the jets, held through the first line (hook rule). Each row's knots are (share of the shot, story time); the loop row's last
knot lands exactly on the film's last frame. Story time t (s) is real time on a snowy evening (snowmelt_world: the jets, the snow,
the car passing the camera of the opening at about t = 104.6). Flags: 'section' cuts the ground open along the centre line, 'sink'
lets the ground drop round the well (share of the shot), 'pipes' shows the newer design (no jets, warm pipes under see-through
asphalt)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.snowmelt_road import snowmelt_world as w

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 100.0
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep31-audio/audio-validation.json"
YW = w.Y_WELL


def cam(loc, target, lens, fstop=8.0):
    return {"loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((-1.1, -2.0, 1.3), (0.6, 20.0, 0.35), 24.0, 5.6)                      # the street spraying water, a car coming through
A1_B = cam((-1.05, -1.5, 1.28), (0.6, 20.5, 0.35), 24.0, 5.6)
B = cam((-38.0, -30.0, 42.0), (0.0, 60.0, 0.0), 26.0, 11.0)                    # from above: the town under snow, the wet street
B_B = cam((-36.0, -24.0, 40.0), (0.0, 62.0, 0.0), 26.0, 11.0)
C = cam((0.75, -0.95, 0.24), (0.0, 0.05, 0.03), 35.0, 2.8)                       # a nozzle in the centre line
C_B = cam((0.68, -0.85, 0.22), (0.0, 0.05, 0.03), 35.0, 2.8)
D = cam((14.0, YW - 7.0, 4.0), (0.0, YW, -5.0), 24.0, 8.0)                      # cut open: down the well to the warm water
D_B = cam((14.0, YW - 7.0, -42.0), (0.0, YW, -50.0), 24.0, 8.0)
E = cam((-0.9, -0.5, 0.35), (-0.8, 0.35, 0.0), 45.0, 3.5)                      # flakes vanish as they land in the water
E_B = cam((-0.88, -0.42, 0.33), (-0.8, 0.4, 0.0), 45.0, 3.5)
F = cam((2.5, -95.0, 9.0), (0.0, 40.0, 2.0), 32.0, 11.0)                        # the whole street, mountains behind
F_B = cam((2.5, -88.0, 8.6), (0.0, 40.0, 2.0), 32.0, 11.0)
G1 = cam((0.9, 6.0, 1.0), (2.7, 18.0, 6.9), 35.0, 4.0)                          # wet snow falling through a street lamp
G1_B = cam((0.9, 6.4, 1.0), (2.7, 18.0, 6.6), 35.0, 4.0)
G2 = cam((3.2, -1.2, 0.5), (1.2, 1.2, 0.05), 32.0, 4.0)                        # the water stays liquid, running to the gutter
G2_B = cam((3.15, -1.0, 0.48), (1.2, 1.3, 0.05), 32.0, 4.0)
H1 = cam((0.0, -20.0, 7.5), (0.0, 40.0, 0.0), 30.0, 11.0)                       # rows and rows of jets: a lot of water
H1_B = cam((0.0, -17.0, 7.3), (0.0, 40.0, 0.0), 30.0, 11.0)
H2 = cam((7.0, YW, -0.5), (0.0, YW, -0.5), 28.0, 8.0)                    # the ground sinks round the well
H2_B = cam((6.6, YW + 0.3, -0.6), (0.0, YW, -0.7), 28.0, 8.0)
I = cam((3.0, 4.0, 3.2), (-0.5, 17.0, -0.1), 28.0, 8.0)                         # newer roads: warm pipes under the pavement
I_B = cam((2.8, 4.6, 3.0), (-0.5, 17.2, -0.1), 28.0, 8.0)
J = cam((-1.0, 2.0, 1.1), (1.75, -20.0, 0.5), 32.0, 5.6)                        # the car drives away through the spray
J_B = cam((-1.0, 1.4, 1.1), (1.75, -20.0, 0.5), 32.0, 5.6)
K = cam((-1.6, -8.0, 2.2), (0.6, 22.0, 0.35), 24.0, 5.6)                         # loop: into frame 1

# label, start line, knots [(share of the shot, story s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-road-sprays", 1, [(0.0, OPEN_SIM), (1.0, OPEN_SIM + 2.73)], A1, A1_B, {}, (1,)),               # held through line 1
    ("B-built-into-street", 2, [(0.0, 92.0), (1.0, 96.11)], B, B_B, {}, (2,)),
    ("C-nozzles-centre", 3, [(0.0, 50.0), (1.0, 53.2)], C, C_B, {}, (3,)),
    ("D-from-deep-underground", 4, [(0.0, 20.0), (1.0, 23.85)], D, D_B, {"section": True}, (4,)),
    ("E-melts-as-it-lands", 5, [(0.0, 60.0), (1.0, 63.73)], E, E_B, {}, (5,)),
    ("F-nagaoka-street", 6, [(0.0, 80.0), (1.0, 84.27)], F, F_B, {}, (6,)),
    ("G1-near-freezing", 7, [(0.0, 30.0), (1.0, 32.73)], G1, G1_B, {}, (7,)),
    ("G2-stays-liquid", 7.55, [(0.0, 40.0), (1.0, 42.13)], G2, G2_B, {}, (7,)),
    ("H1-lots-of-water", 8, [(0.0, 10.0), (1.0, 12.18)], H1, H1_B, {}, (8,)),
    ("H2-ground-sinks", 8.57, [(0.0, 0.0), (1.0, 1.64)], H2, H2_B, {"section": True, "sink": True}, (8,)),
    ("I-pipes-under-pavement", 9, [(0.0, 140.0), (1.0, 143.67)], I, I_B, {"pipes": True}, (9,)),
    ("J-washes-snow-away", 10, [(0.0, 105.0), (1.0, 106.75)], J, J_B, {}, (10,)),
    ("K-loop", 10.5, [(0.0, OPEN_SIM - 1.75), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (10,)),   # last frame = the opening
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
    """Shot start: a line's start, or part of the way through a line for a second shot on the same line."""
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
    c = {"loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
         "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
         "fstop": a.get("fstop", 8.0) + (b.get("fstop", 8.0) - a.get("fstop", 8.0)) * uc}
    sim = sim_time(seg, t)
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim, "cam": c, "u": u,
          "sink": w.subside(u) if seg["flags"].get("sink") else 0.0, "sinking": bool(seg["flags"].get("sink"))}
    st.update({k: v for k, v in seg["flags"].items() if k != "sink"})
    return st


def subject_box(t: float) -> tuple[tuple, tuple]:
    """The subject: the jets in the street in front of the opening camera and the car coming through them, as a world box."""
    cy = w.car_y(t)
    far = 30.0 if cy is None else max(30.0, cy + 2.5)
    return (-2.4, 4.0, 0.0), (2.4, far, 1.45)


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
