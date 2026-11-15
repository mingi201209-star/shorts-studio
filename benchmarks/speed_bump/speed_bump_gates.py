"""EP.03 content gates (pure functions, unit-tested). Numbers spoken in the narration must agree with the simulation that drew the picture;
narration sentences must start near the picture they talk about; the first three seconds must show the difference."""
from __future__ import annotations

import numpy as np

from benchmarks.speed_bump import speed_bump_motion as sim

#: spoken beat -> the frame at which its picture starts (card = comparison chart)
BEAT_PICTURE_START = {3: 321, 4: 481, 5: sim.PASS_FRAMES + 1}
START_TOLERANCE_S = 1.2


def narration_numbers(peaks: dict) -> dict:
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


def narration_picture_timing(audio_report: dict) -> dict:
    """Beat start (s) vs the film second where the picture it talks about starts. Beats 1-2 describe pass A (frames 1-320)."""
    problems = []
    beats = audio_report["beats"]
    for beat_no, frame in BEAT_PICTURE_START.items():
        start = beats[beat_no - 1]["start"]
        want = (frame - 1) / sim.FPS
        if abs(start - want) > START_TOLERANCE_S:
            problems.append(f"beat {beat_no} starts at {start:.2f}s, its picture starts at {want:.2f}s")
    if beats[1]["start"] > 320 / sim.FPS:
        problems.append("beat 2 must start while pass A is still on screen")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "beat_starts": [round(b["start"], 2) for b in beats]}


def first_three_seconds(frames: dict[int, np.ndarray], first_contact_film_s: float) -> dict:
    """frames: film frame number -> RGB array (1080x1920). Hook text visible early and gone later, both panels not empty,
    and the first jolt (front wheel meets the short bump) happens inside 3 s."""
    problems = []
    region = (slice(540, 640), slice(40, 1040))

    def plate_mean(f):
        return float(frames[f][region].mean())

    early, late = plate_mean(10), plate_mean(120)
    if early - late < 25:
        problems.append(f"hook text not visible in the first second (plate region mean {early:.0f} vs {late:.0f} later)")
    for name, rows in (("top", slice(0, 560)), ("bottom", slice(570, 1130))):
        if float(frames[10][rows].std()) < 12:
            problems.append(f"{name} panel looks empty at frame 10")
    if first_contact_film_s > 3.0:
        problems.append(f"first wheel/bump contact at {first_contact_film_s:.2f}s, later than 3 s")
    moved = float(np.abs(frames[90][0:1130].astype(int) - frames[10][0:1130].astype(int)).mean())
    if moved < 2.0:
        problems.append(f"almost nothing changes between frame 10 and 90 (mean diff {moved:.2f})")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "first_contact_film_s": round(first_contact_film_s, 2), "editorial_items": {
                "question_text_on_screen_within_1s": "pixel-checked only; the wording quality is UNVERIFIED",
                "difference_visible_within_3s": "UNVERIFIED (a person must look)",
                "narration_hook_starts_within_0.5s": "from captured speech timing (beat 1 starts at 0)"}}


def first_contact_film_seconds() -> float:
    seg = sim.SEGMENTS[0]
    v = seg["kmh"] / 3.6
    t_contact = sim.SIM_LEAD_M / v          # front axle reaches the bump (simulate() starts 3 m before it)
    t0 = (sim.SIM_LEAD_M - seg["lead_m"]) / v
    return (t_contact - t0) / seg["slow"]
