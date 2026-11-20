"""EP.11 film timeline (pure data). One segment per narration line (frozen audio in examples/episodes/ep11-audio).
Simulated time t: seconds after impact (negative = approaching / falling / before the hazard for the braking scene).
"warp" segments run at real speed until the impact lands at film second `tc` of the segment, then in slow motion (`slow` x real time),
so the opening crash lands before 1.0 s. The last second runs back into the opening (loop)."""
from __future__ import annotations

import json
from pathlib import Path

from benchmarks.speed_energy import speed_motion as sm

FPS = 24
END_PAD_S = 0.25
LOOP_S = 1.0
OPEN_SIM = -0.7
OPEN_TC = 0.7
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep11-audio/audio-validation.json"

SPLIT = {"rel": "wall", "loc": (5.6, -9.8, 3.3), "target": (-0.4, -2.4, 0.5), "lens": 26.0}
SPLIT_B = {"rel": "wall", "loc": (5.0, -8.8, 2.9), "target": (-0.4, -2.2, 0.5), "lens": 27.0}
CLOSE = {"rel": "wall", "loc": (3.6, -4.2, 1.7), "target": (-0.2, -1.4, 0.55), "lens": 26.0}
CLOSE_B = {"rel": "wall", "loc": (3.1, -3.6, 1.4), "target": (-0.2, -1.4, 0.55), "lens": 28.0}
CHASE = {"rel": "car", "loc": (3.4, -6.5, 1.9), "target": (-0.2, 4.0, 0.6), "lens": 26.0}
CHASE_B = {"rel": "car", "loc": (2.6, -5.2, 1.5), "target": (-0.2, 4.0, 0.6), "lens": 28.0}
XRAY_IN = {"rel": "wall", "loc": (-4.6, -6.2, 2.4), "target": (0.0, -2.2, 0.6), "lens": 28.0}
XRAY_IN_B = {"rel": "wall", "loc": (-4.0, -5.2, 2.1), "target": (0.0, -1.8, 0.6), "lens": 30.0}
RAILS = {"rel": "wall", "loc": (-1.9, -0.5, 2.5), "target": (0.0, -1.2, 0.45), "lens": 28.0}
RAILS_B = {"rel": "wall", "loc": (-1.6, -1.3, 2.2), "target": (0.0, -1.2, 0.45), "lens": 30.0}
SIDE = {"rel": "wall", "loc": (-4.0, -3.6, 2.9), "target": (0.0, -1.5, 0.45), "lens": 30.0}
SIDE_B = {"rel": "wall", "loc": (-3.5, -3.0, 2.6), "target": (0.0, -1.4, 0.45), "lens": 32.0}
DROP = {"rel": "drop", "loc": (0.0, -26.0, 9.0), "target": (0.0, 0.0, 7.0), "lens": 48.0}
DROP_B = {"rel": "drop", "loc": (0.0, -18.0, 3.0), "target": (0.0, 0.0, 2.6), "lens": 40.0}
DROP5 = {"rel": "drop", "loc": (0.0, -30.0, 11.0), "target": (0.0, 0.0, 9.5), "lens": 42.0}
DROP5_B = {"rel": "drop", "loc": (0.0, -20.0, 3.5), "target": (0.0, 0.0, 3.0), "lens": 38.0}
BRAKE = {"rel": "brake", "loc": (6.0, sm.stop_distance("slow") + 16.0, 3.4), "target": (-0.6, sm.stop_distance("slow") - 10.0, 0.4), "lens": 28.0}
BRAKE_B = {"rel": "brake", "loc": (5.4, sm.stop_distance("slow") + 13.0, 3.0), "target": (-0.6, sm.stop_distance("slow") - 8.0, 0.4), "lens": 30.0}
CAB = {"rel": "car", "loc": (0.30, 0.95, 1.10), "target": (-0.36, 0.20, 1.00), "lens": 30.0}
CAB_B = {"rel": "car", "loc": (0.25, 0.85, 1.05), "target": (-0.36, 0.25, 0.95), "lens": 34.0}
APPROACH = {"rel": "car", "loc": (4.2, -7.5, 2.4), "target": (-0.2, 5.0, 0.5), "lens": 26.0}
APPROACH_B = {"rel": "car", "loc": (3.6, -6.4, 2.0), "target": (-0.2, 5.0, 0.5), "lens": 27.0}
WIDE = {"rel": "wall", "loc": (7.5, -12.0, 4.4), "target": (-0.4, -2.6, 0.4), "lens": 26.0}
WIDE_B = {"rel": "wall", "loc": (6.4, -10.6, 3.6), "target": (-0.4, -2.4, 0.4), "lens": 26.0}

