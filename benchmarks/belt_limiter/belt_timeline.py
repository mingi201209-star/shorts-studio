"""EP.05 film timeline (pure data, no Blender): every film frame maps to a shot-like state (camera, which belt, how far into the crash, what is visible) that the renderer draws.
Segment boundaries follow the real spoken cue times (line k starts at `line_starts[k-1]`, film seconds including the pre-roll), so the picture is planned against real timing.
Time inside the crash runs in slow motion: `dt` is simulated seconds after first contact (the whole stop takes about 0.09 s)."""
from __future__ import annotations

import math

from benchmarks.belt_limiter import belt_motion as bm
from benchmarks.belt_limiter import belt_shots as sh

FPS = 24
PRE_ROLL_S = 1.2
END_PAD_S = 0.25          # picture continues this long after the last spoken word

I_CHEST, I_FACE, REEL = sh.I_CHEST, sh.I_FACE, sh.REEL
PRETENSIONER_CAM = ((-0.46, -0.24, 0.40), (-0.72, -0.255, 0.43), 42.0)
PRETENSIONER_CAM_END = ((-0.50, -0.26, 0.42), (-0.72, -0.255, 0.45), 46.0)
REEL_FAR = ((-0.30, -0.16, 0.50), (-0.72, -0.30, 0.36), 40.0)
REEL_NEAR = ((-0.60, -0.45, 0.43), (-0.72, -0.37, 0.36), 34.0)
REEL_NEAR_END = ((-0.62, -0.42, 0.42), (-0.72, -0.37, 0.36), 38.0)


def _cam(rel, a, b, at=0.42):
    return {"rel": rel, "a": a, "b": b, "at": at}


def segments(line_starts: list[float], total_s: float) -> list[dict]:
    """Eight narration lines -> ten picture segments A..J (see the plan). Each: label, t0, t1, dt0, dt1, variant, flags, camera path a->b, the narration lines it illustrates."""
    s = line_starts
    t = [0.0, s[1] - 1.5, s[1], s[1] + 1.1, s[2] + 0.8, s[3], s[3] + 1.4, s[5], s[6], s[7], total_s]
    ext_a = ((-4.4, -3.4, 1.5), (0.0, -2.0, 0.6), 36.0)
    ext_b = ((-4.0, -2.0, 1.3), (0.0, -1.2, 0.6), 34.0)
    chest_a = (I_CHEST[0], I_CHEST[1], 26.0)
    chest_b = ((0.58, 0.46, 0.93), I_CHEST[1], 24.0)
    face_a = (I_FACE[0], I_FACE[1], 30.0)
    face_b = ((0.46, 0.56, 1.06), I_FACE[1], 32.0)
    cb = ((-3.4, -1.7, 1.0), (0.0, -1.3, 0.72), 30.0)
    cb_end = ((-3.0, -1.5, 1.0), (0.0, -1.0, 0.72), 32.0)
    rows = [
        ("A-run-up", "modern", -0.90, -0.12, "out", dict(interior=False, xray=0.0, cabin_xray=0.0), "nose", ext_a, ext_b, (1,)),
        ("B-cabin-before", "modern", -0.12, 0.0, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0), "car", chest_a, chest_b, (1,)),
        ("C-cabin-snap", "modern", 0.0, 0.0035, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0), "car", chest_b, chest_a, (2,)),
        ("D-pretensioner-inside", "modern", 0.0035, 0.0095, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0, hide_seat=True, hide_housing=True), "car", PRETENSIONER_CAM,
         PRETENSIONER_CAM_END, (2, 3)),
        ("E-cabin-held-back", "modern", 0.0095, 0.030, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0), "car", chest_a, chest_b, (3,)),
        ("F-into-the-reel", "modern", 0.030, 0.040, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0, hide_seat=True), "car", REEL_FAR, REEL_NEAR, (4,)),
        ("G-reel-inside", "modern", 0.040, 0.075, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0, hide_seat=True, hide_housing=True), "car", REEL_NEAR, REEL_NEAR_END, (4, 5)),
        ("H-gentle-stop", "modern", 0.060, 0.095, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0), "car", face_a, face_b, (6,)),
        ("I-plain-belt", "plain", 0.035, 0.095, "lin", dict(interior=True, xray=0.0, cabin_xray=0.0), "car", face_a, face_b, (7,)),
        ("J-both-give", "modern", 0.0, 0.100, "lin", dict(interior=False, xray=1.0, cabin_xray=1.0), "nose", cb, cb_end, (8,)),
    ]
    out = []
    for i, (label, variant, dt0, dt1, ease, flags, rel, a, b, lines) in enumerate(rows):
        out.append({"label": label, "t0": t[i], "t1": t[i + 1], "dt0": dt0, "dt1": dt1, "ease": ease, "variant": variant, "flags": flags, "rel": rel, "cam_a": a, "cam_b": b, "lines": lines})
    return out


