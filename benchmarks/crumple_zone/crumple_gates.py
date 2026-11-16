"""EP.04 gates for the crumple-zone film (pure functions, unit-tested): simulation facts the narration relies on, geometry facts the renderer must keep, and pixel checks
on rendered frames. Nothing here is weakened to pass; thresholds are stated next to the check."""
from __future__ import annotations

import numpy as np

from benchmarks.crumple_zone import crumple_motion as cm
from benchmarks.speed_bump import speed_bump_gates as sbg


def same_conditions(recs: dict | None = None) -> dict:
    recs = recs or {k: cm.simulate(k) for k in cm.PROFILES}
    a, b = recs["crumple"], recs["rigid"]
    problems = [name for name in ("v0", "mass", "lead") if abs(a[name] - b[name]) > 1e-12]
    return {"status": "FAIL" if problems else "PASS", "problems": [f"{n} differs between the compared cars" for n in problems],
            "speed_kmh": cm.V0_KMH, "mass_kg": cm.MASS}


def energy_and_claims(recs: dict | None = None) -> dict:
    """Both cars absorb the same kinetic energy (same speed and mass); the crumple car does it over a much longer stopping distance and time, so its AVERAGE force
    is lower: F_avg = m v / t_stop. The narration only claims 'average force is far higher' for the rigid front: required ratio >= 5."""
    recs = recs or {k: cm.simulate(k) for k in cm.PROFILES}
    s = {k: cm.summary(r) for k, r in recs.items()}
    ek = 0.5 * cm.MASS * (cm.V0_KMH / 3.6) ** 2
    problems = []
    for k, r in recs.items():
        work = float(np.trapezoid(r["g"] * cm.G * r["mass"], r["d"])) if hasattr(np, "trapezoid") else float(np.trapz(r["g"] * cm.G * r["mass"], r["d"]))
        # crush work up to the stop (the rigid car then rebounds; only the crush phase is compared)
        stop = int(np.argmax(r["v"] <= 0)) if np.any(r["v"] <= 0) else len(r["t"]) - 1
        crush_work = float(np.trapezoid(r["g"][:stop + 1] * cm.G * r["mass"], r["d"][:stop + 1])) if hasattr(np, "trapezoid") else float(
            np.trapz(r["g"][:stop + 1] * cm.G * r["mass"], r["d"][:stop + 1]))
        if abs(crush_work - ek) / ek > 0.03:
            problems.append(f"{k}: crush work {crush_work:.0f} J differs from the kinetic energy {ek:.0f} J")
    ratio = s["rigid"]["average_force_kn"] / s["crumple"]["average_force_kn"]
    if ratio < 5.0:
        problems.append(f"'far higher average force' but the simulated ratio is only {ratio:.1f}")
    if s["crumple"]["stop_time_s"] < 3 * s["rigid"]["stop_time_s"]:
        problems.append("the crumple car does not stop over a clearly longer time")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "force_ratio_rigid_over_crumple": round(ratio, 1),
            "stroke_m": {k: round(v["stroke_m"], 3) for k, v in s.items()}, "stop_time_ms": {k: round(1000 * v["stop_time_s"], 1) for k, v in s.items()},
            "average_decel_g": {k: round(v["average_decel_g"], 1) for k, v in s.items()}, "kinetic_energy_kj": round(ek / 1000, 1)}


def crush_map_keeps_the_cell(nose: float = 2.0) -> dict:
    """The crush map must (1) never move points deeper than the crushed depth (the passenger cell and everything behind), (2) keep points in front-to-back order along the
    car axis (no folding through itself), (3) push the nose back by exactly the stroke, (4) progress rearward: the crushed depth grows with the stroke."""
    rng = np.random.default_rng(4)
    pts = np.column_stack([rng.uniform(-0.9, 0.9, 4000), rng.uniform(nose - 3.6, nose, 4000), rng.uniform(0.1, 1.4, 4000)])
    problems, depths = [], []
    for s in (0.05, 0.2, 0.4, 0.62):
        out = cm.crush_map(pts, s, nose)
        d_c = min(s / cm.COMPACTION, cm.CRUSH_LENGTH)
        deep = pts[:, 1] <= nose - d_c
        moved = float(np.abs(out[deep] - pts[deep]).max()) if deep.any() else 0.0
        if moved > 1e-9:
            problems.append(f"stroke {s}: points behind the crushed zone moved by {moved:.4f} m")
        order = np.argsort(pts[:, 1])
        ys = out[order, 1]
        if np.any(np.diff(ys) < -1e-9):
            problems.append(f"stroke {s}: points fold through each other along the car axis")
        front = np.array([[0.0, nose, 0.5]])
        if abs(cm.crush_map(front, s, nose)[0, 1] - (nose - s)) > 1e-9:
            problems.append(f"stroke {s}: the nose is not pushed back by the stroke")
        depths.append(d_c)
    if depths != sorted(depths):
        problems.append("crushed depth does not grow with the stroke")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "crushed_depth_m": [round(d, 3) for d in depths]}


