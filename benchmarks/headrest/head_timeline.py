"""EP.12 film timeline (pure data). One segment per narration line (frozen audio in examples/episodes/ep12-audio), one thread: hit ->
seat pushes the back -> head stays -> neck bends -> low headrest: whip -> high headrest: caught -> how to set it. Simulated time t = seconds
after the hit. "warp" segments run at real speed until the hit lands at film second tc of the segment, then at `slow` x real time.
The opening is a big side close-up of the two drivers (split), the hit at 0.2 s, the low-headrest head whipping back by about 1.5 s."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
LOOP_S = 1.0
OPEN_SIM = -0.2
OPEN_TC = 0.2
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep12-audio/audio-validation.json"

# "start": world frame = the car where it stood at the light (so the car is seen lurching forward); "car": follows the car
SIDE = {"rel": "start", "loc": (-1.70, 0.10, 1.05), "target": (-0.36, 0.02, 0.98), "lens": 38.0}
SIDE_B = {"rel": "start", "loc": (-1.55, 0.16, 1.03), "target": (-0.36, 0.06, 0.98), "lens": 40.0}
SIDE_PRE = {"rel": "start", "loc": (-2.10, -0.10, 1.15), "target": (-0.36, 0.00, 0.98), "lens": 34.0}
CAR_SIDE = {"rel": "car", "loc": (-1.55, 0.05, 1.08), "target": (-0.36, -0.02, 1.00), "lens": 42.0}
CAR_SIDE_B = {"rel": "car", "loc": (-1.40, 0.12, 1.04), "target": (-0.36, -0.02, 1.00), "lens": 46.0}
NECK = {"rel": "car", "loc": (-1.20, 0.12, 1.02), "target": (-0.36, 0.0, 1.00), "lens": 50.0}
NECK_B = {"rel": "car", "loc": (-1.10, 0.02, 1.00), "target": (-0.36, -0.02, 1.00), "lens": 54.0}
BACK = {"rel": "start", "loc": (-1.50, -0.35, 0.95), "target": (-0.36, 0.10, 0.85), "lens": 30.0}
BACK_B = {"rel": "start", "loc": (-1.35, -0.25, 0.92), "target": (-0.36, 0.12, 0.85), "lens": 32.0}
WIDE = {"rel": "start", "loc": (-7.5, -5.5, 2.3), "target": (0.0, -2.6, 0.7), "lens": 26.0}
WIDE_B = {"rel": "start", "loc": (-6.6, -4.4, 2.0), "target": (0.0, -2.2, 0.7), "lens": 28.0}
ADJ = {"rel": "car", "loc": (-1.35, -0.40, 1.20), "target": (-0.36, -0.05, 1.02), "lens": 40.0}
ADJ_B = {"rel": "car", "loc": (-1.30, -0.30, 1.15), "target": (-0.36, -0.05, 1.02), "lens": 42.0}

# label, variant, sim start, sim end (None = warp), cam a, cam b, flags, narration lines
ROWS = [
    ("A-split", "both", OPEN_SIM, None, SIDE, SIDE_B, {"split": True, "warp": (OPEN_TC, 0.1)}, (1,)),
    ("B-shove", "low", -1.0, None, WIDE, WIDE_B, {"exterior": True, "warp": (1.0, 0.12)}, (2,)),
    ("C-head-stays", "low", -0.03, 0.07, BACK, BACK_B, {}, (3,)),
    ("D-neck-bends", "low", 0.03, 0.09, NECK, NECK_B, {"angle": True}, (4,)),
    ("E-whip", "low", 0.05, 0.16, CAR_SIDE, CAR_SIDE_B, {"angle": True}, (5,)),
    ("F-tenth", "low", 0.0, 0.14, CAR_SIDE_B, CAR_SIDE, {"angle": True, "timer": True}, (6,)),
    ("G-whiplash", "low", 0.10, 0.16, NECK_B, NECK, {"angle": True}, (7,)),
    ("H-two-inches", "high", 0.0, 0.06, CAR_SIDE, CAR_SIDE_B, {"gap": True}, (8,)),
    ("I-caught", "high", 0.03, 0.13, NECK, NECK_B, {"angle": True}, (9,)),
    ("J-three-times", "both", 0.0, 0.15, SIDE_B, SIDE, {"split": True, "angle": True}, (10,)),
    ("K-height", "adjust", -1.0, -1.0, ADJ, ADJ_B, {"adjust": "height"}, (11,)),
    ("L-close", "adjust", -1.0, -1.0, ADJ_B, ADJ, {"adjust": "close"}, (12,)),
    ("M-caught", "both", -0.2, None, SIDE, SIDE_B, {"split": True, "warp": (0.3, 0.09)}, (13,)),
    ("N-loop-run-in", "both", OPEN_SIM - LOOP_S, OPEN_SIM, SIDE_PRE, SIDE, {"split": True}, (13,)),
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
        if "warp" in flags:
            tc, slow = flags["warp"]
            sim1 = (t1 - t0 - tc) * slow
        else:
            sim1 = b
        out.append({"label": label, "variant": variant, "t0": t0, "t1": t1, "sim0": a, "sim1": sim1, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines,
                    "time_scale": round((sim1 - a) / (t1 - t0), 5)})
    return out


def sim_time(seg: dict, film_t: float) -> float:
    tau = film_t - seg["t0"]
    if "warp" in seg["flags"]:
        tc, slow = seg["flags"]["warp"]
        return seg["sim0"] + tau * (-seg["sim0"] / tc) if tau < tc else (tau - tc) * slow
    u = min(1.0, max(0.0, tau / (seg["t1"] - seg["t0"])))
    return seg["sim0"] + (seg["sim1"] - seg["sim0"]) * u


def _smooth(u):
    return 0.5 * u + 0.5 * u * u * (3 - 2 * u)


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    cam = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])), "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])),
           "lens": a["lens"] + (b["lens"] - a["lens"]) * uc}
    flags = {k: v for k, v in seg["flags"].items() if k != "warp"}
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim_time(seg, t), "cam": cam, "u": u}
    if "adjust" in flags:
        k = min(1.0, max(0.0, (u - 0.15) / 0.6))
        flags["setting"] = {"height": k, "close": 0.0} if flags["adjust"] == "height" else {"height": 1.0, "close": k}
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
