"""EP.13 film timeline (pure data). Owner direction 2026-11-21: no text on the picture (only the narration captions), and make it a film
people want to watch. Structure from the best upload (Road Signs, 69.9 % viewed): a question over the money shot, few lines, every
shot a big outdoor event. Frame 1 is already 0.05 s into the hit: the steel ribbon is coming out of the head and the sparks are flying.
Simulated time t: seconds after the car touches the head (or the blunt rail end in the B shots). "warp" segments run toward the
contact at a steady rate so that it lands at film second tc of the segment, then at `slow` x real time. The last segment runs a fresh
terminal into the hit and ends on the opening frame's camera and moment, so the Short loops."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
END_PAD_S = 0.25
OPEN_SIM = 0.12
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep13-audio/audio-validation.json"
B2_START = 5.2                      # "It spears right into the cabin" starts at 5.27 s

# rel: "head" = head front face centre (moves with the head), "T" = terminal site, "S" = blunt-end site, "car" = car root
A_CAM = {"rel": "head", "loc": (2.9, 1.3, 1.5), "target": (0.7, -0.4, 0.45), "lens": 21.0, "fstop": 5.6}
A_CAM_B = {"rel": "head", "loc": (2.75, 1.0, 1.35), "target": (0.6, -0.5, 0.45), "lens": 22.0, "fstop": 5.6}
SPEAR = {"rel": "S", "loc": (1.9, 1.3, 0.9), "target": (-0.2, -0.3, 0.55), "lens": 25.0, "fstop": 8.0}
SPEAR_B = {"rel": "S", "loc": (1.75, 1.1, 0.85), "target": (-0.2, -0.1, 0.55), "lens": 26.0, "fstop": 8.0}
XRAY = {"rel": "car", "loc": (1.6, 3.4, 2.5), "target": (0.4, 0.6, 0.5), "lens": 26.0, "fstop": 11.0}
XRAY_B = {"rel": "car", "loc": (1.5, 3.0, 2.3), "target": (0.4, 0.4, 0.5), "lens": 27.0, "fstop": 11.0}
HEAD_CU = {"rel": "head", "loc": (1.5, -1.6, 0.75), "target": (0.0, 0.15, 0.5), "lens": 28.0, "fstop": 4.0}
HEAD_CU_B = {"rel": "head", "loc": (1.3, -1.3, 0.7), "target": (0.0, 0.15, 0.5), "lens": 30.0, "fstop": 4.0}
CUT = {"rel": "head", "loc": (0.95, 0.30, 1.35), "target": (0.0, 0.35, 0.25), "lens": 30.0, "fstop": 8.0}
CUT_B = {"rel": "head", "loc": (0.85, 0.45, 1.2), "target": (0.0, 0.40, 0.25), "lens": 32.0, "fstop": 8.0}
WIDE = {"rel": "head", "loc": (4.6, -4.5, 4.4), "target": (0.6, -1.4, 0.4), "lens": 24.0, "fstop": 11.0}
WIDE_B = {"rel": "head", "loc": (5.4, -2.4, 3.6), "target": (0.6, -1.2, 0.4), "lens": 24.0, "fstop": 11.0}
POST_CAM = {"rel": "T", "loc": (2.3, 2.85, 0.42), "target": (0.25, 4.6, 0.5), "lens": 28.0, "fstop": 4.0}
POST_CAM_B = {"rel": "T", "loc": (2.1, 3.15, 0.38), "target": (0.25, 4.6, 0.5), "lens": 30.0, "fstop": 4.0}
AERIAL = {"rel": "T", "loc": (4.0, 1.5, 3.5), "target": (0.3, 6.0, 0.3), "lens": 28.0, "fstop": 11.0}
AERIAL_B = {"rel": "T", "loc": (6.5, 0.5, 11.0), "target": (0.3, 5.6, 0.0), "lens": 40.0, "fstop": 16.0}
FRESH = {"rel": "head", "loc": (1.8, 1.8, 0.85), "target": (-0.5, -5.0, 0.6), "lens": 24.0, "fstop": 4.0}

# label, variant, start (line number or (line, absolute second)), sim start, sim end (None = warp), cam a, cam b, flags, lines
ROWS = [
    ("A-ribbon", "terminal", 1, OPEN_SIM, OPEN_SIM + 0.33, A_CAM, A_CAM_B, {}, (1,)),
    ("B1-blunt-end", "spear", 2, -0.55, None, SPEAR, SPEAR_B, {"warp": (0.7, 0.07)}, (2,)),
    ("B2-into-the-cabin", "spear", (2, B2_START), 0.06, 0.20, XRAY, XRAY_B, {"xray": True}, (2,)),
    ("C-steel-head", "terminal", 3, -0.85, None, HEAD_CU, HEAD_CU_B, {"warp": (1.5, 0.085)}, (3,)),
    ("D-inside", "terminal", 4, 0.10, 0.36, CUT, CUT_B, {"cutaway": True}, (4,)),
    ("E-slows-the-car", "terminal", 5, 0.0, 0.74, WIDE, WIDE_B, {}, (5,)),
    ("F-posts-snap", "terminal", 6, 0.12, 0.33, POST_CAM, POST_CAM_B, {}, (6,)),
    ("G-two-car-lengths", "terminal", 7, 0.70, 1.40, AERIAL, AERIAL_B, {}, (7,)),
    ("H-waiting", "terminal", 8, -3.0, OPEN_SIM, FRESH, A_CAM, {"loop": True}, (8,)),
]


def _audio() -> dict:
    return json.loads(AUDIO.read_text())


def line_starts() -> list[float]:
    return [b["start"] for b in _audio()["beats"]]


def total_seconds() -> float:
    return round(_audio()["seconds"] + END_PAD_S, 3)


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def segments() -> list[dict]:
    s = line_starts()
    total = total_seconds()
    starts = [s[r[2] - 1] if isinstance(r[2], int) else r[2][1] for r in ROWS]
    t = starts + [total]
    out = []
    for i, (label, variant, _, a, b, ca, cb, flags, lines) in enumerate(ROWS):
        t0, t1 = t[i], t[i + 1]
        if "warp" in flags:
            tc, slow = flags["warp"]
            sim1 = (t1 - t0 - tc) * slow
        else:
            sim1 = b
        out.append({"label": label, "variant": variant, "t0": t0, "t1": t1, "sim0": a, "sim1": sim1, "cam_a": ca, "cam_b": cb, "flags": flags,
                    "lines": lines, "time_scale": round((sim1 - a) / (t1 - t0), 5)})
    return out


def sim_time(seg: dict, film_t: float) -> float:
    tau = film_t - seg["t0"]
    if "warp" in seg["flags"]:
        tc, slow = seg["flags"]["warp"]
        return seg["sim0"] + tau * (-seg["sim0"] / tc) if tau < tc else (tau - tc) * slow
    u = min(1.0, max(0.0, tau / (seg["t1"] - seg["t0"])))
    if seg["flags"].get("loop"):        # the run-in eases into the opening's slow motion so the seam does not jump in speed
        return seg["sim0"] + (seg["sim1"] - seg["sim0"]) * (0.35 * u + 0.65 * (1.0 - (1.0 - u) ** 1.6))
    return seg["sim0"] + (seg["sim1"] - seg["sim0"]) * u


def _smooth(u):
    """Half ease, half linear: the camera never stops completely."""
    return 0.5 * u + 0.5 * u * u * (3 - 2 * u)


def _lerp_cam(a, b, uc):
    return {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
            "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
            "fstop": a.get("fstop", 8.0) + (b.get("fstop", 8.0) - a.get("fstop", 8.0)) * uc}


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    uc = 0.5 * u + 0.5 * (1.0 - (1.0 - u) ** 2) if seg["flags"].get("loop") else _smooth(u)      # never comes to rest (frozen-frame lesson)
    st = {"frame": f, "film_t": t, "segment": seg["label"], "variant": seg["variant"], "t": sim_time(seg, t), "cam": _lerp_cam(seg["cam_a"], seg["cam_b"], uc), "u": u}
    st.update({k: v for k, v in seg["flags"].items() if k != "warp"})
    return st


def film_time_of(seg: dict, sim: float) -> float | None:
    """Film second at which the segment's simulated clock passes `sim` (None if it never does)."""
    if not min(seg["sim0"], seg["sim1"]) <= sim <= max(seg["sim0"], seg["sim1"]):
        return None
    lo, hi = seg["t0"], seg["t1"]
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if sim_time(seg, mid) < sim:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def scene_alignment(segs: list[dict]) -> dict:
    problems, rows = [], []
    for k, st in enumerate(line_starts(), 1):
        seg = next((s for s in segs if s["t0"] <= st + 0.05 < s["t1"]), None)
        rows.append({"line": k, "cue_s": round(st, 2), "segment": seg["label"] if seg else None})
        if seg is None or k not in seg["lines"]:
            problems.append(f"line {k} at {st:.2f}s shows {seg['label'] if seg else 'nothing'}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows}