def telemetry_geometry(telemetry: list[dict], max_penetration_mm=5.0, max_wheel_gap_mm=1.0) -> dict:
    """From the renderer's per-frame numbers: the deformed nose never goes through the barrier, the wheel keeps its ground height, the crush stroke never shrinks
    within a pass (permanent deformation) and the first contact happens within 1 s of film."""
    problems, worst_pen, worst_gap = [], 0.0, 0.0
    last = {}
    for t in telemetry:
        for panel in ("crumple", "rigid"):
            p = t.get(panel)
            if not p:
                continue
            worst_pen, worst_gap = max(worst_pen, p["nose_penetration_mm"]), max(worst_gap, p["wheel_z_gap_mm"])
            key = (t["segment"], panel)
            if key in last and p["stroke_m"] < last[key] - 1e-6:
                problems.append(f"stroke shrinks in segment {t['segment']} {panel} at frame {t['frame']}")
            last[key] = p["stroke_m"]
    if worst_pen > max_penetration_mm:
        problems.append(f"the deformed nose is {worst_pen:.1f} mm inside the barrier")
    if worst_gap > max_wheel_gap_mm:
        problems.append(f"a wheel leaves its ground height by {worst_gap:.2f} mm")
    contact = cm.first_contact_film_s("H")
    if contact > 1.0:
        problems.append(f"first contact at {contact:.2f}s")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "max_nose_penetration_mm": worst_pen, "max_wheel_gap_mm": worst_gap,
            "first_contact_film_s": round(contact, 2)}


def deformation_visible_by(telemetry: list[dict], frame: int = 60, min_stroke_m: float = 0.2) -> dict:
    row = next(t for t in telemetry if t["frame"] == frame)
    s = row["crumple"]["stroke_m"]
    return {"status": "PASS" if s >= min_stroke_m else "FAIL", "problems": [] if s >= min_stroke_m else [f"stroke {s:.2f} m at frame {frame} (< {min_stroke_m})"],
            "stroke_m_at_frame": s, "frame": frame}


def xray_against_road(load, frames=(80, 95, 110, 125), max_median=0.40, max_each=0.50) -> dict:
    return sbg.xray_readability(load, frames=frames, max_median=max_median, max_each=max_each)


def labels_visible(load, telemetry: list[dict], min_frames=25, min_px=40) -> dict:
    """CRUMPLE on top, RIGID below in the comparison: the 3D signs must be inside the camera view in most comparison frames and really be in the picture."""
    both = [t["frame"] for t in telemetry if t["layout"] == "stack" and t["crumple"]["sign_in_view"] and t["rigid"]["sign_in_view"]]
    problems = []
    if len(both) < min_frames:
        problems.append(f"both signs are in view in only {len(both)} comparison frames (need {min_frames})")
    sample = both[:: max(1, len(both) // 12)] if both else []
    missing = [f for f in sample if sbg._sign_pixels(load(f)[0:960]) < min_px or sbg._sign_pixels(load(f)[960:1920]) < min_px]
    if sample and len(missing) > 0.15 * len(sample):
        problems.append(f"sign pixels missing in frames {missing[:6]}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "frames_with_both_signs": len(both), "missing": missing}


def smoothness(frame_diffs: np.ndarray, min_median=0.3) -> dict:
    """Continuous motion: no frozen frame (mean gray diff to the previous frame < 0.02) in the whole clip, and the median change is visible."""
    frozen = int((frame_diffs < 0.02).sum())
    med = float(np.median(frame_diffs))
    problems = []
    if frozen:
        problems.append(f"{frozen} frozen frames")
    if med < min_median:
        problems.append(f"median frame change {med:.2f} < {min_median}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "frozen_frames": frozen, "median_diff": round(med, 3)}


def sync_to_speech(cues: list[dict]) -> dict:
    problems, rows = [], []
    by_text = {c["text"].replace("\\N", " "): c for c in cues}
    for text, event, frame in cm.SYNC_EVENTS:
        cue = by_text.get(text)
        if cue is None:
            problems.append(f"no spoken cue {text!r}")
            continue
        delta = (frame - 1) / cm.FPS - cue["start"]
        rows.append({"cue": text, "event": event, "cue_start_s": round(cue["start"], 2), "picture_start_s": round((frame - 1) / cm.FPS, 2), "delta_s": round(delta, 2)})
        if abs(delta) > cm.SYNC_TOLERANCE_S:
            problems.append(f"{event!r} starts {delta:+.2f}s from the spoken cue {text!r}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "events": rows}
