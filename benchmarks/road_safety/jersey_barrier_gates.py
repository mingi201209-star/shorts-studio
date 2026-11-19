"""Quality gates for the Jersey barrier episode that read the renderer's
per-frame telemetry. Pure functions, no Blender and no ffmpeg, so they are
unit-tested (tests/test_jersey_barrier_gates.py).

What "match" means here, exactly: for each narrated sentence, the physical
condition the sentence describes must be (a) true in the simulated state
the frame was drawn from and (b) located inside the visible picture, not
hidden behind other geometry, and large enough to read, for a minimum time
WHILE THE SENTENCE IS BEING SPOKEN (real caption-cue timing from the
captured narration, not the planned timing).

What it does not do: it does not look at pixels or understand images. It
cannot tell whether a shot is attractive or whether a viewer will follow
it. It can only fail a film whose picture is not showing the thing being
said -- which is the failure this gate exists to stop.
"""
from __future__ import annotations


def spoken_windows(audio_report: dict) -> list[dict]:
    """One window per narrated sentence: from its first caption cue to its
    last, inside the beat the audio builder locked for it."""
    windows = []
    cues = audio_report["cues"]
    for beat in audio_report["beats"]:
        inside = [c for c in cues if beat["start"] - 1e-6 <= c["start"] and c["end"] <= beat["end"] + 1e-6]
        if not inside:
            raise ValueError(f"no caption cues inside beat: {beat['narration_en']!r}")
        windows.append({"text": beat["narration_en"], "start": min(c["start"] for c in inside),
                        "end": max(c["end"] for c in inside)})
    return windows


def _seen(record: dict, event: str) -> bool:
    entry = record["events"].get(event)
    return bool(entry and entry["active"] and entry.get("visible"))


def narration_screen_match(manifest: dict, audio_report: dict, telemetry: dict[int, dict]) -> dict:
    fps = manifest["fps"]
    shots = manifest["shots"]
    windows = spoken_windows(audio_report)
    if len(windows) != len(shots):
        raise ValueError("one narrated sentence per shot is required")
    sentences, problems = [], []
    for index, (shot, window) in enumerate(zip(shots, windows), start=1):
        if shot["narration_en"] != window["text"]:
            problems.append(f"sentence {index}: manifest text differs from the captured narration")
        first = max(1, int(window["start"] * fps) + 1)
        last = min(manifest["total_frames"], int(window["end"] * fps))
        frames = [telemetry[f] for f in range(first, last + 1)]
        outside = sum(1 for r in frames if r["shot_id"] != shot["id"])
        checks = []
        for need in shot["must_show_while_spoken"]:
            seconds = sum(1 for r in frames if _seen(r, need["event"])) / fps
            ok = seconds + 1e-9 >= need["min_seconds"]
            checks.append({"event": need["event"], "visible_seconds": round(seconds, 3),
                           "required_seconds": need["min_seconds"], "status": "PASS" if ok else "FAIL"})
            if not ok:
                problems.append(
                    f"sentence {index} ({window['start']:.2f}-{window['end']:.2f}s) "
                    f"{need['event']}: on screen {seconds:.2f}s, needs {need['min_seconds']}s")
        # A sentence that runs well past its own shot is being spoken over
        # the wrong picture even if an event happens to match.
        spill = outside / max(1, len(frames))
        if spill > 0.15:
            problems.append(f"sentence {index}: {spill:.0%} of it is spoken over another shot")
        sentences.append({"sentence": index, "text": window["text"], "shot_id": shot["id"],
                          "spoken": [round(window["start"], 3), round(window["end"], 3)],
                          "frames": [first, last], "spoken_over_other_shot": round(spill, 3),
                          "checks": checks})
    return {"status": "FAIL" if problems else "PASS", "method": "simulation-state + visibility telemetry",
            "problems": problems, "sentences": sentences}


