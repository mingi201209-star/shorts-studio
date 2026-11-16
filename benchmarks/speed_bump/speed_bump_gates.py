"""EP.03 content gates (pure functions, unit-tested). Numbers spoken in the narration must agree with the simulation that drew the picture;
narration sentences must start near the picture they talk about; the first three seconds must show the difference."""
from __future__ import annotations

import numpy as np

from benchmarks.speed_bump import speed_bump_motion as sim

#: spoken beat -> the frame at which its picture starts (card = comparison chart)
BEAT_PICTURE_START = sim.BEAT_PICTURE_START   # per film profile (EP03_FILM)
START_TOLERANCE_S = 1.2


def narration_numbers(peaks: dict) -> dict:
    if sim.FILM == "final":
        return narration_numbers_single_speed(peaks)
    problems = []
    ratio_b = peaks["B"]["short"]["peak_body_g"] / peaks["B"]["hump"]["peak_body_g"]
    if not 1.8 <= ratio_b <= 2.4:
        problems.append(f"'about twice as hard' at 30 km/h but the simulated ratio is {ratio_b:.2f}")
    ratios = [peaks[s]["short"]["peak_body_g"] / peaks[s]["hump"]["peak_body_g"] for s in ("A", "B", "C")]
    if not (min(ratios) >= 1.8 and max(ratios) <= 6.3):
        problems.append(f"'two to six times harsher at every speed' but ratios are {[round(r, 2) for r in ratios]}")
    c = peaks["C"]
    if not (c["hump"]["peak_body_g"] < 0.15 and c["short"]["peak_body_g"] > 0.4):
        problems.append("at 10 km/h the long hump must be gentle (<0.15 g) while the short bump still jolts (>0.4 g)")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "ratios": ratios}


def narration_numbers_single_speed(peaks: dict) -> dict:
    """The final cut compares the two bumps at ONE speed (20 km/h, pass A). Narration: the short bump lifts the wheel 'about four times faster', squeezes the
    spring 'more than twice as fast' and gives the body 'a jolt more than twice as hard' (peak body acceleration). Each claim is checked against the simulation."""
    a = peaks["A"]
    hub = a["short"]["peak_hub_rate_ms"] / a["hump"]["peak_hub_rate_ms"]
    spring = a["short"]["peak_spring_rate_ms"] / a["hump"]["peak_spring_rate_ms"]
    body = a["short"]["peak_body_g"] / a["hump"]["peak_body_g"]
    problems = []
    if not 3.5 <= hub <= 4.6:
        problems.append(f"'about four times faster' (wheel lift rate) but the simulated ratio is {hub:.2f}")
    if spring < 2.05:
        problems.append(f"'more than twice as fast' (spring squeeze rate) but the simulated ratio is {spring:.2f}")
    if body < 2.05:
        problems.append(f"'more than twice as hard' (peak body acceleration) but the simulated ratio is {body:.2f}")
    if not all(abs(peaks[k]["short"]["peak_hub_rate_ms"] - a["short"]["peak_hub_rate_ms"]) < 1e-9 for k in peaks):
        problems.append("passes do not share one speed")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "ratios": [round(hub, 2), round(spring, 2), round(body, 2)]}


def narration_picture_timing(audio_report: dict) -> dict:
    """Beat start (s) vs the film second where the picture it talks about starts. Beats 1-2 describe pass A (frames 1-320)."""
    problems = []
    beats = audio_report["beats"]
    for beat_no, frame in BEAT_PICTURE_START.items():
        start = beats[beat_no - 1]["start"]
        want = (frame - 1) / sim.FPS
        if abs(start - want) > START_TOLERANCE_S:
            problems.append(f"beat {beat_no} starts at {start:.2f}s, its picture starts at {want:.2f}s")
    if beats[1]["start"] > sim.BEAT2_BEFORE_FRAME / sim.FPS:
        problems.append("beat 2 must start while pass A is still on screen")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "beat_starts": [round(b["start"], 2) for b in beats]}


