"""EP.08 film timeline (pure data, no Blender). Segments start with their narration lines (frozen audio in examples/episodes/ep08-audio).
Simulated time is dt after first contact with the wall; the 0.1 s crash is shown in deep slow motion. The opening is the labelled split
(top: airbag, bottom: none) already 25 ms into the crash, so the bag is visibly opening in the first frames and the bare head hits the
wheel at about 1.3 s of film time; the last second is the approach to the wall, looping back into frame 0."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.airbag.airbag_shots import ACU, FACE, HUB, HUB_SIDE, SIDE_XRAY

FPS = 24
END_PAD_S = 0.25
LOOP_S = 1.0
OPEN_DT = 0.025
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep08-audio/audio-validation.json"

SIDE_XRAY_B = {"loc": (-1.85, 0.48, 1.08), "target": (-0.35, 0.70, 0.86), "lens": 26.0}
FACE_B = {"loc": (0.42, 0.66, 1.06), "target": (-0.36, 0.40, 0.95), "lens": 32.0}
HUB_CUT = {"loc": (0.05, 0.50, 1.22), "target": (-0.36, 0.72, 0.88), "lens": 60.0}
HUB_CUT_B = {"loc": (-0.02, 0.55, 1.15), "target": (-0.36, 0.72, 0.88), "lens": 75.0}
SEAM = {"loc": (-0.12, 0.32, 1.22), "target": (-0.36, 0.72, 0.88), "lens": 60.0}
SEAM_B = {"loc": (-0.14, 0.36, 1.20), "target": (-0.36, 0.72, 0.88), "lens": 48.0}
BAG_SIDE = {"loc": (0.35, 0.45, 1.10), "target": (-0.36, 0.55, 0.95), "lens": 34.0}
BAG_SIDE_B = {"loc": (0.30, 0.30, 1.02), "target": (-0.36, 0.55, 0.95), "lens": 38.0}
ACU_B = {"loc": (0.90, 0.12, 0.60), "target": (0.0, 0.30, 0.33), "lens": 130.0}

# label, variant, dt start, dt end (None = real time), cam a, cam b, flags, narration lines
ROWS = [
    ("A-split-crash", "both", OPEN_DT, OPEN_DT + 0.105, SIDE_XRAY, SIDE_XRAY_B, {"split": True, "xray": True}, (1,)),
    ("B-head-keeps-going", "off", 0.020, 0.058, FACE, FACE_B, {"interior": True}, (2,)),
    ("C-hits-the-wheel", "off", 0.058, 0.080, FACE_B, FACE_B, {"interior": True}, (3,)),
    ("D-sensor-feels", "on", 0.000, 0.010, ACU, ACU_B, {"xray": True, "sensor": True}, (4,)),
    ("E-decides", "on", 0.010, 0.0135, ACU_B, ACU, {"xray": True, "sensor": True}, (5,)),
    ("F-igniter", "on", 0.0105, 0.0140, HUB_CUT, HUB_CUT_B, {"interior": True, "cutaway": True}, (6,)),
    ("G-gas-generator", "on", 0.0140, 0.0200, HUB_CUT_B, HUB_CUT, {"interior": True, "cutaway": True}, (7,)),
    ("H-cover-splits", "on", 0.0120, 0.0220, SEAM, SEAM_B, {"interior": True}, (8,)),
    ("I-bag-fills", "on", 0.0200, 0.0420, HUB_SIDE, FACE, {"interior": True}, (9,)),
    ("J-holes", "on", 0.0420, 0.0520, BAG_SIDE, BAG_SIDE_B, {"interior": True}, (10,)),
    ("K-head-sinks", "on", 0.0420, 0.0900, FACE, FACE_B, {"interior": True}, (11,)),
    ("L-gentle-vs-bounce", "both", 0.0500, 0.1400, SIDE_XRAY, SIDE_XRAY_B, {"split": True, "xray": True}, (12,)),
    ("M-sit-back", "on", 0.0900, 0.2200, FACE_B, FACE, {"interior": True}, (13,)),
    ("N-loop-run-in", "both", OPEN_DT - 0.060, OPEN_DT, SIDE_XRAY, SIDE_XRAY, {"split": True, "xray": True}, (13,)),
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
        out.append({"label": label, "variant": variant, "t0": t0, "t1": t1, "sim0": a, "sim1": b, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines,
                    "time_scale": round((b - a) / (t1 - t0), 5)})
    return out


def _smooth(u):
    return u * u * (3 - 2 * u)


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    dt = seg["sim0"] + (seg["sim1"] - seg["sim0"]) * u
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    cam = {"loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])), "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])),
           "lens": a["lens"] + (b["lens"] - a["lens"]) * uc}
    return {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "dt": dt, "t": dt, "cam": cam, **seg["flags"]}


def scene_alignment(segs: list[dict]) -> dict:
    problems, rows = [], []
    for k, st in enumerate(line_starts(), 1):
        seg = next((s for s in segs if s["t0"] <= st + 0.05 < s["t1"]), None)
        rows.append({"line": k, "cue_s": round(st, 2), "segment": seg["label"] if seg else None})
        if seg is None or k not in seg["lines"]:
            problems.append(f"line {k} at {st:.2f}s shows {seg['label'] if seg else 'nothing'}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows}
