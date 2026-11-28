"""EP.37 film timeline (pure data). For now only the opening, rendered first so it can be EP.36's teaser (owner, 2026-11-28: the
teaser comes with the first build; playbook section 10): its first line is recorded and frozen (examples/episodes/ep37-audio/line1),
and its opening rows are fixed; the rest of the film is added when EP.37 is made, without touching these rows.

Frame 1 is a falling elevator full of people already being caught by its safety gear: the shaft cut away on one side, the car
behind glass with Bumper and two passengers, the wedges biting the guide rails in a shower of sparks, the broken hoist rope ends
whipping above. Held until 3.6 s (line 1 runs about 4.4 s), then a close look at a wedge on the rail. Simulated time t is seconds
after the hoist ropes break (car_motion)."""
from __future__ import annotations

import json
from pathlib import Path

FPS = 24
LINE1 = Path(__file__).resolve().parents[2] / "examples/episodes/ep37-audio/line1/capture.json"
GAP_S = 0.12                                          # the narration build's gap between lines


def cam(loc, target, lens, fstop=11.0, rel="car"):
    """rel "car": z measured from the car's floor (a tracking shot); "world": as given."""
    return {"rel": rel, "loc": tuple(loc), "target": tuple(target), "lens": lens, "fstop": fstop}


A1 = cam((3.05, -1.05, 0.75), (0.5, 0.1, 0.75), 19.0)                 # the cutaway: the car behind glass, the gear on the right rail
A1_B = cam((2.95, -1.0, 0.72), (0.5, 0.1, 0.75), 19.0)
A2 = cam((2.15, -0.55, -0.2), (1.42, 0.0, -0.45), 26.0)               # close: the wedge on the rail, sparks dying
A2_B = cam((2.05, -0.5, -0.22), (1.42, 0.0, -0.45), 26.0)

# the rest of the film (lines 2-8), added after the opening without touching its rows
B1 = cam((3.1, -1.3, 2.3 + 0.4), (0.0, 0.0, 2.3 + 1.9), 20.0)           # from the cutaway at the car's top: the hitch, the five ropes up
B1_B = cam((2.9, -1.2, 2.3 + 0.5), (0.0, 0.0, 2.3 + 2.0), 20.0)
B2 = cam((0.95, -0.95, 2.3 + 0.95), (-0.05, 0.0, 2.3 + 4.5), 20.0)       # up the ropes from the hitch; one rope lit: it alone holds the car
B2_B = cam((0.9, -0.9, 2.3 + 0.9), (-0.05, 0.0, 2.3 + 4.8), 20.0)
C1 = cam((2.8, -1.2, 2.3 + 0.6), (0.0, 0.0, 2.3 + 1.3), 20.0)           # the ropes snap above the car
C1_B = cam((2.6, -1.1, 2.3 + 0.6), (0.0, 0.0, 2.3 + 1.2), 20.0)
C2 = cam((1.9, -1.1, 0.2), (-0.9, 0.3, 1.6), 22.0)                       # x-ray from the cutaway: the governor rope lit beside the car
C2_B = cam((1.7, -1.0, 0.2), (-0.9, 0.3, 1.7), 22.0)
D1 = cam((1.9, -2.0, 1.75), (0.0, 0.0, 0.95), 24.0, rel="gov")           # the machine room: the governor on its stand, the rope loop
D1_B = cam((1.7, -1.8, 1.65), (0.0, 0.0, 1.0), 24.0, rel="gov")
D2 = cam((0.95, -0.55, 1.45), (0.04, 0.0, 1.15), 30.0, rel="gov")        # close: the flyweights swing out, the pawl locks the sheave
D2_B = cam((0.85, -0.5, 1.4), (0.04, 0.0, 1.15), 30.0, rel="gov")
E1 = cam((0.4, -1.15, -0.55), (-0.85, 0.2, -0.35), 22.0)                  # x-ray under the car: the locked rope pulls the lever up
E1_B = cam((0.3, -1.05, -0.5), (-0.85, 0.2, -0.35), 22.0)
E2 = cam((0.95, -0.6, -1.15), (1.42, 0.0, -0.45), 24.0)                   # from below: the wedge jammed on the rail, sparks
E2_B = cam((1.0, -0.55, -1.1), (1.42, 0.0, -0.45), 24.0)
F = cam((3.9, -1.9, 0.2), (0.6, 0.0, 0.2), 22.0, rel="world")           # the drop laid out in yellow beside the car
F_B = cam((3.7, -1.8, 0.15), (0.6, 0.0, 0.15), 22.0, rel="world")
G = cam((2.1, 0.1, 1.55), (0.35, 0.25, 1.45), 30.0)                     # through the glass: Bumper waves
G_B = cam((1.95, 0.12, 1.55), (0.35, 0.25, 1.48), 30.0)
H = cam((3.0, -9.8, 1.9), (0.0, 0.0, 4.6), 24.0, rel="otis")            # 1854: from the crowd, the open platform on its tower
H_B = cam((2.7, -9.2, 1.9), (0.0, 0.0, 4.4), 24.0, rel="otis")