def picture_events_match_cues(audio_report: dict) -> dict:
    """Narration sync: every picture event the film profile declares (SYNC_EVENTS) must start within SYNC_TOLERANCE_S of the start of the spoken phrase it
    illustrates, measured from the captured speech timing (the same cues that time the captions)."""
    problems, rows = [], []
    cues = {c["text"].replace("\\N", " "): c for c in audio_report["cues"]}
    for text, event, frame in sim.SYNC_EVENTS:
        cue = cues.get(text)
        if cue is None:
            problems.append(f"no spoken cue {text!r} for picture event {event!r}")
            continue
        delta = (frame - 1) / sim.FPS - cue["start"]
        rows.append({"cue": text, "event": event, "cue_start_s": round(cue["start"], 2), "picture_start_s": round((frame - 1) / sim.FPS, 2), "delta_s": round(delta, 2)})
        if abs(delta) > sim.SYNC_TOLERANCE_S:
            problems.append(f"{event!r} starts {delta:+.2f}s from the spoken cue {text!r}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "events": rows}


def first_three_seconds(frames: dict[int, np.ndarray], first_contact_film_s: float) -> dict:
    """frames: film frame number -> RGB array (1080x1920). The picture is 3D only (no text): both cars must be on screen from the first moments (left and
    right halves of the side-by-side opening both busy), the picture must move, and the first jolt (front wheel meets the short bump) is inside 3 s."""
    problems = []
    first = frames[10][0:1440]          # the caption sits on the picture below row 1440
    if sim.shot_at(10)[1] == "stack":   # long hump on top, short bump below
        regions = (("top (long hump)", (slice(0, 960), slice(None))), ("bottom (short bump)", (slice(960, 1440), slice(None))))
    else:                               # long hump left, short bump right
        regions = (("left", (slice(None), slice(0, 540))), ("right", (slice(None), slice(540, 1080))))
    for name, (rows, cols) in regions:
        if float(first[rows, cols].std()) < 12:
            problems.append(f"{name} part of the opening picture looks empty at frame 10")
    if first_contact_film_s > 3.0:
        problems.append(f"first wheel/bump contact at {first_contact_film_s:.2f}s, later than 3 s")
    moved = float(np.abs(frames[90][0:1440].astype(int) - frames[10][0:1440].astype(int)).mean())
    if moved < 2.0:
        problems.append(f"almost nothing changes between frame 10 and 90 (mean diff {moved:.2f})")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "first_contact_film_s": round(first_contact_film_s, 2), "editorial_items": {
                "same_car_same_speed_stated_in_first_sentence": "from the speech plan (beat 1)",
                "difference_visible_within_3s": "UNVERIFIED (a person must look)",
                "narration_hook_starts_within_0.5s": "from captured speech timing (beat 1 starts at 0)"}}


def assumptions_in_narration(audio_report: dict) -> dict:
    """The picture carries no text, so the simulation / assumed-values disclosure has to be spoken (and repeated in the description)."""
    text = " ".join(b["narration_en"].lower() for b in audio_report["beats"])
    problems = [w for w in ("simulation", "assumed") if w not in text]
    return {"status": "FAIL" if problems else "PASS", "problems": [f"narration never says '{w}'" for w in problems]}


def assumptions_in_description(path) -> dict:
    """The owner moved the simulation / assumed-values disclosure out of the narration into the posted description (the picture carries no text and the
    narration should end on the explanation). The description file that goes with the film must still say it."""
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return {"status": "FAIL", "problems": [f"description file {p} is missing"]}
    text = p.read_text(encoding="utf8").lower()
    problems = [f"description never says '{w}'" for w in ("simulation", "assumed") if w not in text]
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "description_file": str(p)}


def first_contact_film_seconds() -> float:
    seg = sim.SEGMENTS[0]
    v = seg["kmh"] / 3.6
    t_contact = sim.SIM_LEAD_M / v          # front axle reaches the bump (simulate() starts 3 m before it)
    t0 = (sim.SIM_LEAD_M - seg["lead_m"]) / v
    return (t_contact - t0) / seg["slow"]


# ----------------------------------------------------------------------------- final-cut gates (owner review of 1000020414.mp4): pure simulation checks + pixel checks
def _pass_rec(bump: str, seg: dict):
    return sim.simulate(sim.BUMPS[bump], speed_kmh=seg["kmh"], car=sim.CAR, hz=sim.RENDER_HZ)


