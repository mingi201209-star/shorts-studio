"""EP.10 film timeline (pure data). One segment per narration line (frozen audio in examples/episodes/ep10-audio); simulated time t is
seconds after the car ahead starts braking (negative = both cruising). The opening is the labelled split (3-second gap / 1-second gap)
already 2.1 s into the stop, so the rear-end hit lands at about 0.9 s of film time; the last second runs back into the opening.
Sign counting: the car ahead's tail passes the sign at SIGN_PASS_LEAD_S in the 3-second case; the follower reaches it 3 s later."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
LOOP_S = 1.0
OPEN_SIM = 2.1
SIGN_PASS_LEAD_S = -4.2
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep10-audio/audio-validation.json"

SPLIT = {"rel": "fol", "loc": (4.5, -9.0, 5.5), "target": (-1.0, 14.0, -0.5), "lens": 24.0}
SPLIT_B = {"rel": "fol", "loc": (3.8, -8.0, 4.8), "target": (-1.0, 14.0, -0.3), "lens": 26.0}
CAB = {"rel": "car", "loc": (0.45, 0.20, 1.18), "target": (-0.30, 2.5, 0.95), "lens": 26.0}
CAB_B = {"rel": "car", "loc": (0.40, 0.35, 1.15), "target": (-0.30, 3.0, 0.95), "lens": 28.0}
FACE = {"rel": "car", "loc": (0.30, 0.95, 1.10), "target": (-0.36, 0.20, 1.00), "lens": 34.0}
FACE_B = {"rel": "car", "loc": (0.25, 0.85, 1.05), "target": (-0.36, 0.25, 0.95), "lens": 38.0}
SIDE = {"rel": "fol", "loc": (-15.0, 4.0, 2.2), "target": (0.0, 7.0, 0.6), "lens": 34.0}
SIDE_B = {"rel": "fol", "loc": (-13.0, 6.0, 2.0), "target": (0.0, 7.0, 0.6), "lens": 36.0}
TOP = {"rel": "fol", "loc": (-1.0, 10.0, 34.0), "target": (-1.0, 26.0, 0.0), "lens": 26.0}
TOP_B = {"rel": "fol", "loc": (-1.0, 14.0, 34.0), "target": (-1.0, 30.0, 0.0), "lens": 26.0}
TOP_FIXED = {"rel": "world", "loc": (-1.0, 2.0, 70.0), "target": (-1.0, 6.0, 0.0), "lens": 38.0}
TOP_FIXED_B = {"rel": "world", "loc": (-1.0, 12.0, 58.0), "target": (-1.0, 16.0, 0.0), "lens": 40.0}
SIGN_CAM = {"rel": "sign", "loc": (4.5, 9.0, 2.2), "target": (-0.5, -12.0, 1.0), "lens": 34.0}      # downstream of the sign, looking back at the cars coming
SIGN_CAM_B = {"rel": "sign", "loc": (4.0, 8.0, 2.0), "target": (-0.5, -12.0, 1.0), "lens": 36.0}
CHASE = {"rel": "fol", "loc": (2.0, -7.0, 2.4), "target": (-0.5, 10.0, 0.6), "lens": 28.0}
CHASE_B = {"rel": "fol", "loc": (1.5, -6.0, 2.0), "target": (-0.5, 10.0, 0.6), "lens": 30.0}

# label, variant, sim start, sim end, cam a, cam b, flags, narration lines
ROWS = [
    ("A-split", "both", OPEN_SIM, OPEN_SIM + 3.34, SPLIT, SPLIT_B, {"split": True}, (1,)),
    ("B-not-yet", "one", -0.2, 0.9, CAB, CAB_B, {"interior": True}, (2,)),
    ("C-reaction", "one", 0.0, 1.5, FACE, FACE_B, {"interior": True, "timer": True}, (3,)),
    ("D-forty-yards", "one", 0.0, 1.5, TOP, TOP_B, {"timer": True}, (4,)),
    ("E-square", "one", 1.5, 2.9, SIDE, SIDE_B, {}, (5,)),
    ("F-double", "three", -2.0, -0.6, TOP_FIXED, TOP_FIXED_B, {}, (6,)),
    ("G-46-vs-86", "three", 0.0, 5.0, TOP_FIXED, TOP_FIXED_B, {}, (7,)),
    ("H-count", "three", SIGN_PASS_LEAD_S - 0.3, SIGN_PASS_LEAD_S + 3.1, SIGN_CAM, SIGN_CAM_B, {"count": True}, (8,)),
    ("I-too-close", "one", SIGN_PASS_LEAD_S + 1.7, SIGN_PASS_LEAD_S + 3.1, SIGN_CAM, SIGN_CAM_B, {"count": True}, (9,)),
    ("J-rain", "three", SIGN_PASS_LEAD_S + 1.5, SIGN_PASS_LEAD_S + 2.5, SIGN_CAM_B, SIGN_CAM, {}, (10,)),
    ("K-phone", "one", -2.0, -0.2, FACE, FACE_B, {"interior": True, "phone": True}, (11,)),
    ("L-buys-time", "both", OPEN_SIM, OPEN_SIM + 2.4, SPLIT, SPLIT_B, {"split": True}, (12,)),
    ("M-three-seconds", "three", 2.5, 5.0, CHASE, CHASE_B, {}, (13,)),
    ("N-loop-run-in", "both", OPEN_SIM - 1.0, OPEN_SIM, SPLIT, SPLIT, {"split": True}, (13,)),
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
    return 0.5 * u + 0.5 * u * u * (3 - 2 * u)


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    sim = seg["sim0"] + (seg["sim1"] - seg["sim0"]) * u
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    cam = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])), "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])),
           "lens": a["lens"] + (b["lens"] - a["lens"]) * uc}
    return {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": cam, "u": u, **seg["flags"]}


def scene_alignment(segs: list[dict]) -> dict:
    problems, rows = [], []
    for k, st in enumerate(line_starts(), 1):
        seg = next((s for s in segs if s["t0"] <= st + 0.05 < s["t1"]), None)
        rows.append({"line": k, "cue_s": round(st, 2), "segment": seg["label"] if seg else None})
        if seg is None or k not in seg["lines"]:
            problems.append(f"line {k} at {st:.2f}s shows {seg['label'] if seg else 'nothing'}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows}
