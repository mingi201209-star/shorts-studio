"""EP.24 musical road (pure Python + numpy). Render-world coordinates: a two-lane desert road runs along +y; the musical section is cut
into the right-hand lane from y = 0. Every note is a stretch of grooves milled across the lane at an even spacing; a tyre rolling at
speed v hits v / spacing grooves a second, and that thump rate is the note's pitch (f = v / s). Short stretches of smooth asphalt
between notes separate repeated notes. The tune is the opening phrase of the finale of Rossini's William Tell Overture (1829, public
domain), played twice, laid out for 55 mph.

Two versions of the same road:
- design: the plan's spacing is measured groove to groove (centre to centre), so every note is in tune at 55 mph;
- built: the crew cut the plan's spacing as the gap between grooves, so each centre-to-centre spacing grew by one groove width; every
  note comes out flat by s / (s + w), and the closer the grooves (the higher the note), the bigger the share the width adds.
The note stretches keep their planned lengths, so the tempo stays and only the pitch is wrong. Driving slower scales every note's
pitch and the tempo by the same factor. The rear tyres replay the tune a wheelbase later. Simplified explanation model; the groove
width and depth are assumptions, not survey data of the real road."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

MPH = 0.44704
IN = 0.0254
V_DESIGN = 55 * MPH
V_SLOW = 35 * MPH
SIXTEENTH = 0.1                          # s: quarter note = 150 bpm at the design speed
GROOVE_W = 0.75 * IN                     # milled groove width (assumption)
GROOVE_D = 0.012                         # groove depth (assumption)
REST = 0.22                              # share of each note left as smooth asphalt (separates repeated notes)
LANE_X = (0.15, 3.45)                    # grooves across the right lane (x from the centre line)
WHEELBASE = 2.312                        # the CC0 sedan, measured from the mesh
FRONT_AXLE = 1.087                       # ahead of the car's reference point
TYRE_R = 0.281
TRACK = 1.43                             # between the left and right tyres
CAR_X = 1.8                              # the car's centre line in the right lane
START_Y = 0.0                            # first groove stretch
A4 = 440.0
NOTE = {"E3": -17, "B3": -10, "E4": -5, "F#4": -3, "G#4": -1, "A4": 0}
PHRASE = [("B3", 1), ("B3", 1), ("B3", 2), ("B3", 1), ("B3", 1), ("B3", 2), ("B3", 1), ("B3", 1), ("E4", 2), ("F#4", 2), ("G#4", 4)]
TUNE = PHRASE + [(None, 2)] + PHRASE


def freq(name: str) -> float:
    return A4 * 2 ** (NOTE[name] / 12)


@lru_cache(maxsize=None)
def layout(version: str) -> tuple:
    """Note stretches along the road: (y start, y end of grooves, y end with the rest, note, design spacing, cut spacing)."""
    out = []
    y = START_Y
    for name, n16 in TUNE:
        length = n16 * SIXTEENTH * V_DESIGN
        if name is None:
            y += length
            continue
        s = V_DESIGN / freq(name)
        cut = s if version == "design" else s + GROOVE_W
        out.append((y, y + length * (1 - REST), y + length, name, s, cut))
        y += length
    return tuple(out)


def road_end(version: str = "design") -> float:
    return layout(version)[-1][2]


@lru_cache(maxsize=None)
def grooves(version: str) -> np.ndarray:
    """Centre line (y) of every groove cut in the lane."""
    ys = []
    for y0, y1, _, _, _, cut in layout(version):
        n = int(math.floor((y1 - y0) / cut)) + 1
        ys.extend(y0 + cut * np.arange(n))
    return np.array(ys)


def played_freq(name: str, version: str, v: float) -> float:
    s = V_DESIGN / freq(name)
    return v / (s if version == "design" else s + GROOVE_W)


def cents(f: float, ref: float) -> float:
    return 1200 * math.log2(f / ref)


def car_y(t: float, v: float) -> float:
    """Car reference point at time t (s) for a car at constant speed v: the front tyres reach the first groove at t = 0."""
    return START_Y - FRONT_AXLE + v * t


@lru_cache(maxsize=None)
def hits(version: str, speed: str) -> tuple[np.ndarray, np.ndarray]:
    """Times (s) when the front and the rear tyres drop into a groove (the thumps), for a car at the design or the slow speed."""
    v = V_DESIGN if speed == "design" else V_SLOW
    g = grooves(version)
    front = (g - START_Y) / v
    rear = front + WHEELBASE / v
    return front, rear


def thump_rate(t: float, version: str, speed: str) -> float:
    """Thumps a second from the front tyres at time t (0 between notes)."""
    v = V_DESIGN if speed == "design" else V_SLOW
    y = START_Y + v * t
    for y0, y1, _, _, _, cut in layout(version):
        if y0 <= y <= y1:
            return v / cut
    return 0.0


def note_at(t: float, version: str, speed: str) -> str | None:
    v = V_DESIGN if speed == "design" else V_SLOW
    y = START_Y + v * t
    for y0, y1, _, name, _, _ in layout(version):
        if y0 <= y <= y1:
            return name
    return None


def wheel_angle(t: float, v: float) -> float:
    return (v * t) / TYRE_R


def bounce(t: float, version: str, speed: str) -> float:
    """Small vertical jiggle of the tyre over the grooves (m), only where the tyre is over grooves; drawn, not used for sound."""
    r = thump_rate(t, version, speed)
    return 0.0 if r == 0 else 0.0025 * math.sin(2 * math.pi * r * t) ** 2


def musical_physics() -> dict:
    """Gate: the tune is in tune as designed, flat as built (the high notes the most), lower and slower at a lower speed."""
    problems = []
    rows = []
    for name in ("B3", "E4", "F#4", "G#4"):
        fd = played_freq(name, "design", V_DESIGN)
        fb = played_freq(name, "built", V_DESIGN)
        rows.append({"note": name, "hz": round(freq(name), 1), "spacing_in": round(V_DESIGN / freq(name) / IN, 2),
                     "design_cents": round(cents(fd, freq(name)), 2), "built_hz": round(fb, 1), "built_cents": round(cents(fb, freq(name)), 1)})
    if any(abs(r["design_cents"]) > 1.0 for r in rows):
        problems.append("the designed spacing is not in tune at 55 mph")
    flats = [r["built_cents"] for r in rows]
    if not all(c < -50 for c in flats) or not all(a > b for a, b in zip(flats, flats[1:])):
        problems.append(f"the built road is not flat with the high notes flattest ({flats})")
    if min(r["hz"] for r in rows) < 150:
        problems.append("a note is under 150 thumps a second (\"hundreds of thumps a second\")")
    slow = cents(V_SLOW, V_DESIGN)
    if not -900 < slow < -600:
        problems.append("35 mph is not between 6 and 9 semitones lower")
    span_design = cents(freq("G#4"), freq("B3"))
    span_built = cents(played_freq("G#4", "built", V_DESIGN), played_freq("B3", "built", V_DESIGN))
    if not span_built < span_design - 100:
        problems.append("the built road does not squeeze the tune's leap")
    f_front, _ = hits("design", "design")
    n_hit = len(f_front)
    tune_s = (road_end() - START_Y) / V_DESIGN
    if abs(tune_s - sum(n for _, n in TUNE) * SIXTEENTH) > 1e-6:
        problems.append("the tune's length on the road does not match its notes")
    if abs(road_end("built") - road_end("design")) > 1e-9:
        problems.append("the built note stretches are not the planned lengths")
    return {
        "status": "FAIL" if problems else "PASS", "problems": problems, "notes": rows, "design_speed_mph": 55, "slow_speed_mph": 35,
        "slow_shift_cents": round(slow, 1), "slow_tempo_share": round(V_SLOW / V_DESIGN, 3), "groove_width_in": GROOVE_W / IN,
        "leap_design_cents": round(span_design, 1), "leap_built_cents": round(span_built, 1), "tune_seconds": round(tune_s, 2),
        "road_m": round(road_end() - START_Y, 1), "grooves_design": n_hit, "grooves_built": int(len(grooves("built"))),
        "rear_echo_s": round(WHEELBASE / V_DESIGN, 3),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(musical_physics(), indent=1))
