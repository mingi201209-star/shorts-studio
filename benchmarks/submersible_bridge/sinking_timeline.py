"""EP.27 film timeline (pure data), built like EP.20-EP.26: frame 1 is the road at the mouth of the Corinth Canal going under the sea
behind the waiting cars, held through the first line (hook rule). Each row's knots are (share of the shot, story time); the loop
row's last knot lands exactly on the film's last frame. Story time t (s): the deck starts down at t = 0 (sinking_motion), the tall
ship passes over it at about t = 170-196, the deck comes back up from t = 232. Flags: 'ghost' shows a lift bridge that would do the
same job (translucent), 'under' marks underwater shots."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.submersible_bridge import sinking_motion as sm

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 22.0                                    # frame 1: the sea just flooding over the road (deck 0.13 m under)
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep27-audio/audio-validation.json"


def cam(loc, target, lens, fstop=8.0):
    return {"loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((-28.5, -6.0, 4.4), (-8.0, 3.5, -1.0), 24.0, 11.0)            # from the approach: the road running on into the sea
A1_B = cam((-28.1, -5.9, 4.2), (-8.0, 3.6, -1.2), 24.0, 11.0)
B = cam((-30.4, 2.5, 3.1), (-6.0, -1.2, -0.2), 28.0, 11.0)
B = cam((0.0, 300.0, 76.0), (0.0, 0.0, -2.0), 28.0, 11.0)              # above the canal cut, looking down it to the bridge and the sea
B_B = cam((0.0, 282.0, 73.0), (0.0, -6.0, -2.0), 28.0, 11.0)
C = cam((-29.5, -0.6, 2.3), (-18.0, -1.2, 1.5), 30.0, 8.0)              # behind the red car: the gate comes down in front of it
C_B = cam((-29.2, -0.7, 2.25), (-18.0, -1.2, 1.4), 30.0, 8.0)
D = cam((0.0, -14.0, -4.5), (0.0, 0.0, -4.8), 24.0, 11.0)              # under water: the whole road sinking
D_B = cam((0.0, -13.5, -5.0), (0.0, 0.0, -5.5), 24.0, 11.0)
E = cam((-12.0, -5.0, 1.6), (-16.4, -2.0, -1.5), 30.0, 5.6)            # the deck's end sliding down past the depth bands
E_B = cam((-12.2, -5.1, 1.4), (-16.4, -2.0, -2.0), 30.0, 5.6)
F = cam((6.0, -7.5, -6.8), (1.0, 0.0, -8.2), 24.0, 8.0)                # under water: settling on the bottom
F_B = cam((5.6, -7.0, -6.9), (1.0, 0.0, -8.3), 24.0, 8.0)
G = cam((5.0, -10.0, -7.0), (0.0, 2.0, -2.0), 20.0, 8.0)               # under water, looking up: the ship over the drowned road
G_B = cam((4.6, -9.0, -7.0), (0.0, 4.0, -2.0), 20.0, 8.0)
H = cam((-19.0, -8.0, 1.9), (0.0, 6.0, 14.0), 22.0, 11.0)              # from the quay: the masts pass, nothing above the water
H_B = cam((-19.0, -7.0, 1.9), (0.0, 9.0, 14.0), 22.0, 11.0)
I = cam((-55.0, -40.0, 22.0), (0.0, 2.0, 20.0), 26.0, 11.0)            # what a lift bridge would need (translucent towers)
I_B = cam((-52.0, -37.0, 21.5), (0.0, 4.0, 20.0), 26.0, 11.0)
J1 = cam((-18.0, -6.0, 2.4), (0.0, 25.0, 6.0), 26.0, 11.0)             # the ship goes on into the cut
J1_B = cam((-18.0, -5.0, 2.4), (0.0, 35.0, 6.0), 26.0, 11.0)
J2 = cam((-12.0, -9.0, 1.6), (-4.0, 0.0, 0.2), 30.0, 8.0)              # the road rises again, dripping wet
J2_B = cam((-12.3, -9.2, 1.9), (-4.0, 0.0, 0.6), 30.0, 8.0)
K = cam((-48.0, 14.0, 9.0), (-14.0, -2.0, 0.0), 26.0, 11.0)            # loop: the cars wait, the road starts down: into frame 1

# label, start line, knots [(share of the shot, story s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-road-sinking", 1, [(0.0, OPEN_SIM), (1.0, 36.0)], A1, A1_B, {}, (1,)),                     # held through line 1
    ("B-corinth-canal", 2, [(0.0, 40.0), (1.0, 60.0)], B, B_B, {}, (2,)),
    ("C-gates-stop-traffic", 3, [(0.0, -46.0), (1.0, -30.0)], C, C_B, {}, (3,)),
    ("D-sinks-26-feet", 4, [(0.0, 0.0), (1.0, 142.0)], D, D_B, {"under": True}, (4,)),
    ("E-13-feet-a-minute", 5, [(0.0, 40.0), (1.0, 70.0)], E, E_B, {}, (5,)),
    ("F-on-the-bottom", 6, [(0.0, 124.0), (1.0, 150.0)], F, F_B, {"under": True}, (6,)),
    ("G-ships-sail-over", 7, [(0.0, 166.0), (1.0, 198.0)], G, G_B, {"under": True}, (7,)),
    ("H-no-mast-too-tall", 8, [(0.0, 176.0), (1.0, 192.0)], H, H_B, {}, (8,)),
    ("I-lift-bridge-towers", 9, [(0.0, 179.0), (1.0, 190.0)], I, I_B, {"ghost": True}, (9,)),
    ("J1-ship-passed", 10, [(0.0, 196.0), (1.0, 230.0)], J1, J1_B, {}, (10,)),
    ("J2-rises-dripping", 10.45, [(0.0, 352.0), (1.0, 368.0)], J2, J2_B, {}, (10,)),
    ("K-loop", 11, [(0.0, -8.0), (1.0, OPEN_SIM - 0.0002)], K, A1, {"loop": True}, (11,)),            # last frame = the opening
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
    """Shot start: a line's start, or part of the way through a line for a second shot on the same line (10.45: "the road rises")."""
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
    rate = (sim_time(seg, min(t + 0.5 / FPS, seg["t1"] - 1e-6)) - sim_time(seg, max(t - 0.5 / FPS, seg["t0"]))) * FPS
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim, "cam": c, "u": u, "time_scale": rate}
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


def deck_box(t: float) -> tuple[tuple, tuple]:
    """The subject (the bridge deck) as a world box at story time t: the road surface and the girders under it."""
    z = sm.deck_z(t)
    return (-sm.DECK_L / 2, -sm.DECK_W / 2, z - sm.DECK_DEPTH), (sm.DECK_L / 2, sm.DECK_W / 2, z + 0.9)