def first_three_seconds(manifest: dict, telemetry: dict[int, dict]) -> dict:
    """Counts physical events that BECOME true-and-visible inside the first
    three seconds. A cut, a zoom or an event already true on frame 1 does
    not count: only something starting to happen in the picture does."""
    rule = manifest["first_three_seconds"]
    fps = manifest["fps"]
    last = int(3.0 * fps)
    onsets = []
    for event in rule["counted_events"]:
        previous = _seen(telemetry[1], event)
        for frame in range(2, last + 1):
            now = _seen(telemetry[frame], event)
            if now and not previous:
                onsets.append({"event": event, "frame": frame, "seconds": round((frame - 1) / fps, 3)})
                break
            previous = now
    onsets.sort(key=lambda o: o["frame"])
    distinct = []
    for onset in onsets:
        if not distinct or onset["seconds"] - distinct[-1]["seconds"] >= rule["min_separation_seconds"]:
            distinct.append(onset)
    ok = len(distinct) >= rule["min_distinct_visible_event_onsets"]
    return {"status": "PASS" if ok else "FAIL", "onsets": onsets, "distinct_onsets": distinct,
            "required": rule["min_distinct_visible_event_onsets"]}


#: Bounds the simulated motion has to stay inside for the film's claims to
#: hold and for the motion not to be exaggerated. A shallow hit: the tyre
#: stays on the lower slope, the body never reaches the wall, nothing spins.
MOTION_LIMITS = {
    "jersey": {"min_body_gap_m": (0.02, None), "peak_wheel_lift_m": (0.05, 0.30),
               "peak_compression_m": (0.02, 0.09), "peak_corner_rise_m": (0.03, 0.25),
               "max_abs_yaw_rate_dps": (None, 30.0), "end_speed_mps": (11.0, None)},
    "flat": {"peak_wheel_lift_m": (None, 0.0), "peak_body_force_kN": (1.0, 40.0),
             "max_abs_yaw_rate_dps": (None, 40.0)},
}


def motion_plausibility(summaries: dict) -> dict:
    problems = []
    for wall, limits in MOTION_LIMITS.items():
        for key, (low, high) in limits.items():
            value = summaries[wall][key]
            if (low is not None and value < low) or (high is not None and value > high):
                problems.append(f"{wall}.{key}={value} outside [{low}, {high}]")
    if summaries["jersey"]["first_body_contact_s"] is not None:
        problems.append("jersey: the body reached the wall")
    if summaries["flat"]["first_body_contact_s"] is None:
        problems.append("flat: the body never reached the wall")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "summaries": summaries}


#: Captions live in the black band (rows 1400-1919 of 1920). The lower part
#: of that band sits under the YouTube Shorts title/channel overlay, so the
#: text itself has to stay in the upper part of the band.
CAPTION_BAND_TOP = 1400
CAPTION_TEXT_FLOOR = 1540


def caption_safety(cues: list[dict], measured: list[dict]) -> dict:
    """measured: verify_captions_visible evidence, [{t, rows_in_band:[top,bottom]}]."""
    problems = []
    for a, b in zip(cues, cues[1:]):
        if b["start"] < a["end"] - 1e-6:
            problems.append(f"captions overlap in time: {a['text']!r} / {b['text']!r}")
    for cue in cues:
        if cue["end"] - cue["start"] < 0.25:
            problems.append(f"caption on screen under 0.25s: {cue['text']!r}")
    for item in measured:
        top, bottom = item["rows_in_band"]
        if top < CAPTION_BAND_TOP + 8 or bottom > CAPTION_TEXT_FLOOR:
            problems.append(f"caption at t={item['t']:.2f}s spans rows {top}-{bottom}, "
                            f"outside {CAPTION_BAND_TOP + 8}-{CAPTION_TEXT_FLOOR}")
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "text_rows": [min(i["rows_in_band"][0] for i in measured), max(i["rows_in_band"][1] for i in measured)]}