def tyre_road_contact(info_c: dict | None = None) -> dict:
    """The rendered wheel follows the rigid tyre envelope (|gap| <= 5 mm in every frame of every pass): no tyre inside the bump, no floating tyre. The simulated
    tyre compliance that is NOT drawn is reported so the picture and the description stay honest."""
    worst, compliance = 0.0, 0.0
    for key in sorted({(s["kmh"]) for s in sim.SEGMENTS}):
        seg = next(s for s in sim.SEGMENTS if s["kmh"] == key)
        for bump in sim.BUMPS:
            rec = _pass_rec(bump, seg)
            for u, w in (("uf", "wf"), ("ur", "wr")):
                vis = np.array([sim.visual_wheel_z(a, b) for a, b in zip(rec[u], rec[w])])
                worst = max(worst, float(np.max(np.abs(vis - rec[w]))))
                compliance = max(compliance, float(np.max(np.abs(rec[u] - rec[w]))))
    problems = []
    if worst > 0.005:
        problems.append(f"drawn wheel is {1000 * worst:.1f} mm off the tyre envelope (limit 5 mm)")
    if info_c is not None and info_c.get("rendered_wheel_gap_mm_max", 0.0) > 5.0:
        problems.append(f"rendered telemetry reports a {info_c['rendered_wheel_gap_mm_max']} mm wheel gap")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "max_drawn_gap_mm": round(1000 * worst, 2),
            "simulated_tyre_compliance_not_drawn_mm": round(1000 * compliance, 1),
            "rendered_gap_mm_max": None if info_c is None else info_c.get("rendered_wheel_gap_mm_max")}


def suspension_timing(max_lag_s: float = 0.06) -> dict:
    """Spring squeeze must follow the wheel: on the short bump the peak squeeze RATE comes after the peak wheel-lift rate and within max_lag_s of it
    (simulated seconds; the film is slowed 5x, so 0.06 s is about 9 film frames); the spring then returns to within 25 % of its peak squeeze."""
    seg = sim.SEGMENTS[0]
    rec = _pass_rec("short", seg)
    t = rec["t"]
    hub_rate = np.gradient(rec["wf"], t)
    squeeze_rate = np.gradient(-rec["df"], t)
    t_hub, t_spring = float(t[int(np.argmax(hub_rate))]), float(t[int(np.argmax(squeeze_rate))])
    peak = float(np.max(-rec["df"]))
    i_peak = int(np.argmax(-rec["df"]))
    restored = float(np.min(np.abs(rec["df"][i_peak:])))
    problems = []
    if not 0.0 <= t_spring - t_hub <= max_lag_s:
        problems.append(f"spring squeeze peaks {t_spring - t_hub:+.3f}s after the wheel lift (allowed 0 to {max_lag_s}s)")
    if restored > 0.25 * peak:
        problems.append("spring does not return towards rest after the peak squeeze")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "wheel_lift_peak_t": round(t_hub, 3), "spring_squeeze_peak_t": round(t_spring, 3),
            "lag_film_frames": round((t_spring - t_hub) / sim.SEGMENTS[0]["slow"] * sim.FPS, 1)}


def _sky_fraction(p: np.ndarray) -> float:
    r, g, b = (p[..., i].astype(int) for i in range(3))
    return float(((g > 140) & (b > 150) & (b >= r)).mean())