T_FALL = {k: (2 * sm.fall_height_m(k) / sm.G) ** 0.5 for k in sm.SPEEDS}

# label, variant, sim start, sim end (None = warp/real), cam a, cam b, flags, narration lines
ROWS = [
    ("A-split", "both", OPEN_SIM, None, SPLIT, SPLIT_B, {"split": True, "warp": (OPEN_TC, 0.025)}, (1,)),
    ("B-deeper", "both", 0.0, 0.075, CLOSE, CLOSE_B, {"split": True}, (2,)),
    ("C-square", "fast", -1.3, -0.35, CHASE, CHASE_B, {}, (3,)),
    ("D-energy", "both", -1.0, -0.2, APPROACH, APPROACH_B, {"split": True, "energy": True}, (4,)),
    ("E-somewhere", "fast", -0.14, 0.0, XRAY_IN, XRAY_IN_B, {"xray_ramp": True}, (5,)),
    ("F-rails", "fast", 0.0, 0.068, RAILS, RAILS_B, {"xray": 1.0}, (6,)),
    ("G-thirty", "slow", 0.0, 0.068, SIDE, SIDE_B, {"xray": 1.0, "ruler": True}, (7,)),
    ("H-forty", "fast", 0.0, 0.068, SIDE_B, SIDE, {"xray": 1.0, "ruler": True}, (8,)),
    ("I-three-story", "slow", -T_FALL["slow"], None, DROP, DROP_B, {"drop": True, "warp": (2.5, 0.06)}, (9,)),
    ("J-five-story", "fast", -T_FALL["fast"], None, DROP5, DROP5_B, {"drop": True, "warp": (1.5, 0.1)}, (10,)),
    ("K-braking", "both", 0.6, 3.5, BRAKE, BRAKE_B, {"split": True, "brake": True}, (11,)),
    ("L-driver", "fast", -0.6, None, CAB, CAB_B, {"interior": True, "warp": (2.4, 0.05)}, (12,)),
    ("M-twice", "both", -0.9, None, WIDE, WIDE_B, {"split": True, "warp": (0.9, 0.022)}, (13,)),
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
        if "warp" in flags:
            tc, slow = flags["warp"]
            sim1 = 0.0 + (t1 - t0 - tc) * slow
        else:
            sim1 = b if b is not None else a + (t1 - t0)
        out.append({"label": label, "variant": variant, "t0": t0, "t1": t1, "sim0": a, "sim1": sim1, "cam_a": ca, "cam_b": cb, "flags": flags, "lines": lines,
                    "time_scale": round((sim1 - a) / (t1 - t0), 5)})
    return out


def sim_time(seg: dict, film_t: float) -> float:
    tau = film_t - seg["t0"]
    if "warp" in seg["flags"]:
        tc, slow = seg["flags"]["warp"]
        if tau < tc:
            return seg["sim0"] + tau * (-seg["sim0"] / tc)
        return (tau - tc) * slow
    u = min(1.0, max(0.0, tau / (seg["t1"] - seg["t0"])))
    return seg["sim0"] + (seg["sim1"] - seg["sim0"]) * u


def _smooth(u):
    """Half ease, half linear: the camera never stops completely."""
    return 0.5 * u + 0.5 * u * u * (3 - 2 * u)


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    sim = sim_time(seg, t)
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    cam = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])), "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])),
           "lens": a["lens"] + (b["lens"] - a["lens"]) * uc}
    flags = {k: v for k, v in seg["flags"].items() if k != "warp"}
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim, "cam": cam, "u": u}
    if flags.pop("xray_ramp", False):
        flags["xray"] = min(1.0, max(0.0, (u - 0.1) * 1.6))
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