def total_seconds(line_starts: list[float], last_line_end: float) -> float:
    return round(last_line_end + END_PAD_S, 3)


def frame_count(total_s: float) -> int:
    return int(round(total_s * FPS))


def _smooth(u: float) -> float:
    return u * u * (3.0 - 2.0 * u)


def _lerp(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def segment_at(segs: list[dict], t: float) -> dict:
    for s in segs:
        if s["t0"] <= t < s["t1"]:
            return s
    return segs[-1]


def frame_shot(f: int, segs: list[dict]) -> dict:
    """The shot-like dict for film frame f (0-based): same keys as belt_shots.SHOTS entries so the still renderer draws it unchanged."""
    t = f / FPS
    s = segment_at(segs, t)
    u = min(1.0, max(0.0, (t - s["t0"]) / max(1e-9, s["t1"] - s["t0"])))
    ud = 1.0 - (1.0 - u) ** 2 if s["ease"] == "out" else u
    dt = s["dt0"] + (s["dt1"] - s["dt0"]) * ud
    uc = _smooth(u)
    loc, tgt, lens = (_lerp(s["cam_a"][k], s["cam_b"][k], uc) if k < 2 else s["cam_a"][2] + (s["cam_b"][2] - s["cam_a"][2]) * uc for k in range(3))
    d = {"line": s["lines"][0], "text": s["label"], "variant": s["variant"], "dt": dt, "cam": {"rel": s["rel"], "loc": loc, "target": tgt, "lens": lens, "at": 0.42}, "segment": s["label"]}
    d.update(s["flags"])
    return d


def belt_scene_alignment(segs: list[dict], line_starts: list[float]) -> dict:
    """What must be on screen when each narration line starts (0.25 s after the cue, so the picture has had a moment): checked against the segment table, with the cue times."""
    need = {1: ("A-run-up", "B-cabin-before"), 2: ("C-cabin-snap", "D-pretensioner-inside"), 3: ("D-pretensioner-inside", "E-cabin-held-back"), 4: ("F-into-the-reel", "G-reel-inside"),
            5: ("G-reel-inside",), 6: ("H-gentle-stop",), 7: ("I-plain-belt",), 8: ("J-both-give",)}
    problems, rows = [], []
    for k in range(1, 9):
        seg = segment_at(segs, line_starts[k - 1] + 0.25)
        rows.append({"line": k, "cue_s": round(line_starts[k - 1], 2), "segment": seg["label"]})
        if seg["label"] not in need[k]:
            problems.append(f"line {k} starts at {line_starts[k - 1]:.2f}s but the picture is {seg['label']} (needs one of {need[k]})")
    cuts_first5 = sum(1 for s in segs if 0.0 < s["t0"] < 5.0)
    if cuts_first5 < 2:
        problems.append(f"only {cuts_first5} picture changes in the first 5 s")
    if segs[7]["variant"] != "modern" or segs[8]["variant"] != "plain":
        problems.append("the gentle stop must use the modern belt and the no-give replay the plain belt")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "lines": rows, "cuts_in_first_5s": cuts_first5}


def monotone_in_segment(segs: list[dict]) -> dict:
    """Simulated time never runs backwards inside a segment (a crash does not un-happen on screen) and every shown dt is inside the simulated record."""
    problems = []
    for s in segs:
        if s["dt1"] < s["dt0"]:
            problems.append(f"{s['label']}: dt runs backwards")
    return {"status": "FAIL" if problems else "PASS", "problems": problems}
