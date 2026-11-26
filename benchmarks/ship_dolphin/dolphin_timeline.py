"""EP.33 film timeline (pure data), built like EP.18-EP.32: frame 1 is a big ship's bow already crushing into a round dolphin in front of
a bridge pier, water and concrete chips thrown up, the bridge's tower behind, held through the first line (hook rule). Simulated time
t: seconds after the bow first touches the dolphin (dolphin_motion). Flags: cut (the near half of the struck dolphin, the sea and the
sea bed are cut away along the ship's line: the steel ring, its rock fill and the bed in section), reveal (the channel's signature
cut-away moment: its sting plays at the cut), force (the load path glows: ring, rock and bed). A row may start at a word inside its
line (start = (line, word))."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.hook_gate import opening_rule
from benchmarks.ship_dolphin import dolphin_motion as m

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.6
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep33-audio/audio-validation.json"
CY = m.dolphin_centres()[m.HIT][1]


def cam(loc, target, lens, fstop=11.0):
    return {"rel": "world", "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((34.0, CY - 22.0, 7.0), (-2.0, CY - 5.0, 4.0), 28.0)            # side-front, low: the bow crushing into the dolphin, the tower behind
A1_B = cam((32.0, CY - 20.0, 6.6), (-2.0, CY - 4.5, 4.0), 28.0)
B = cam((150.0, CY - 210.0, 95.0), (0.0, CY + 10.0, 10.0), 26.0)          # high: the bridge, the pier, the arc of dolphins, the ship coming
B_B = cam((140.0, CY - 195.0, 88.0), (0.0, CY + 12.0, 10.0), 26.0)
C = cam((24.0, CY - 26.0, 8.0), (0.0, CY, 1.5), 30.0)                     # one dolphin: a round island of steel and concrete
C_B = cam((22.0, CY - 22.0, 7.0), (0.0, CY, 1.5), 30.0)
D1 = cam((44.0, CY + 2.0, -6.0), (0.0, CY, -9.0), 30.0)                   # cut open: the steel ring down into the sea bed
D1_B = cam((40.0, CY + 1.0, -5.0), (0.0, CY, -8.0), 30.0)
D2 = cam((18.0, CY + 3.0, -1.0), (0.0, CY, -4.0), 30.0)                   # closer: the crushed rock packed inside
D2_B = cam((16.0, CY + 2.0, -1.5), (0.0, CY, -4.5), 30.0)
E = cam((46.0, CY - 8.0, -1.0), (0.0, CY - 6.0, -3.0), 26.0)              # in section: the bow pushes, the ring bends, the rock packs
E_B = cam((44.0, CY - 7.0, -1.0), (0.0, CY - 5.5, -3.0), 26.0)
F = cam((32.0, CY - 26.0, 10.0), (0.0, CY - 11.0, 4.0), 30.0)            # the bow crumpling against the dolphin
F_B = cam((30.0, CY - 24.0, 9.5), (0.0, CY - 10.5, 4.0), 30.0)
G = cam((120.0, CY + 10.0, 40.0), (0.0, CY + 5.0, 6.0), 30.0)             # high side: the ship stopped, the pier untouched
G_B = cam((112.0, CY + 10.0, 37.0), (0.0, CY + 5.0, 6.0), 30.0)
H = cam((40.0, CY - 16.0, 2.0), (0.0, CY - 2.0, -6.0), 28.0)              # in section, the load glowing through ring, rock and bed
H_B = cam((38.0, CY - 15.0, 2.0), (0.0, CY - 2.0, -6.0), 28.0)
I = cam((60.0, CY - 120.0, 22.0), (0.0, CY - 30.0, 8.0), 28.0)            # loop: the ship comes on toward the bridge, into frame 1

CUT = {"cut": True}
# label, start (line, or (line, first word of the cut)), knots [(film s from shot start, simulated s)], cam a, cam b, flags, lines
ROWS = [
    ("A1-bow-hits", 1, [(0.0, OPEN_SIM), (2.81, 1.95)], A1, A1_B, {}, (1,)),                   # held through line 1 (hook rule)
    ("B-guards", 2, [(0.0, -46.0), (3.62, -38.0)], B, B_B, {}, (2,)),
    ("C-dolphins", 3, [(0.0, -36.0), (2.25, -33.0)], C, C_B, {}, (3,)),
    ("D1-steel-ring", 4, [(0.0, -30.0), (1.6, -29.0)], D1, D1_B, dict(CUT, reveal=True), (4,)),
    ("D2-crushed-rock", (4, "with"), [(0.0, -29.0), (3.2, -27.0)], D2, D2_B, dict(CUT), (4,)),
    ("E-ring-bends", 5, [(0.0, -0.2), (3.56, 2.4)], E, E_B, dict(CUT), (5,)),
    ("F-bow-crumples", 6, [(0.0, 0.0), (3.11, 2.5)], F, F_B, {}, (6,)),
    ("G-stops-short", 7, [(0.0, 2.2), (2.8, 5.0)], G, G_B, {}, (7,)),
    ("H-thirty-million", 8, [(0.0, 0.3), (3.24, 2.6)], H, H_B, dict(CUT, force=True), (8,)),
    ("I-loop", 9, [(0.0, -14.0), (3.8, -1.2), (5.24, OPEN_SIM - 0.004)], I, A1, {"loop": True}, (9,)),   # last frame = the opening
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
    for i, (label, _, knots, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        kn = list(knots)
        if flags.get("loop"):                                   # the loop's last knot lands exactly on the film's last frame
            scale = (last_frame_t - t0) / kn[-1][0]
            kn = [(round(a * scale, 6), s) for a, s in kn]
        seg = {"label": label, "t0": t0, "t1": t1, "knots": kn, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines}
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
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim_time(seg, t), "cam": c, "u": u}
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
