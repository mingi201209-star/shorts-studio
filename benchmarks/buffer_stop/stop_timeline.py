"""EP.36 film timeline (pure data), built like EP.18-EP.35. Frame 1 is a six-car train already shoving a friction buffer stop along
the rails at the end of a station track: buffers squashed, shoes sliding, sparks. The shot is held through line 1 (2.8 s) and cut
on line 2. Simulated time t is seconds after the train's buffers first touch the stop's (stop_motion).

Variants:
- train: the stop and the train (the stop at rest before t = 0);
- wall: the what-if, the same train into a solid wall (stop_motion.wall_state);
- split: the comparison, two panels stacked: the cab with Bumper during the stop (top) and a car stopping as hard as it can with a
  dummy at the wheel (bottom, stop_motion.car_state);
- crew: afterwards, the train gone, the crew at the slid stop, then a rail tractor pushing it back.
Flags:
- xray: the channel's reveal look, everything blueprint blue but the stop's mechanism (frame, buffers, shoes, bolts) glowing orange;
- reveal: the channel's signature cut, whose sting plays at the cut;
- heat: the shoes glow hotter (friction turning motion into heat);
- marker: the slide's length laid out on the track (about sixty feet), the rail polished where the shoes have slid;
- cab: Bumper at the controls in the lit cab; wave: he waves once the train has stopped;
- push: the crew's rail tractor pushes the stop back to its mark.
A row may start at a word inside its line (start = (line, word) or (line, word, k) for the k-th cue opening with that word) or at
a fixed film time (a float)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.buffer_stop import stop_motion as m
from benchmarks.hook_gate import opening_rule

FPS = 24
END_PAD_S = 0.25
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep36-audio/audio-validation.json"


def cam(loc, target, lens, fstop=11.0, rel="world"):
    """rel "world": coordinates as given; rel "stop": y measured from the stop's current position (a tracking shot); rel "train":
    y measured from the train's front."""
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


# the track runs along +y; the stop's buffer faces at y = 0 at rest (+y is behind the stop); the platform is on the left (x < 0)
A1 = cam((3.3, 3.9, 1.75), (-0.2, -0.7, 1.05), 22.0, rel="stop")          # ahead-right of the sliding stop: the train shoving it, shoes sparking
A1_B = cam((3.15, 3.7, 1.7), (-0.2, -0.7, 1.05), 22.0, rel="stop")
B1 = cam((-3.5, 1.4, 2.45), (0.3, -3.0, 1.7), 24.0)                        # the what-if, from the platform beside the wall: the train comes
B1_B = cam((-3.4, 1.3, 2.4), (0.3, -2.8, 1.7), 24.0)                        # at us and hits it; its cab's corner folds up in front of us
B2 = cam((1.5, 15.0, 1.4), (0.0, 1.5, 1.0), 28.0)                           # the stop at rest, the empty rails behind it to slide on
B2_B = cam((1.3, 9.5, 1.2), (0.0, 1.0, 1.0), 28.0)
C = cam((3.6, 6.8, 3.4), (0.0, 2.2, 0.2), 28.0)                             # x-ray: the shoes clamped on both rails, their bolts
C_B = cam((2.3, 4.6, 1.5), (0.75, 2.3, 0.1), 30.0)
D = cam((2.9, -1.2, 1.25), (0.85, 0.15, 1.06), 30.0, rel="stop")           # x-ray: a buffer squashing as the train's buffer hits
D_B = cam((2.6, -0.9, 1.2), (0.85, 0.2, 1.06), 30.0, rel="stop")
E1 = cam((4.0, 3.0, 0.75), (0.0, 0.8, 0.55), 26.0, rel="stop")             # low beside the stop: shoved along, sparks off the shoes
E1_B = cam((3.8, 3.4, 0.75), (0.0, 1.0, 0.55), 26.0, rel="stop")
E2 = cam((1.1, 5.55, 0.3), (0.72, 3.1, 0.03), 26.0, rel="stop")            # thermal look, low just ahead of the last shoe: the shoes on the
E2_B = cam((1.05, 5.4, 0.28), (0.72, 3.1, 0.03), 26.0, rel="stop")          # rail, glowing hotter
F = cam((5.2, 27.5, 7.0), (0.0, 5.0, 0.4), 26.0)                            # behind the stop, high: its slide laid out (about 60 ft), the train coming
F_B = cam((5.0, 27.0, 6.8), (0.0, 6.5, 0.4), 26.0)
G_TOP = cam((0.4, -1.15, 2.5), (-0.45, -2.3, 2.2), 28.0, rel="train")       # split, top: inside the cab, Bumper at the controls
G_BOT = cam((2.7, 0.2, 1.2), (-0.35, -0.2, 0.95), 30.0, rel="car")          # split, bottom: beside the car, the dummy thrown forward
H = cam((0.5, 1.8, 3.0), (-0.45, -2.2, 2.55), 40.0, rel="train")            # Bumper through the windscreen, waving
H_B = cam((0.45, 1.6, 2.98), (-0.45, -2.2, 2.55), 40.0, rel="train")
I1 = cam((2.8, 1.0, 1.4), (0.7, 2.6, 0.2), 28.0, rel="stop")               # the crew loosening a shoe's bolts
I1_B = cam((2.6, 1.4, 1.35), (0.7, 2.8, 0.2), 28.0, rel="stop")
I2 = cam((-3.3, -1.2, 2.15), (0.3, 9.0, 0.8), 26.0)                         # from the platform end: the tractor pushing the stop back to its mark
I2_B = cam((-3.2, -1.8, 2.15), (0.3, 6.0, 0.8), 26.0)

