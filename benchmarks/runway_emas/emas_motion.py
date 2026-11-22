"""EP.22 runway-end arrestor bed (EMAS) (pure Python + numpy). Render-world coordinates: the runway runs along +y and ends at y = 0;
after a short setback a bed of crushable cellular-concrete blocks starts at Y_BED and runs BED_L metres, as wide as the runway. The bed
is shallow at its leading edge and gets deeper further in.

A 737-class jet (65 t) leaves the end of the runway at 70 knots (the standard design exit speed, about 80 mph). Simulated time t = 0
when the main gear reaches the bed. The nose gear enters first (it is WHEELBASE ahead). Each gear's tyres sink into the blocks by a
share of the local bed depth and crush them as they roll; crushing takes a force roughly proportional to how deep the tyres sink, so
the bed slows the jet more and more as it gets deeper; the pilots' braking adds a little. The jet stops well inside the bed, the nose
pitched down a little. Simplified explanation model, not an EMAS design calculation."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

KT = 0.514444
MPH = 0.44704
G = 9.81
M = 65000.0
V0 = 70 * KT
Y_BED = 12.0                               # setback from the end of the runway
BED_L = 140.0
BED_W = 46.0                               # 150 ft
DEPTH0, DEPTH1, DEPTH_RAMP = 0.25, 0.60, 45.0
LEAD_IN = 2.5                              # the bed's front edge ramps up over this length
SINK = 0.72                                # tyres sink this share of the bed depth
WHEELBASE = 15.6
MAIN_X = 2.86                              # main gears at x = +-MAIN_X
NOSE_SHARE = 0.08
K_CRUSH = 4.8e5                            # crushing drag per metre of sink for the whole gear set (N/m)
A_BRAKE = 0.10 * G
BLOCK = 1.22                               # 4 ft blocks


def bed_depth(y: float) -> float:
    if y < Y_BED or y > Y_BED + BED_L:
        return 0.0
    u = y - Y_BED
    d = DEPTH0 + (DEPTH1 - DEPTH0) * min(1.0, u / DEPTH_RAMP)
    return d * min(1.0, u / LEAD_IN)


def sink(y: float) -> float:
    return SINK * bed_depth(y)


def drag(y_main: float) -> float:
    """Crushing drag on the jet (N) with the main gear at y_main."""
    s_m, s_n = sink(y_main), sink(y_main + WHEELBASE)
    return K_CRUSH * ((1 - NOSE_SHARE) * s_m + NOSE_SHARE * s_n) / 0.5


@lru_cache(maxsize=None)
def _run() -> dict:
    dt = 1e-3
    t = -(Y_BED + 30.0) / V0                       # start 30 m before the end of the runway
    y = -30.0
    v = V0
    ts, ys, vs, w_bed, w_brake = [], [], [], 0.0, 0.0
    while v > 0 and t < 20:
        f = drag(y)
        a = -(f / M + A_BRAKE)
        dv = a * dt
        step = (v + 0.5 * dv) * dt if v + dv > 0 else v * v / (2 * -a)
        w_bed += f * step
        w_brake += M * A_BRAKE * step
        if v + dv <= 0:
            t += v / -a
            y += step
            v = 0.0
        else:
            y += step
            v += dv
            t += dt
        ts.append(t)
        ys.append(y)
        vs.append(v)
    return {"t": np.array(ts), "y": np.array(ys), "v": np.array(vs), "stop_t": t, "stop_y": y, "w_bed": w_bed, "w_brake": w_brake,
            "t_start": -(Y_BED + 30.0) / V0}


def main_y(t: float) -> float:
    """Main-gear position along the runway (y)."""
    c = _run()
    if t <= c["t_start"]:
        return -30.0 + V0 * (t - c["t_start"])
    if t >= c["stop_t"]:
        return float(c["stop_y"])
    return float(np.interp(t, c["t"], c["y"]))


def speed(t: float) -> float:
    c = _run()
    if t <= c["t_start"]:
        return V0
    if t >= c["stop_t"]:
        return 0.0
    return float(np.interp(t, c["t"], c["v"]))


def stop_time() -> float:
    return _run()["stop_t"]


def stop_distance() -> float:
    """How far the main gear rolls into the bed."""
    return _run()["stop_y"] - Y_BED


def time_at(y: float) -> float | None:
    """When the main gear reaches y (None if it never does)."""
    c = _run()
    if y > c["stop_y"]:
        return None
    if y <= c["y"][0]:
        return c["t_start"] - (c["y"][0] - y) / V0
    return float(np.interp(y, c["y"], c["t"]))


def pitch(t: float) -> float:
    """Nose-down pitch (rad) from the nose gear sinking deeper than the mains."""
    y = main_y(t)
    return math.atan2(sink(y + WHEELBASE) - sink(y), WHEELBASE)


def crushed_to(y_track: float, t: float, gear: str) -> float:
    """How deep the bed at y_track is crushed by a gear by time t (0 if the gear has not reached it)."""
    y = main_y(t) + (WHEELBASE if gear == "nose" else 0.0)
    return sink(y_track) if y_track <= y else 0.0


def state(t: float, variant: str = "overrun") -> dict:
    y = main_y(t)
    return {"t": t, "variant": variant, "y": y, "speed": speed(t), "sink_main": sink(y), "sink_nose": sink(y + WHEELBASE), "pitch": pitch(t),
            "decel_g": (drag(y) / M + A_BRAKE) / G if speed(t) > 0 else 0.0}


def emas_physics() -> dict:
    problems = []
    if abs(V0 / MPH - 80.5) > 0.6:
        problems.append("70 knots is not about 80 mph")
    c = _run()
    ke = 0.5 * M * V0 * V0
    w = c["w_bed"] + c["w_brake"]
    if abs(w - ke) / ke > 0.01:
        problems.append(f"energy does not balance ({w / 1e6:.2f} vs {ke / 1e6:.2f} MJ)")
    d = stop_distance()
    if not 50 < d < BED_L - 15:
        problems.append(f"the jet stops {d:.0f} m into a {BED_L:.0f} m bed")
    peak = max(drag(y) / M + A_BRAKE for y in np.linspace(Y_BED, c["stop_y"], 400)) / G
    if peak > 1.0:
        problems.append(f"peak deceleration {peak:.2f} g is not a gentle stop")
    share = c["w_bed"] / w
    if share < 0.75:
        problems.append(f"the bed takes only {share:.0%} of the energy")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "exit_mph": round(V0 / MPH, 1), "stop_in_bed_m": round(d, 1),
            "stop_in_bed_ft": round(d / 0.3048), "stop_s": round(c["stop_t"], 2), "peak_g": round(peak, 2), "bed_share": round(share, 3),
            "kinetic_MJ": round(ke / 1e6, 1), "max_sink_m": round(SINK * DEPTH1, 2)}


if __name__ == "__main__":
    import json
    print(json.dumps(emas_physics(), indent=1))
