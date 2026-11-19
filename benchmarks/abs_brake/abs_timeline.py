"""EP.06 film timeline (pure data, no Blender). Picture segments follow the frozen narration (examples/episodes/ep06-audio/audio-validation.json):
segment k starts when narration line k starts. Each segment maps film time to simulated time (real time or slow motion, stated per segment)
and moves the camera from cam_a to cam_b. The film opens on the split screen (no pre-roll: the first word is at 0 s) and its last second is the
run-in just before the brakes go on, so the Short loops back into frame 0."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
LOOP_S = 1.0
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep06-audio/audio-validation.json"

SPLIT_CAM = {"rel": "chase", "loc": (3.4, -6.5, 4.2), "target": (-1.0, 7.0, -1.3), "lens": 28.0}
SIDE_WHEEL = {"rel": "car", "loc": (-3.0, 1.4, 0.40), "target": (-0.7, 1.0, 0.32), "lens": 32.0}
SIDE_WHEEL_B = {"rel": "car", "loc": (-2.2, 1.2, 0.34), "target": (-0.7, 1.05, 0.30), "lens": 34.0}
TOP = {"rel": "chase", "loc": (-1.0, -4.0, 8.5), "target": (-1.0, 5.0, 0.0), "lens": 30.0}
TOP_B = {"rel": "chase", "loc": (-1.0, -3.0, 9.0), "target": (-1.0, 6.0, 0.0), "lens": 30.0}
WHEEL_WIDE = {"rel": "car", "loc": (-2.8, 0.2, 0.9), "target": (-0.75, 1.05, 0.30), "lens": 30.0}
RING = {"rel": "car", "loc": (-1.75, 0.70, 0.30), "target": (-0.78, 1.09, 0.25), "lens": 30.0}
CALIPER = {"rel": "car", "loc": (-1.30, 0.80, 0.70), "target": (-0.77, 1.00, 0.40), "lens": 40.0}
CALIPER_WIDE = {"rel": "car", "loc": (-1.55, 0.65, 0.62), "target": (-0.77, 1.02, 0.36), "lens": 34.0}
PEDAL = {"rel": "pedal", "loc": (0.90, -0.10, 0.36), "target": (0.0, 0.30, 0.20), "lens": 30.0}
PEDAL_B = {"rel": "pedal", "loc": (0.75, 0.00, 0.30), "target": (0.0, 0.32, 0.19), "lens": 34.0}

# label, variant, sim start, sim end, cam a, cam b, flags, narration lines
ROWS = [
    ("A-split-stop", "both", 0.00, None, SPLIT_CAM, SPLIT_CAM, {"split": True}, (1,)),
    ("B-wheel-locks", "locked", 0.00, 0.45, SIDE_WHEEL, SIDE_WHEEL_B, {}, (2,)),
    ("C-slides-straight", "locked", 0.55, 1.75, TOP, TOP_B, {}, (3,)),
    ("D-sensor", "abs", 0.40, 0.55, WHEEL_WIDE, RING, {"macro": True}, (4,)),
    ("E-caliper-pulse", "abs", 0.55, 0.75, CALIPER, CALIPER, {"macro": True}, (5,)),
    ("F-many-times", "abs", 0.75, 1.25, CALIPER, CALIPER_WIDE, {"macro": True}, (6,)),
    ("G-abs-steers", "abs", 0.70, 1.95, TOP, TOP_B, {}, (7,)),
    ("H-pedal-buzz", "abs", 0.40, 1.60, PEDAL, PEDAL_B, {"pedal": True}, (8,)),
    ("I-loop-run-in", "both", -LOOP_S, 0.0, SPLIT_CAM, SPLIT_CAM, {"split": True}, (8,)),
]


def line_starts() -> list[float]:
    r = json.loads(AUDIO.read_text())
    return [b["start"] for b in r["beats"]]


def total_seconds() -> float:
    r = json.loads(AUDIO.read_text())
    return round(r["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def segments() -> list[dict]:
    s = line_starts()
    total = total_seconds()
    t = [s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], total - LOOP_S, total]
    out = []
    for i, (label, variant, a, b, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        sim1 = b if b is not None else a + (t1 - t0)          # None: real time
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
    """Every narration line starts while its own segment is on screen."""
    problems, rows = [], []
    for k, st in enumerate(line_starts(), 1):
        seg = next((s for s in segs if s["t0"] <= st + 0.05 < s["t1"]), None)
        rows.append({"line": k, "cue_s": round(st, 2), "segment": seg["label"] if seg else None})
        if seg is None or k not in seg["lines"]:
            problems.append(f"line {k} at {st:.2f}s shows {seg['label'] if seg else 'nothing'}")
    first_hit = None
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows}