TRAIN, WALL, SPLIT, CREW = "train", "wall", "split", "crew"
XR = {"xray": True}
# label, start, knots [(film s from shot start, simulated s)], cam a, cam b, variant, flags, lines
ROWS = [
    ("A1-slides", 1, [(0.0, 0.25), (2.82, 0.90)], A1, A1_B, TRAIN, {}, (1,)),                      # held through line 1
    ("B1-wall", 2, [(0.0, -0.85), (2.74, 0.45)], B1, B1_B, WALL, {}, (2,)),
    ("B2-built-to-slide", (2, "buffer"), [(0.0, -9.0), (1.92, -8.0)], B2, B2_B, TRAIN, {}, (2,)),
    ("C-shoes", 3, [(0.0, -7.0), (3.63, -6.0)], C, C_B, TRAIN, dict(XR, reveal=True), (3,)),
    ("D-buffers", 4, [(0.0, -0.25), (3.57, 0.22)], D, D_B, TRAIN, dict(XR), (4,)),
    ("E1-shoved", 5, [(0.0, 0.22), (3.10, 2.0)], E1, E1_B, TRAIN, {}, (5,)),
    ("E2-heat", (5, "and"), [(0.0, 2.0), (2.74, 4.0)], E2, E2_B, TRAIN, dict(XR, heat=True), (5,)),
    ("F-sixty-feet", 6, [(0.0, -1.2), (3.6, 5.5)], F, F_B, TRAIN, {"marker": True}, (6,)),
    ("G-gentler", 7, [(0.0, 0.0), (2.92, 2.9)], G_TOP, G_BOT, SPLIT, {"cab": True}, (7,)),
    ("H-thats-me", 8, [(0.0, 5.6), (2.36, 7.96)], H, H_B, TRAIN, {"cab": True, "wave": True}, (8,)),
    ("I1-loosen", 9, [(0.0, 0.0), (3.05, 1.0)], I1, I1_B, CREW, {}, (9,)),
    ("I2-push-back", (9, "it"), [(0.0, 1.0), (1.98, 2.0)], I2, I2_B, CREW, {"push": True}, (9,)),
]


def _audio() -> dict:
    return json.loads(AUDIO.read_text())


def line_starts() -> list[float]:
    return [b["start"] for b in _audio()["beats"]]


def total_seconds() -> float:
    return round(_audio()["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def word_start(line: int, word: str, k: int = 1) -> float:
    """Start of the k-th caption cue that opens with `word` inside narration line `line` (cue times are the voice's word timings)."""
    a = _audio()
    b = a["beats"][line - 1]
    hits = [c["start"] for c in a["cues"] if b["start"] - 1e-6 <= c["start"] < b["end"] and c["text"].split()[0].strip(".,!?").lower() == word.lower()]
    if len(hits) < k:
        raise ValueError(f"no cue number {k} starting with {word!r} in line {line}")
    return hits[k - 1]


def _start(st) -> float:
    if isinstance(st, float):
        return st
    return line_starts()[st - 1] if isinstance(st, int) else word_start(*st)


def segments() -> list[dict]:
    total = total_seconds()
    t = [_start(r[1]) for r in ROWS] + [total]
    out = []
    for i, (label, _, knots, ca, cb, variant, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        seg = {"label": label, "t0": t0, "t1": t1, "knots": list(knots), "cam_a": ca, "cam_b": cb, "variant": variant, "flags": flags,
               "lines": lines}
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
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    if seg["variant"] == SPLIT:                 # two panels, each with its own fixed camera
        c = {"top": a, "bottom": b}
    else:
        c = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
             "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
             "fstop": a.get("fstop", 8.0) + (b.get("fstop", 8.0) - a.get("fstop", 8.0)) * uc}
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim_time(seg, t), "variant": seg["variant"], "cam": c, "u": u,
          "split": seg["variant"] == SPLIT}
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
