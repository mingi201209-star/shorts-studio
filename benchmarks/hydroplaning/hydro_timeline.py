"""EP.09 film timeline (pure data). Fast cuts: one segment per narration line (frozen audio in examples/episodes/ep09-audio), lab shots for
the tread facts, the wedge cutaway, the driver's useless steering, and overlays named per segment (added in assembly). The opening is the
labelled split already just before the puddle: the worn car floats at about 0.2 s of film time and runs wide; the last second runs back
into the opening moment so the Short loops."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
LOOP_S = 1.0
OPEN_SIM = 0.75
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep09-audio/audio-validation.json"

SPLIT = {"rel": "follow", "loc": (4.0, -8.5, 5.0), "target": (-1.0, 6.0, -0.8), "lens": 28.0}
SPLIT_B = {"rel": "follow", "loc": (3.4, -7.4, 4.4), "target": (-1.2, 6.5, -0.6), "lens": 30.0}
LAB_WIDE = {"rel": "lab", "loc": (0.0, -1.55, 1.05), "target": (0.0, 0.0, 0.05), "lens": 30.0}
LAB_WIDE_B = {"rel": "lab", "loc": (0.0, -1.35, 0.85), "target": (0.0, 0.0, 0.05), "lens": 32.0}
LAB_NEW = {"rel": "lab", "loc": (-0.42, -0.85, 0.42), "target": (-0.42, 0.0, 0.03), "lens": 34.0}
LAB_NEW_B = {"rel": "lab", "loc": (-0.42, -0.70, 0.30), "target": (-0.42, 0.0, 0.03), "lens": 38.0}
LAB_NEW_LOW = {"rel": "lab", "loc": (-0.68, -0.55, 0.10), "target": (-0.42, 0.0, 0.04), "lens": 40.0}
LAB_WORN_LOW = {"rel": "lab", "loc": (0.16, -0.55, 0.08), "target": (0.42, 0.0, 0.01), "lens": 40.0}
LAB_WORN = {"rel": "lab", "loc": (0.42, -0.85, 0.42), "target": (0.42, 0.0, 0.03), "lens": 34.0}
LAB_WORN_B = {"rel": "lab", "loc": (0.30, -0.65, 0.30), "target": (0.42, 0.05, 0.03), "lens": 38.0}
LAB_NEW_LOW_B = {"rel": "lab", "loc": (-0.52, -0.42, 0.07), "target": (-0.40, 0.05, 0.04), "lens": 44.0}
LAB_WORN_LOW_B = {"rel": "lab", "loc": (0.30, -0.42, 0.06), "target": (0.44, 0.05, 0.01), "lens": 44.0}
WEDGE = {"rel": "lab", "loc": (29.6, -2.6, 0.60), "target": (29.6, 0.0, 0.45), "lens": 30.0}
WEDGE_B = {"rel": "lab", "loc": (29.4, -2.0, 0.35), "target": (29.4, 0.0, 0.20), "lens": 36.0}
COIN = {"rel": "lab", "loc": (-0.55, -0.55, 0.40), "target": (-0.42, 0.20, 0.10), "lens": 34.0}
COIN_B = {"rel": "lab", "loc": (0.29, -0.55, 0.40), "target": (0.42, 0.20, 0.10), "lens": 34.0}
CAB = {"rel": "car", "loc": (0.35, 0.40, 1.20), "target": (-0.36, 0.72, 0.88), "lens": 34.0}
CAB_B = {"rel": "car", "loc": (0.30, 0.20, 1.25), "target": (-0.36, 0.72, 0.90), "lens": 30.0}
TYRE_LOW = {"rel": "car", "loc": (-2.2, 2.8, 0.45), "target": (-0.72, 1.05, 0.20), "lens": 30.0}
TYRE_LOW_B = {"rel": "car", "loc": (-1.9, 2.4, 0.35), "target": (-0.72, 1.05, 0.20), "lens": 34.0}
CHASE = {"rel": "follow", "loc": (2.5, -8.0, 3.0), "target": (-1.0, 4.0, 0.4), "lens": 28.0}
CHASE_B = {"rel": "follow", "loc": (1.8, -6.5, 2.6), "target": (-1.0, 4.0, 0.4), "lens": 30.0}

# label, variant, sim start, sim end (None = real time), cam a, cam b, flags, narration lines
ROWS = [
    ("A-split", "both", OPEN_SIM, None, SPLIT, SPLIT_B, {"split": True}, (1,)),
    ("B-tread-depth", "new", 0.0, 0.0, LAB_WIDE, LAB_WIDE_B, {"lab": "sections"}, (2,)),
    ("C-drains", "new", 0.0, 0.0, LAB_NEW, LAB_NEW_B, {"lab": "flow"}, (3,)),
    ("D-eight-mm", "new", 0.0, 0.0, LAB_NEW_LOW, LAB_NEW_LOW_B, {"lab": "sections"}, (4,)),
    ("E-one-point-six", "worn", 0.0, 0.0, LAB_WORN_LOW, LAB_WORN_LOW_B, {"lab": "sections"}, (5,)),
    ("F-cant-escape", "worn", 0.0, 0.0, LAB_WORN, LAB_WORN_B, {"lab": "pool"}, (6,)),
    ("G-wedge", "worn", 0.0, 0.0, WEDGE, WEDGE_B, {"lab": "wedge", "float_ramp": True}, (7,)),
    ("H-steering-useless", "worn", 0.95, 2.05, CAB, CAB_B, {"interior": True}, (8,)),
    ("I-nasa", "worn", 0.90, 1.40, TYRE_LOW, TYRE_LOW_B, {}, (9,)),
    ("J-formula", "worn", 0.0, 0.0, WEDGE_B, WEDGE, {"lab": "wedge", "float": 1.0}, (10,)),
    ("K-fifty", "both", OPEN_SIM, OPEN_SIM + 2.2, SPLIT, SPLIT_B, {"split": True}, (11,)),
    ("L-penny", "worn", 0.0, 0.0, COIN, COIN_B, {"lab": "sections", "coin_ramp": True}, (12,)),
    ("M-ease-off", "worn", 1.80, 3.60, CHASE, CHASE_B, {}, (13,)),
    ("N-loop-run-in", "both", OPEN_SIM - LOOP_S, OPEN_SIM, SPLIT, SPLIT, {"split": True}, (13,)),
]


def line_starts() -> list[float]:
    return [b["start"] for b in json.loads(AUDIO.read_text())["beats"]]


def total_seconds() -> float:
    return round(json.loads(AUDIO.read_text())["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def segments() -> list[dict]:
    s = line_starts()
    total = total_seconds()
    t = [s[row[7][0] - 1] for row in ROWS[:-1]] + [total - LOOP_S, total]
    out = []
    for i, (label, variant, a, b, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        sim1 = b if b is not None else a + (t1 - t0)
        out.append({"label": label, "variant": variant, "t0": t0, "t1": t1, "sim0": a, "sim1": sim1, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines,
                    "time_scale": round((sim1 - a) / (t1 - t0), 5)})
    return out


def _smooth(u):
    return u * u * (3 - 2 * u)


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    sim = seg["sim0"] + (seg["sim1"] - seg["sim0"]) * u
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    cam = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])), "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])),
           "lens": a["lens"] + (b["lens"] - a["lens"]) * uc}
    flags = dict(seg["flags"])
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": cam, "u": u}
    if flags.pop("float_ramp", False):
        flags["float"] = min(1.0, u * 1.4)
    if flags.pop("coin_ramp", False):
        flags["coin"] = ("new", min(1.0, u * 2.2)) if u < 0.5 else ("worn", min(1.0, (u - 0.5) * 2.2))
    st.update(flags)
    return st


def scene_alignment(segs: list[dict]) -> dict:
    problems, rows = [], []
    for k, st in enumerate(line_starts(), 1):
        seg = next((s for s in segs if s["t0"] <= st + 0.05 < s["t1"]), None)
        rows.append({"line": k, "cue_s": round(st, 2), "segment": seg["label"] if seg else None})
        if seg is None or k not in seg["lines"]:
            problems.append(f"line {k} at {st:.2f}s shows {seg['label'] if seg else 'nothing'}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows}
