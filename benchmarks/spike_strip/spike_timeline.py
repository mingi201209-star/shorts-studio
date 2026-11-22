"""EP.19 film timeline (pure data), built like EP.13-EP.18: frame 1 is the front tyre already on the strip, hollow steel quills punching
into its tread (extreme slow motion, low beside the wheel). Simulated time t: seconds after the front-left tyre meets the first quill
row. pose_rate lets the time-lapse shots run the tyre's deflation fast while the car barely moves in frame. rel "wheel" = front-left
wheel centre (no rotation); rel "car" = car reference; rel "world" = render world."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.spike_strip import spike_motion as sm

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.01
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep19-audio/audio-validation.json"
DASH = 12.0
HERO = (-2.46, 0.31, 0.0)          # a quill the tyres do not take (row 2), for the macro

A1 = {"rel": "car", "loc": (-2.3, 2.6, 0.28), "target": (-0.7, 0.3, 0.32), "lens": 26.0, "fstop": 5.6}      # hero 3/4 from road level: the strip across the foreground, the car on it
A1_B = {"rel": "car", "loc": (-2.1, 2.3, 0.27), "target": (-0.7, 0.2, 0.32), "lens": 26.0, "fstop": 5.6}
B = {"rel": "car", "loc": (-3.2, 7.5, 1.4), "target": (0.0, 0.0, 0.6), "lens": 28.0, "fstop": 5.6}
B_B = {"rel": "car", "loc": (-2.8, 6.5, 1.1), "target": (0.0, 0.0, 0.6), "lens": 28.0, "fstop": 5.6}
C1 = {"rel": "world", "loc": (HERO[0] - 0.10, HERO[1] - 0.12, 0.11), "target": (HERO[0], HERO[1] - 0.03, 0.075), "lens": 50.0, "fstop": 11.0}
C1_B = {"rel": "world", "loc": (HERO[0] - 0.08, HERO[1] - 0.10, 0.10), "target": (HERO[0], HERO[1] - 0.03, 0.078), "lens": 50.0, "fstop": 11.0}
C2 = {"rel": "world", "loc": (-1.3, 1.4, 0.12), "target": (-2.0, -12.0, 0.25), "lens": 30.0, "fstop": 4.0}
C2_B = {"rel": "world", "loc": (-1.3, 1.2, 0.10), "target": (-2.0, -12.0, 0.25), "lens": 30.0, "fstop": 4.0}
D = {"rel": "wheel", "loc": (-1.3, 0.9, -0.12), "target": (0.0, 0.0, -0.25), "lens": 55.0, "fstop": 5.6}
D_B = {"rel": "wheel", "loc": (-1.25, 0.8, -0.12), "target": (0.0, -0.02, -0.25), "lens": 55.0, "fstop": 5.6}
E = {"rel": "wheel", "loc": (-0.85, -0.90, -0.05), "target": (0.0, 0.0, -0.05), "lens": 32.0, "fstop": 4.0}
E_B = {"rel": "wheel", "loc": (-0.80, -0.75, -0.08), "target": (0.0, 0.0, -0.06), "lens": 32.0, "fstop": 4.0}
F = {"rel": "wheel", "loc": (-0.55, 0.62, 0.18), "target": (-0.02, 0.20, 0.0), "lens": 34.0, "fstop": 4.0}
F_B = {"rel": "wheel", "loc": (-0.50, 0.55, 0.14), "target": (-0.02, 0.20, 0.0), "lens": 36.0, "fstop": 4.0}
G = {"rel": "wheel", "loc": (-0.75, 0.25, -0.18), "target": (0.0, 0.0, -0.22), "lens": 32.0, "fstop": 4.0}
G_B = {"rel": "wheel", "loc": (-0.70, 0.15, -0.19), "target": (0.0, 0.0, -0.23), "lens": 32.0, "fstop": 4.0}
H = {"rel": "car", "loc": (-1.0, -12.0, 4.2), "target": (0.0, 4.0, 0.5), "lens": 30.0, "fstop": 8.0}
H_B = {"rel": "car", "loc": (-0.8, -10.0, 3.6), "target": (0.0, 4.0, 0.5), "lens": 30.0, "fstop": 8.0}
I = {"rel": "car", "loc": (-5.5, 7.0, 1.0), "target": (-0.6, 0.6, 0.3), "lens": 28.0, "fstop": 5.6}

CUT = {"cut": (50.0, 130.0)}
# label, variant, start (line, or (line, absolute second)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-quills-punch-in", "road", 1, [(0.0, OPEN_SIM), (2.68, 0.20)], A1, A1_B, {}, (1,)),      # held through line 1 (hook rule): both tyres cross
    ("B-sixty", "road", 2, [(0.0, -3.2), (3.05, -0.15)], B, B_B, {}, (2,)),
    ("C1-hollow-tube", "road", 3, [(0.0, -8.0), (1.97, -7.0)], C1, C1_B, {}, (3,)),
    ("C2-rows-of-quills", "road", (3, 7.70), [(0.0, -1.3), (1.87, -0.25)], C2, C2_B, {}, (3,)),
    ("D-punch-into-tread", "road", 4, [(0.0, -0.004), (3.66, 0.016)], D, D_B, {}, (4,)),
    ("E-snap-off", "road", 5, [(0.0, 0.014), (2.89, 0.08)], E, E_B, {}, (5,)),
    ("F-like-a-straw", "road", 6, [(0.0, 0.5), (3.8, 4.0)], F, F_B, dict(CUT, pose_rate=0.002, pose_t0=sm.pose_for_angle(60.0, 0.5)), (6,)),
    ("G-flat-in-half-a-minute", "road", 7, [(0.0, 0.5), (3.65, 31.0)], G, G_B, {"pose_rate": 0.002, "pose_t0": sm.pose_for_angle(45.0, 0.5)}, (7,)),
    ("H-slows-straight", "road", 8, [(0.0, 2.0), (3.41, 31.0)], H, H_B, {}, (8,)),
    ("I-loop", "road", 9, [(0.0, -1.0), (2.565, OPEN_SIM - 0.0002)], I, A1, {"loop": True}, (9,)),
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
        seg["y_shift"] = 0.0
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
    pose_t = sim if rate is None else seg["flags"].get("pose_t0", seg["sim0"]) + rate * (t - seg["t0"])
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
    """Pace rules as a gate: the opening shot held through the first line (benchmarks/hook_gate.py; replaces the competitor research's
    "first cut by 1.5 s", which cut away from the money shot), at least 18 cuts a minute, 160-200 words a minute, at most 40 s."""
    a = _audio()
    words = sum(len(b["narration_en"].split()) for b in a["beats"])
    secs = total_seconds()
    wpm = 60 * words / a["seconds"]
    cuts = 60 * len(segs) / secs
    problems = []
    problems += opening_rule(segs, line_starts()[1])          # hold the opening money shot through the first line (2026-11-22 data)
    if cuts < 18:
        problems.append(f"{cuts:.0f} cuts a minute (rule: at least 18)")
    if not 160 <= wpm <= 200:
        problems.append(f"narration at {wpm:.0f} words a minute (rule: 160-200)")
    if secs > 40:
        problems.append(f"{secs:.1f} s long (rule: at most 40)")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "first_cut_s": round(segs[1]["t0"], 2), "cuts_per_min": round(cuts, 1),
            "wpm": round(wpm), "seconds": secs}
