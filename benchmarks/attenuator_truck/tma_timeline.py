"""EP.32 film timeline (pure data), built like EP.18-EP.31: frame 1 is the red car already crushing into the crash cushion on the back
of the parked work truck, aluminum skin and bumper plastic flying, held through the first line (hook rule). Simulated time t: seconds
after the car's nose meets the cushion's rear face (tma_motion). Variants: car (the red sedan), pickup (the 5,000 lb test pickup),
deploy (no vehicle; the cushion swings down from upright, fold_angle). Flags: cut (the cushion's near skin is cut away to show the
honeycomb), reveal (the channel's signature cut-away moment: its sting plays at the cut), ghost (the cushion's uncrushed outline
stays drawn, so the crushed length is seen), skid (the truck's tyre marks are drawn). A row may start at a word inside its line
(start = (line, word)): the picture changes where the sentence does."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.attenuator_truck import tma_motion as m
from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.035
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep32-audio/audio-validation.json"
X = m.LANE_R


def cam(loc, target, lens, fstop=8.0):
    return {"rel": "world", "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((-1.0, -10.2, 2.6), (2.1, -2.8, 1.0), 30.0, 5.6)               # behind-left, raised: the car crushing into the cushion, the truck
A1_B = cam((-0.9, -9.9, 2.55), (2.1, -2.7, 1.0), 30.0, 5.6)
B = cam((-1.2, -16.0, 8.0), (X, 24.0, 0.8), 30.0, 11.0)               # a driver's view, raised: traffic passing, the truck, the crew beyond
B_B = cam((-1.1, -13.5, 7.6), (X, 24.0, 0.8), 30.0, 11.0)
C = cam((X + 6.5, -5.5, 2.6), (X, -1.8, 2.4), 34.0, 8.0)                # side, behind: the cushion swings down from upright
C_B = cam((X + 6.3, -5.9, 2.2), (X, -2.2, 1.4), 34.0, 8.0)
D = cam((X + 0.5, -6.8, 1.05), (X + 0.1, -3.0, 0.75), 42.0, 5.6)      # opened from the back: straight into the honeycomb, then back
D_B = cam((X + 3.2, -10.0, 2.6), (X, -3.0, 0.75), 35.0, 5.6)   # out to the three blocks sliding apart
E = cam((X + 5.4, -4.6, 2.0), (X, -2.8, 0.7), 28.0, 5.6)                # side, cut open: the rows crush one after another
E_B = cam((X + 5.2, -4.2, 1.95), (X, -2.5, 0.7), 28.0, 5.6)
F = cam((X + 6.5, -4.5, 5.0), (X, -2.5, 0.8), 30.0, 8.0)                # high side: the uncrushed outline against the crushed cushion
F_B = cam((X + 6.3, -4.1, 4.8), (X, -2.2, 0.8), 30.0, 8.0)
G1 = cam((X + 4.5, -1.5, 1.2), (X + 0.8, 2.6, 0.5), 30.0, 5.6)         # at the rear tandem: braked wheels shoved along, tyre marks
G1_B = cam((X + 4.4, -1.0, 1.15), (X + 0.8, 3.0, 0.5), 30.0, 5.6)
G2 = cam((X + 10.0, -6.0, 6.0), (X, 14.0, 0.5), 28.0, 11.0)             # wide: the truck stops after a few feet, the crew far ahead
G2_B = cam((X + 9.7, -5.2, 5.8), (X, 14.5, 0.5), 28.0, 11.0)
H = cam((X + 5.5, -20.0, 3.0), (X, -5.0, 0.9), 34.0, 8.0)               # the 5,000 lb test pickup at 62 mph
H_B = cam((X + 5.2, -18.5, 2.9), (X, -4.6, 0.9), 34.0, 8.0)
I = cam((-2.4, -64.0, 4.0), (X, -42.0, 0.8), 30.0, 5.6)                 # loop: a driver who does not see the truck, into frame 1

# label, variant, start (line, or (line, first word of the cut)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-slam", "car", 1, [(0.0, OPEN_SIM), (2.64, 0.32)], A1, A1_B, {}, (1,)),                 # held through line 1 (hook rule)
    ("B-shield", "car", 2, [(0.0, -2.2), (4.11, -0.9)], B, B_B, {}, (2,)),
    ("C-folds-down", "deploy", 3, [(0.0, 0.0), (3.41, 3.7)], C, C_B, {}, (3,)),
    ("D-honeycomb", "car", 4, [(0.0, -9.0), (2.69, -8.5)], D, D_B, {"cut": True, "reveal": True}, (4,)),
    ("E-row-by-row", "car", 5, [(0.0, -0.03), (3.3, 0.16)], E, E_B, {"cut": True}, (5,)),
    ("F-eight-feet", "car", 6, [(0.0, -0.01), (3.58, 0.62)], F, F_B, {"ghost": True, "skid": True}, (6,)),
    ("G1-braked", "car", 7, [(0.0, 0.10), (1.9, 0.48)], G1, G1_B, {"skid": True}, (7,)),
    ("G2-few-feet", "car", (7, "so"), [(0.0, 0.40), (1.8, 1.30)], G2, G2_B, {"skid": True}, (7,)),
    ("H-pickup", "pickup", 8, [(0.0, -0.26), (4.18, 0.50)], H, H_B, {}, (8,)),
    ("I-loop", "car", 9, [(0.0, -1.70), (3.0, -0.13), (4.22, OPEN_SIM - 0.0004)], I, A1, {"loop": True}, (9,)),   # last frame = the opening
]


def _audio() -> dict:
    return json.loads(AUDIO.read_text())


def line_starts() -> list[float]:
    return [b["start"] for b in _audio()["beats"]]


def total_seconds() -> float:
    return round(_audio()["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def word_start(line: int, word: str) -> float:
    """Start of the caption cue that opens with `word` inside narration line `line` (cue times are the voice's own word timings)."""
    a = _audio()
    b = a["beats"][line - 1]
    for c in a["cues"]:
        if b["start"] - 1e-6 <= c["start"] < b["end"] and c["text"].split()[0].strip(".,!?").lower() == word.lower():
            return c["start"]
    raise ValueError(f"no cue starting with {word!r} in line {line}")


def _start(st) -> float:
    return line_starts()[st - 1] if isinstance(st, int) else word_start(*st)


def segments() -> list[dict]:
    total = total_seconds()
    t = [_start(r[2]) for r in ROWS] + [total]
    last_frame_t = (frame_count() - 1) / FPS
    out = []
    for i, (label, variant, _, knots, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        kn = list(knots)
        if flags.get("loop"):                                   # the loop's last knot lands exactly on the film's last frame
            scale = (last_frame_t - t0) / kn[-1][0]
            kn = [(round(a * scale, 6), s) for a, s in kn]
        seg = {"label": label, "variant": variant, "t0": t0, "t1": t1, "knots": kn, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines}
        seg["sim0"], seg["sim1"] = sim_time(seg, t0), sim_time(seg, t1 - 1e-6)
        seg["time_scale"] = round((seg["sim1"] - seg["sim0"]) / (t1 - t0), 6)
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
    if seg["flags"].get("loop"):
        uc = min(1.0, max(0.0, (t - seg["t0"]) / ((frame_count() - 1) / FPS - seg["t0"])))
        uc = uc * uc * (3 - 2 * uc)
    else:
        uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    c = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
         "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
         "fstop": a.get("fstop", 8.0) + (b.get("fstop", 8.0) - a.get("fstop", 8.0)) * uc}
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim_time(seg, t), "cam": c, "u": u}
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
