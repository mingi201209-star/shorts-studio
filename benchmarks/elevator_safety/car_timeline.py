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

ROWS = [
    ("A1-caught", 0.0, [(0.0, 0.10), (3.6, 0.86)], A1, A1_B, "car", {}, (1,)),
    ("A2-wedge", 3.6, [(0.0, 0.86), (0.9, 1.10)], A2, A2_B, "car", {}, (1,)),
]


def line1_seconds() -> float:
    w = json.loads(LINE1.read_text())["beats"][0]["words"]
    return w[-1]["end"] - w[0]["start"]


def opening_seconds() -> float:
    """Up to where line 2 will start: line 1 as recorded and the build's gap."""
    return round(line1_seconds() + GAP_S, 3)


def segments() -> list[dict]:
    t = [r[1] for r in ROWS] + [opening_seconds()]
    out = []
    for i, (label, _, knots, ca, cb, variant, flags, lines) in enumerate(ROWS):
        seg = {"label": label, "t0": t[i], "t1": t[i + 1], "knots": list(knots), "cam_a": ca, "cam_b": cb, "variant": variant,
               "flags": flags, "lines": lines}
        seg["sim0"], seg["sim1"] = sim_time(seg, t[i]), sim_time(seg, t[i + 1] - 1e-6)
        out.append(seg)
    return out


def frame_count() -> int:
    return int(opening_seconds() * FPS)


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
