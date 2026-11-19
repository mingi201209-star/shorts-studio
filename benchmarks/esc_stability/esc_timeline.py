"""EP.07 film timeline (pure data, no Blender). A segment starts when its first narration line starts (frozen narration in
examples/episodes/ep07-audio). Each segment maps film time to simulated time and moves the camera from cam_a to cam_b. The film opens on
the split screen already into the swerve (the car without ESC is visibly sliding inside the first second) and its last second runs back
into the opening moment so the Short loops."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
LOOP_S = 1.0
OPEN_SIM = 1.7          # by film time 1 s (sim 2.7) the car without ESC has turned past 65 degrees, the ESC car is straight
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep07-audio/audio-validation.json"

SPLIT = {"rel": "follow", "loc": (4.5, -7.5, 6.5), "target": (-0.5, 4.0, -1.8), "lens": 28.0}
SPLIT_B = {"rel": "follow", "loc": (3.6, -6.2, 5.6), "target": (-0.5, 4.5, -1.5), "lens": 30.0}
REAR_LOW = {"rel": "car", "loc": (-2.2, -3.2, 0.55), "target": (-0.6, -1.2, 0.25), "lens": 30.0}
REAR_LOW_B = {"rel": "car", "loc": (-2.0, -2.6, 0.45), "target": (-0.7, -1.2, 0.25), "lens": 32.0}
REAR_WIDE = {"rel": "car", "loc": (-2.6, -3.8, 0.9), "target": (-0.5, -1.0, 0.3), "lens": 28.0}
REAR_WIDE_B = {"rel": "car", "loc": (-3.4, -4.6, 1.6), "target": (-0.3, -0.5, 0.2), "lens": 26.0}
TOP = {"rel": "follow", "loc": (0.0, -3.0, 8.5), "target": (0.0, 2.5, 0.0), "lens": 30.0}
TOP_B = {"rel": "follow", "loc": (0.0, -2.5, 10.0), "target": (0.0, 2.5, 0.0), "lens": 30.0}
GHOST_WIDE = {"rel": "car", "loc": (-3.2, 3.6, 2.6), "target": (0.0, 0.4, 0.4), "lens": 30.0}
GHOST_WIDE_B = {"rel": "car", "loc": (-2.4, 2.4, 2.0), "target": (0.0, 0.2, 0.4), "lens": 32.0}
YAW = {"rel": "car", "loc": (0.95, -0.25, 0.80), "target": (0.0, 0.05, 0.40), "lens": 100.0}
YAW_B = {"rel": "car", "loc": (0.95, -0.25, 0.80), "target": (0.0, 0.05, 0.40), "lens": 130.0}
STEER = {"rel": "car", "loc": (-1.35, 0.20, 1.20), "target": (-0.36, 0.68, 0.82), "lens": 70.0}
STEER_B = {"rel": "car", "loc": (-1.35, 0.20, 1.20), "target": (-0.36, 0.68, 0.82), "lens": 95.0}
HCU = {"rel": "car", "loc": (-1.20, 2.55, 1.55), "target": (-0.40, 1.45, 0.62), "lens": 50.0}
HCU_B = {"rel": "car", "loc": (-1.00, 2.30, 1.30), "target": (-0.40, 1.45, 0.62), "lens": 55.0}
BRAKE = {"rel": "car", "loc": (1.50, 0.70, 0.45), "target": (0.80, 1.09, 0.28), "lens": 34.0}
BRAKE_B = {"rel": "car", "loc": (1.28, 0.82, 0.40), "target": (0.80, 1.09, 0.28), "lens": 38.0}
CHASE = {"rel": "follow", "loc": (2.5, -7.0, 2.4), "target": (-0.3, 3.0, 0.6), "lens": 30.0}
CHASE_B = {"rel": "follow", "loc": (1.8, -5.5, 1.9), "target": (-0.3, 3.0, 0.6), "lens": 32.0}

# label, variant, sim start, sim end (None = real time), cam a, cam b, flags, narration lines
ROWS = [
    ("A-split-swerve", "both", OPEN_SIM, None, SPLIT, SPLIT_B, {"split": True}, (1,)),
    ("B-rear-loses-grip", "off", 0.85, 1.35, REAR_LOW, REAR_LOW_B, {}, (2,)),
    ("C-turns-faster", "off", 1.35, 2.30, REAR_WIDE, REAR_WIDE_B, {}, (3,)),
    ("D-too-late", "off", 2.10, 3.70, TOP, TOP_B, {}, (4,)),
    ("E-hardware", "esc", 0.40, 0.55, GHOST_WIDE, GHOST_WIDE_B, {"xray": True}, (5,)),
    ("F-yaw-sensor", "esc", 0.55, 0.80, YAW, YAW_B, {"xray": True}, (6,)),
    ("G-steering-sensor", "esc", 0.40, 0.80, STEER, STEER_B, {"xray": True}, (7,)),
    ("H-decides", "esc", 0.62, 0.74, HCU, HCU_B, {"xray": True}, (8,)),
    ("I-outer-brake", "esc", 0.70, 1.05, BRAKE, BRAKE_B, {"xray": True, "macro": True}, (9,)),
    ("J-nose-back", "esc", 0.80, 1.70, TOP, TOP_B, {}, (10,)),
    ("K-valve-block", "esc", 1.75, 2.45, HCU, HCU_B, {"xray": True}, (11,)),
    ("L-stays-straight", "esc", 1.60, 3.40, CHASE, CHASE_B, {}, (12,)),
    ("M-keep-steering", "esc", 3.40, 4.40, CHASE_B, CHASE, {}, (13,)),
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
                    "time_scale": round((sim1 - a) / (t1 - t0), 3)})
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
    return {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": cam, **seg["flags"]}


def scene_alignment(segs: list[dict]) -> dict:
    problems, rows = [], []
    for k, st in enumerate(line_starts(), 1):
        seg = next((s for s in segs if s["t0"] <= st + 0.05 < s["t1"]), None)
        rows.append({"line": k, "cue_s": round(st, 2), "segment": seg["label"] if seg else None})
        if seg is None or k not in seg["lines"]:
            problems.append(f"line {k} at {st:.2f}s shows {seg['label'] if seg else 'nothing'}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows}
