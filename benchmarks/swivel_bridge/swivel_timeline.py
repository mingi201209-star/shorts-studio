"""EP.30 film timeline (pure data), built like EP.20-EP.29: frame 1 is the bridge in mid-turn, swinging out over the railway
(time-lapse), held through the first line (hook rule). Each row's knots are (share of the shot, story time); the loop row's last
knot lands exactly on the film's last frame. Story time t (s): the turn runs from t = 0 to 68 minutes (swivel_motion); the railway's
window from -15 to +95 minutes. Flags: 'ghost' shows where the bridge will sit, 'section' cuts the swivel open, 'clock' adds a
clock's minute hand turning about the pier."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from benchmarks.hook_gate import opening_rule
from benchmarks.swivel_bridge import swivel_motion as sm

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 1500.0
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep30-audio/audio-validation.json"
PX, PY = sm.PIER


def train_x(k: int, t: float) -> float | None:
    """Front of train k (x along the tracks) at story time t, or None when it is out of the picture."""
    if k == 0:
        return 30.0 * (t + 2458.0) if -2520.0 <= t <= -2380.0 else None          # passes beside the bridge before the window
    if sm.WINDOW[0] <= t < 5785.0:
        return -420.0                                                             # waits at the red signal
    if 5785.0 <= t <= 5900.0:
        return -420.0 + 25.0 * (t - 5785.0)                                       # rolls under the turned bridge
    return None


TRACK_OF = (-5.0, 1.7)


def cam(loc, target, lens, fstop=8.0):
    return {"loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((-80.0, 116.6, 120.0), (0.0, -22.0, 8.0), 20.0, 11.0)                 # from high up: mid-turn, swinging out over the railway
A1_B = cam((-77.5, 112.3, 117.0), (0.0, -22.0, 8.0), 20.0, 11.0)
B = cam((-175.0, 8.0, 5.0), (-70.0, -20.0, 12.0), 24.0, 8.0)                    # built beside the tracks: a train rushes past
B_B = cam((-171.0, 8.0, 5.0), (-70.0, -20.0, 12.0), 24.0, 8.0)
C1 = cam((60.0, 30.0, 22.0), (-40.0, -12.0, 4.0), 26.0, 11.0)                # trains can't stop for long: one runs past
C1_B = cam((54.0, 30.0, 21.0), (-40.0, -12.0, 4.0), 26.0, 11.0)
C = cam((150.0, -260.0, 150.0), (-10.0, -10.0, 0.0), 26.0, 11.0)               # where it will sit (translucent)
C_B = cam((140.0, -250.0, 145.0), (-10.0, -8.0, 0.0), 26.0, 11.0)
D = cam((PX - 8.60, PY + 4.26, 1.45), (PX, PY, 0.42), 50.0, 8.0)                 # the swivel cut open, square to the cut: one giant ball joint
D_B = cam((PX - 8.29, PY + 4.10, 1.4), (PX, PY, 0.42), 50.0, 8.0)
E1 = cam((PX + 12.0, PY - 16.0, 1.6), (PX - 6.0, PY + 8.0, 14.0), 22.0, 8.0)  # 46,000 tons on one pier
E1_B = cam((PX + 11.0, PY - 15.0, 1.6), (PX - 6.0, PY + 8.0, 15.0), 22.0, 8.0)
E = cam((112.1, -124.5, 28.5), (-97.3, 67.0, 14.0), 26.0, 11.0)                 # almost 900 ft long: along the deck from one end
E_B = cam((109.0, -120.5, 28.0), (-97.3, 67.0, 14.0), 26.0, 11.0)
F = cam((PX - 15.0, PY - 13.0, 4.5), (PX, PY, 1.0), 28.0, 5.6)                # the turntable slowly turning
F_B = cam((PX - 14.0, PY - 12.0, 4.2), (PX, PY, 1.0), 28.0, 5.6)
G = cam((PX, PY + 20.0, 230.0), (PX, PY + 21.0, 0.0), 26.0, 11.0)              # from above: 52.4 degrees in 68 minutes
G_B = cam((PX, PY + 20.0, 222.0), (PX, PY + 21.0, 0.0), 26.0, 11.0)
H = cam((PX - 70.0, PY - 150.0, 160.0), (PX, PY + 5.0, 0.0), 26.0, 11.0)       # a clock's minute hand races round it
H_B = cam((PX - 66.0, PY - 145.0, 156.0), (PX, PY + 5.0, 0.0), 26.0, 11.0)
I = cam((-450.0, -16.0, 6.0), (-150.0, 5.0, 12.0), 50.0, 11.0)                 # the railway's window: a train waits at red
I_B = cam((-448.0, -16.0, 6.2), (-150.0, 5.0, 12.0), 50.0, 11.0)
J = cam((20.0, 13.0, 3.0), (-30.0, 0.0, 9.0), 26.0, 8.0)                        # trains roll underneath again
J_B = cam((18.0, 13.0, 3.0), (-30.0, 0.0, 9.0), 26.0, 8.0)
K = cam((-100.0, 160.0, 160.0), (0.0, -22.0, 8.0), 20.0, 11.0)                 # loop: into frame 1

# label, start line, knots [(share of the shot, story s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-bridge-spinning", 1, [(0.0, OPEN_SIM), (1.0, 2400.0)], A1, A1_B, {}, (1,)),                      # held through line 1
    ("B-built-beside-tracks", 2, [(0.0, -2466.0), (1.0, -2462.0)], B, B_B, {}, (2,)),
    ("C1-trains-cant-stop", 3, [(0.0, -2462.0), (1.0, -2459.0)], C1, C1_B, {}, (3,)),
    ("C2-turned-into-place", 3.5, [(0.0, -1200.0), (1.0, -950.0)], C, C_B, {"ghost": True}, (3,)),
    ("D-one-ball-joint", 4, [(0.0, 1800.0), (1.0, 2300.0)], D, D_B, {"section": True}, (4,)),
    ("E1-46000-tons", 5, [(0.0, 3000.0), (1.0, 3150.0)], E1, E1_B, {}, (5,)),
    ("E2-900-feet-long", 5.5, [(0.0, 3150.0), (1.0, 3300.0)], E, E_B, {}, (5,)),
    ("F-turns-on-the-joint", 6, [(0.0, 600.0), (1.0, 1600.0)], F, F_B, {}, (6,)),
    ("G-52-degrees-68-minutes", 7, [(0.0, 0.0), (1.0, sm.T_TURN)], G, G_B, {"angle": True}, (7,)),
    ("H-minute-hand", 8, [(0.0, 1800.0), (1.0, 2700.0)], H, H_B, {"clock": True}, (8,)),
    ("I-two-hour-window", 9, [(0.0, 3000.0), (1.0, 3600.0)], I, I_B, {}, (9,)),
    ("J-trains-roll-again", 10, [(0.0, 5798.0), (1.0, 5805.0)], J, J_B, {}, (10,)),
    ("K-loop", 11, [(0.0, 300.0), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),             # last frame = the opening
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
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim, "cam": c, "u": u}
    st.update(seg["flags"])
    return st


def subject_box(t: float) -> tuple[tuple, tuple]:
    """The subject: the deck at story time t, as a world box (axis-aligned round the turned deck)."""
    e0, e1 = sm.deck_ends(t)
    h = sm.heading(t)
    n = np.array([math.cos(h), -math.sin(h)]) * sm.DECK_W / 2
    pts = np.array([e0 + n, e0 - n, e1 + n, e1 - n])
    return (float(pts[:, 0].min()), float(pts[:, 1].min()), sm.DECK_TOP - sm.DEPTH_PIER), (float(pts[:, 0].max()), float(pts[:, 1].max()), sm.DECK_TOP + 1.1)


def deck_local_box() -> tuple[tuple, tuple]:
    """The deck as a box in the turning bridge's own frame (origin on the pier, length along local y): the hook gate projects this
    box turned with the bridge, so the subject is the deck itself rather than the square round it."""
    return (-sm.DECK_W / 2, -sm.HALF, sm.DECK_TOP - sm.DEPTH_PIER), (sm.DECK_W / 2, sm.HALF, sm.DECK_TOP + 1.1)


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
