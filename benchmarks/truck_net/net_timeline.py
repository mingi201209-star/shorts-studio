"""EP.34 film timeline (pure data), built like EP.18-EP.33. Frame 1 is a runaway semi already plowing into the first steel net of an
escape ramp: the net is wrapped over its grille, its sides are stretched back to the walls and the tapes are running out of the wall.
The shot is held through the first line (hook rule). Simulated time t is seconds after the truck's front reaches net 1 (net_motion).

Variants: truck (the 80,000 lb semi at 60 mph), rating (a 90,000 lb tanker at 90 mph), reset (the crew refilling an absorber, nets
hung again).
Flags:
- cut: the wall at net 2 is cut open (the absorber box, its coils of tape and the pins);
- reveal: the channel's signature cut-away moment, whose sting plays at the cut;
- open: net 1's right absorber with its lid off for the crew;
- driver: the cab's side window lit enough to see the driver.
A row may start at a word inside its line (start = (line, word))."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.12
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep34-audio/audio-validation.json"


def cam(loc, target, lens, fstop=11.0, rel="world"):
    """rel "world": loc and target in world coordinates; rel "front": their y is measured from the truck's front (a tracking shot)."""
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((-3.4, 9.4, 2.4), (0.0, 1.5, 1.3), 27.0)                      # inside the ramp, ahead-left: the semi plowing into net 1
A1_B = cam((-3.4, 14.2, 2.5), (0.0, 6.3, 1.3), 27.0)                   # (stays short of net 2)
B = cam((16.0, 22.0, 16.0), (-3.0, -45.0, 0.0), 24.0)                   # up the mountainside: off the highway into the nets below
B_B = cam((15.0, 24.0, 14.0), (0.0, 14.0, 1.0), 24.0)
C = cam((-2.3, -7.0, 2.2), (0.6, 40.0, 1.2), 28.0)                      # down the ramp: the nets one after another
C_B = cam((-2.0, -4.5, 2.1), (0.6, 42.0, 1.2), 28.0)
D1 = cam((1.8, 11.8, 2.2), (4.7, 13.7, 0.9), 26.0)                      # net 2's corner, its tapes into the cut-open wall
D1_B = cam((2.0, 12.3, 2.0), (4.75, 13.6, 0.9), 26.0)
D2 = cam((3.2, 11.6, 1.9), (4.95, 13.0, 0.85), 30.0)                    # the coils of tape inside the wall
D2_B = cam((3.35, 12.0, 1.75), (4.95, 13.05, 0.85), 30.0)
E1 = cam((5.0, 21.5, 3.0), (1.5, 14.5, 1.1), 24.0)                      # on the right wall: the truck hits net 2, tape whips out
E1_B = cam((5.0, 22.0, 2.9), (1.5, 16.0, 1.1), 24.0)
E2 = cam((3.65, 13.2, 1.25), (4.9, 13.95, 0.55), 32.0)                  # close: the tape dragged through the pins
E2_B = cam((3.75, 13.4, 1.15), (4.9, 14.0, 0.55), 32.0)
F = cam((-6.5, 44.0, 6.0), (0.0, 22.0, 1.0), 26.0)                      # ahead-left, high: net after net picked up
F_B = cam((-7.0, 78.0, 7.0), (0.0, 60.0, 1.0), 26.0)
G = cam((-0.9, 3.5, 3.0), (-0.5, -3.7, 2.55), 30.0, rel="front")         # tracking, in front: the nets on the grille, the driver held in the cab
G_B = cam((-0.8, 3.2, 2.95), (-0.5, -3.7, 2.55), 30.0, rel="front")
H = cam((-9.0, 14.0, 7.0), (0.0, -3.0, 1.4), 30.0, rel="front")          # tracking the 90,000 lb tanker at 90 mph, from over the gore
H_B = cam((-9.0, 12.5, 6.5), (0.0, -3.5, 1.4), 30.0, rel="front")
I = cam((2.6, -4.8, 3.6), (4.9, -1.7, 0.9), 28.0)                       # from above: the crew lowering fresh tape into net 1's absorber
I_B = cam((2.8, -4.4, 3.5), (4.9, -1.75, 0.95), 28.0)
J = cam((-3.3, 13.0, 2.1), (0.0, -20.0, 1.4), 24.0)                     # loop: the nets hung again, the next truck coming, into frame 1

TRUCK, RATING, RESET = "truck", "rating", "reset"
CUT = {"cut": True}
# label, start (line, or (line, first word of the cut)), knots [(film s from shot start, simulated s)], cam a, cam b, variant, flags, lines
ROWS = [
    ("A1-net-grabs", 1, [(0.0, OPEN_SIM), (2.70, 0.30)], A1, A1_B, TRUCK, {}, (1,)),          # held through line 1 (hook rule)
    ("B-mountain", 2, [(0.0, -2.2), (3.36, 1.0)], B, B_B, TRUCK, {}, (2,)),
    ("C-nets-in-a-row", 3, [(0.0, -9.0), (3.65, -8.0)], C, C_B, TRUCK, {}, (3,)),
    ("D1-tied-to-tape", 4, [(0.0, -7.0), (1.38, -6.6)], D1, D1_B, TRUCK, dict(CUT, reveal=True), (4,)),
    ("D2-coiled", (4, "tape"), [(0.0, -6.6), (3.09, -5.8)], D2, D2_B, TRUCK, dict(CUT), (4,)),
    ("E1-truck-hits", 5, [(0.0, 0.42), (1.68, 0.80)], E1, E1_B, TRUCK, {}, (5,)),
    ("E2-pins", (5, "is"), [(0.0, 0.58), (2.98, 1.05)], E2, E2_B, TRUCK, dict(CUT), (5,)),
    ("F-net-after-net", 6, [(0.0, 0.9), (3.79, 3.3)], F, F_B, TRUCK, {}, (6,)),
    ("G-driver", 7, [(0.0, 3.2), (2.2, 4.1), (2.72, 4.3)], G, G_B, TRUCK, {"driver": True}, (7,)),
    ("H-ninety", 8, [(0.0, 0.6), (4.04, 4.7)], H, H_B, RATING, {}, (8,)),
    ("I-fresh-tape", 9, [(0.0, 0.0), (2.17, 1.0)], I, I_B, RESET, {"open": True}, (9,)),
    ("J-loop", (9, "and"), [(0.0, -2.5), (2.48, OPEN_SIM - 0.004)], J, A1, TRUCK, {"loop": True}, (9,)),   # last frame = the opening
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
    t = [_start(r[1]) for r in ROWS] + [total]
    last_frame_t = (frame_count() - 1) / FPS
    out = []
    for i, (label, _, knots, ca, cb, variant, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        kn = list(knots)
        if flags.get("loop"):                                   # the loop's last knot lands exactly on the film's last frame
            scale = (last_frame_t - t0) / kn[-1][0]
            kn = [(round(a * scale, 6), s) for a, s in kn]
        seg = {"label": label, "t0": t0, "t1": t1, "knots": kn, "cam_a": ca, "cam_b": cb, "variant": variant, "flags": flags, "lines": lines}
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
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim_time(seg, t), "variant": seg["variant"], "cam": c, "u": u}
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