def xray_readability(load, frames=(180, 230, 290, 360, 440, 520, 600), max_median=0.40, max_each=0.50) -> dict:
    """The ghost body must be seen against the road, not against the sky: the share of sky-coloured pixels in the (full, 960-row) top panel of X-ray frames
    stays low. Both panels use the same camera, so the top panel stands for both. Measured on the rendered frames; the previous cut had 0.44-0.65."""
    rows = [{"frame": f, "sky_share": round(_sky_fraction(load(f)[0:960]), 3)} for f in frames]
    vals = [r["sky_share"] for r in rows]
    problems = []
    if float(np.median(vals)) > max_median:
        problems.append(f"median sky share {np.median(vals):.2f} > {max_median}")
    if max(vals) > max_each:
        problems.append(f"a frame has {max(vals):.2f} sky share > {max_each}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "median_sky_share": round(float(np.median(vals)), 3), "frames": rows}


def _warm_share(p: np.ndarray, box) -> float:
    h, w = p.shape[:2]
    x0, y0, x1, y1 = box          # normalised, y up
    c0, c1 = max(0, int((x0 - 0.05) * w)), min(w, int((x1 + 0.05) * w) + 1)
    r0, r1 = max(0, int((1 - y1 - 0.03) * h)), min(h, int((1 - y0 + 0.03) * h) + 1)
    q = p[r0:r1, c0:c1].astype(int)
    if q.size == 0:
        return 0.0
    return float(((q[..., 0] > 190) & (q[..., 0] - q[..., 2] > 40) & (q[..., 1] > 50)).mean())


def spring_tracks_simulation(load, wheelbase: float, proj: dict, first=203, last=262, min_r=0.9, min_range_px=4.0, min_warm=0.04) -> dict:
    """Continuous motion of the spring in the close-up: (1) the spring drawn by the renderer (its two ends projected through the shot's camera) changes length
    together with the simulated spring length (Pearson r); (2) the change is large enough to see (px in the 960-row panel); (3) the warm-coloured spring
    pixels really are in the composed frames where the renderer put the spring."""
    from benchmarks.speed_bump.speed_bump_timeline import Timeline
    tl = Timeline(wheelbase, hz=sim.RENDER_HZ)
    out, problems = {}, []
    for panel, rows in (("hump", slice(0, 960)), ("short", slice(960, 1920))):
        length, ref, warm = [], [], []
        for f in range(first, last + 1):
            pr = (proj.get(str(f)) or proj.get(f) or {}).get(panel)
            if not pr:
                continue
            seg, t = sim.frame_to_pass(f)
            rec = tl.recs[(seg["id"], panel)]
            i = min(int(round(t * sim.RENDER_HZ)), len(rec["t"]) - 1)
            length.append(pr[0] * 960)
            ref.append(0.37 + float(rec["zf"][i]) - sim.visual_wheel_z(rec["uf"][i], rec["wf"][i]))
            warm.append(_warm_share(load(f)[rows], pr[1:]))
        if len(length) < 0.9 * (last - first + 1):
            problems.append(f"{panel}: the spring is projected in only {len(length)} of {last - first + 1} close-up frames")
            out[panel] = {"frames": len(length)}
            continue
        a, b = np.array(length), np.array(ref)
        r = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
        seen = float(np.mean([w >= min_warm for w in warm]))
        out[panel] = {"frames": len(length), "pearson_r": round(r, 3), "length_range_px": round(float(a.max() - a.min()), 1), "warm_pixels_found_share": round(seen, 2)}
        if r < min_r:
            problems.append(f"{panel}: drawn spring length follows the simulation only with r={r:.2f} (need {min_r})")
        if a.max() - a.min() < min_range_px:
            problems.append(f"{panel}: the drawn spring changes by only {a.max() - a.min():.1f} px (need {min_range_px})")
        if seen < 0.8:
            problems.append(f"{panel}: spring-coloured pixels found in only {seen:.0%} of the frames where the spring is drawn")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, **out}


def _sign_pixels(p: np.ndarray) -> int:
    r, g, b = (p[..., i].astype(int) for i in range(3))
    return int(((g > 200) & (g - r > 30) & (g - b > 80) & (b < 170)).sum())


def signs_visible(load, in_view: dict, min_px=40, min_frames=150) -> dict:
    """LONG / SHORT signs: the panel order is fixed (long on top); in every frame where the renderer reports a sign inside the camera view the sign pixels
    must really be in the picture, and the signs must be on screen for most of the comparison (including 19-25 s and the closing replay)."""
    both = [int(f) for f, v in in_view.items() if v["hump"] and v["short"]]
    problems = []
    if len(both) < min_frames:
        problems.append(f"both signs are in view in only {len(both)} frames (need {min_frames})")
    for lo, hi, name in ((570, 750, "19-25 s"), (783, 930, "closing replay")):
        if sum(1 for f in both if lo <= f <= hi) < 30:
            problems.append(f"fewer than 30 frames with both signs in view during {name}")
    sample = both[:: max(1, len(both) // 24)] if both else []
    missing = []
    for f in sample:
        img = load(f)
        if _sign_pixels(img[0:960]) < min_px or _sign_pixels(img[960:1920]) < min_px:
            missing.append(f)
    if sample and len(missing) > 0.15 * len(sample):
        problems.append(f"sign pixels missing in frames {missing[:8]} although the renderer says they are in view")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "frames_with_both_signs": len(both), "sampled": len(sample), "missing": missing}


def shots_are_distinct() -> dict:
    """No two neighbouring shots use the same camera, and no shot is longer than 105 frames (3.5 s) without a cut."""
    problems = []
    for (a1, b1, k1, _), (a2, b2, k2, _) in zip(sim.SHOTS, sim.SHOTS[1:]):
        if k1 == k2:
            problems.append(f"shots {a1}-{b1} and {a2}-{b2} use the same camera {k1!r}")
    for a, b, k, _ in sim.SHOTS:
        if b - a + 1 > 105:
            problems.append(f"shot {a}-{b} is longer than 3.5 s")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "shots": len(sim.SHOTS)}