ROWS = [
    ("A1-caught", 0.0, [(0.0, 0.10), (3.6, 0.86)], A1, A1_B, "car", {}, (1,)),
    ("A2-wedge", 3.6, [(0.0, 0.86), (0.9, 1.10)], A2, A2_B, "car", {}, (1,)),
    ("B1-ropes", 4.70, [(0.0, -6.0), (1.58, -4.42)], B1, B1_B, "car", {}, (2,)),
    ("B2-one-rope", 6.276, [(0.0, -4.4), (2.66, -1.8)], B2, B2_B, "car", {"glow_rope": True}, (2,)),
    ("C1-snap", 8.93, [(0.0, -0.30), (1.66, 0.02)], C1, C1_B, "car", {}, (3,)),
    ("C2-governor-rope", 10.587, [(0.0, 0.02), (1.74, 0.05)], C2, C2_B, "car", {"xray": True, "reveal": True}, (3,)),
    ("D1-machine-room", 12.33, [(0.0, -2.44), (2.44, 0.0)], D1, D1_B, "gov", {}, (4,)),
    ("D2-flyweights", 14.771, [(0.0, -0.06), (1.6, 0.031), (3.06, 0.06)], D2, D2_B, "gov", {}, (4,)),
    ("E1-lever", 17.77, [(0.0, 0.02), (2.31, 0.115)], E1, E1_B, "car", {"xray": True}, (5,)),
    ("E2-wedges", 20.077, [(0.0, 0.11), (2.8, 0.42)], E2, E2_B, "car", {}, (5,)),
    ("F-drop", 22.82, [(0.0, 0.30), (4.22, 0.95)], F, F_B, "car", {"marker": True}, (6,)),
    ("G-thats-me", 27.04, [(0.0, 1.0), (2.03, 3.0)], G, G_B, "car", {"wave": True}, (7,)),
    ("H-otis", 29.07, [(0.0, -2.6), (3.913, 0.8)], H, H_B, "otis", {}, (8,)),
]
AUDIO = Path(__file__).resolve().parents[2] / "examples/episodes/ep37-audio/audio-validation.json"
OPENING_ROWS = 2


def line1_seconds() -> float:
    w = json.loads(LINE1.read_text())["beats"][0]["words"]
    return w[-1]["end"] - w[0]["start"]


def opening_seconds() -> float:
    """Up to where line 2 will start: line 1 as recorded and the build's gap."""
    return round(line1_seconds() + GAP_S, 3)


def total_seconds() -> float:
    return json.loads(AUDIO.read_text())["seconds"]


def segments(opening_only: bool = False) -> list[dict]:
    rows = ROWS[:OPENING_ROWS] if opening_only else ROWS
    t = [r[1] for r in rows] + [opening_seconds() if opening_only else total_seconds()]
    out = []
    for i, (label, _, knots, ca, cb, variant, flags, lines) in enumerate(rows):
        seg = {"label": label, "t0": t[i], "t1": t[i + 1], "knots": list(knots), "cam_a": ca, "cam_b": cb, "variant": variant,
               "flags": flags, "lines": lines}
        seg["sim0"], seg["sim1"] = sim_time(seg, t[i]), sim_time(seg, t[i + 1] - 1e-6)
        out.append(seg)
    return out


def frame_count() -> int:
    return int(round(total_seconds() * FPS))


def sim_time(seg: dict, film_t: float) -> float:
    tau = film_t - seg["t0"]
    k = seg["knots"]
    if tau <= k[0][0]:
        return k[0][1]
    for (a, sa), (b, sb) in zip(k[:-1], k[1:]):
        if tau <= b:
            return sa + (sb - sa) * (tau - a) / (b - a)
    (a, sa), (b, sb) = k[-2], k[-1]
    return sb + (sb - sa) / (b - a) * (tau - b)


def _smooth(u):
    return 0.5 * u + 0.5 * u * u * (3 - 2 * u)


def frame_state(f: int, segs: list[dict]) -> dict:
    t = f / FPS
    seg = next((s for s in segs if s["t0"] <= t < s["t1"]), segs[-1])
    u = min(1.0, max(0.0, (t - seg["t0"]) / (seg["t1"] - seg["t0"])))
    uc = _smooth(u)
    a, b = seg["cam_a"], seg["cam_b"]
    c = {"rel": a["rel"], "loc": tuple(x + (y - x) * uc for x, y in zip(a["loc"], b["loc"])),
         "target": tuple(x + (y - x) * uc for x, y in zip(a["target"], b["target"])), "lens": a["lens"] + (b["lens"] - a["lens"]) * uc,
         "fstop": a.get("fstop", 8.0)}
    st = {"frame": f, "film_t": t, "segment": seg["label"], "t": sim_time(seg, t), "variant": seg["variant"], "cam": c, "u": u}
    st.update(seg["flags"])
    return st
