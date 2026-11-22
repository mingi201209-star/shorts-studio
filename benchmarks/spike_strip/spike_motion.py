"""EP.19 tyre-deflation spike strip (pure Python + numpy). Render-world coordinates like EP.16: the highway runs along +y, the red car
in the left lane (x = X_LANE) at 60 mph. A strip lies across the lane at y = 0 .. STRIP_W with four rows of hollow steel quills.

As each left tyre rolls across, three quills punch into its tread, snap off their holders and stay in the rubber. Air leaves through
each quill's bore: choked (sonic) flow while the tyre holds more than 1.89 x atmospheric pressure, then subsonic orifice flow,
isothermal; the tyre is "flat" below 5 psi. Compare a blowout (EP.16): the carcass opens and the pressure is gone in hundredths of a
second. The driver lifts off and the car slows down in a straight line. Simplified explanation model, not a product specification."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

MPH = 0.44704
PSI = 6894.76
P_ATM = 101325.0
V0 = 60 * MPH
R = 0.281
RIM_R = 0.19
X_LANE = -1.85
WHEEL_OFFSET = (-0.72, 1.08)            # front-left wheel from the car reference (car frame), as in EP.16
REAR_OFFSET_Y = -1.62                   # rear axle from the car reference (checked by the renderer)
P0_GAUGE = 35.0 * PSI
TYRE_VOLUME = 0.030                     # m3 of air in a passenger tyre
BORE = 1.5e-3                           # quill bore diameter (m)
CD = 0.8
GAMMA, R_AIR, T_AIR = 1.4, 287.0, 300.0
QUILLS_PER_TYRE = 3
FLAT_GAUGE = 5.0 * PSI
STRIP_W = 0.50
ROWS_Y = (0.06, 0.19, 0.31, 0.44)
QUILL_DX = 0.12
STRIP_X = (X_LANE - 1.75, X_LANE + 1.75)
CAUGHT_ROWS = (0, 1, 3)
LIFT_OFF_T = 1.5                        # the driver keeps going for a moment, then lifts off
DECEL = 0.9                             # gentle slowing on soft tyres (m/s2)
VIS_GAIN = 2.0
LOAD = 1400 * 9.81 / 4
K0, KP = 30e3, 5e3 / PSI                # vertical stiffness N/m and N/m per Pa (EP.16's model)
BLOWOUT_TAU = 0.02                      # EP.16: pressure gone in a few hundredths of a second


def deflection(p_gauge: float) -> float:
    return LOAD / (K0 + KP * max(p_gauge, 0.0))


@lru_cache(maxsize=None)
def _deflate() -> tuple[np.ndarray, np.ndarray]:
    """Gauge pressure of one tyre against time since its quills went in (isothermal, QUILLS_PER_TYRE bores)."""
    a = QUILLS_PER_TYRE * math.pi * BORE ** 2 / 4
    c = math.sqrt(GAMMA * R_AIR * T_AIR)
    f = (2 / (GAMMA + 1)) ** ((GAMMA + 1) / (2 * (GAMMA - 1)))
    p, t, dt = P0_GAUGE + P_ATM, 0.0, 0.01
    ts, ps = [0.0], [P0_GAUGE]
    while t < 120.0:
        rho = p / (R_AIR * T_AIR)
        if p > 1.893 * P_ATM:
            mdot = CD * a * rho * c * f
        else:
            mdot = CD * a * math.sqrt(max(0.0, 2 * rho * (p - P_ATM)))
        m = rho * TYRE_VOLUME - mdot * dt
        p = max(P_ATM, m * R_AIR * T_AIR / TYRE_VOLUME)
        t += dt
        ts.append(t)
        ps.append(p - P_ATM)
    return np.array(ts), np.array(ps)


def gauge_after(tau: float) -> float:
    if tau < 0:
        return P0_GAUGE
    ts, ps = _deflate()
    return float(np.interp(tau, ts, ps))


def time_to_flat() -> float:
    ts, ps = _deflate()
    return float(ts[np.argmax(ps < FLAT_GAUGE)])


def car_speed(t: float) -> float:
    if t < LIFT_OFF_T:
        return V0
    return max(0.0, V0 - DECEL * (t - LIFT_OFF_T))


def car_y(t: float) -> float:
    """Car reference y; t = 0 when the front-left tyre's contact patch reaches the first quill row."""
    y0 = ROWS_Y[0] - WHEEL_OFFSET[1]
    if t < LIFT_OFF_T:
        return y0 + V0 * t
    tau = min(t - LIFT_OFF_T, V0 / DECEL)
    return y0 + V0 * LIFT_OFF_T + V0 * tau - 0.5 * DECEL * tau * tau


def stop_time() -> float:
    return LIFT_OFF_T + V0 / DECEL


def hit_time(row: int, axle: str) -> float:
    """When a tyre's contact patch reaches a quill row."""
    off = WHEEL_OFFSET[1] if axle == "front" else REAR_OFFSET_Y
    target = ROWS_Y[row] - off
    lo, hi = -5.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if car_y(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def quill_xs(row: int = 0) -> np.ndarray:
    """Quill positions across the lane; alternate rows are staggered by half a pitch so a tyre always meets one."""
    return np.arange(STRIP_X[0] + 0.06 + (QUILL_DX / 2 if row % 2 else 0.0), STRIP_X[1], QUILL_DX)


def captured() -> list[dict]:
    """The quills each left tyre takes: row, x on the strip, capture time, and the tyre's rolled distance then (sets the material
    angle the quill stays at)."""
    wx = X_LANE + WHEEL_OFFSET[0]
    out = []
    for axle in ("front", "rear"):
        for row in (CAUGHT_ROWS if axle == "front" else (0, 2, 3)):
            xs = quill_xs(row)
            x = float(xs[np.argmin(np.abs(xs - wx))])
            th = hit_time(row, axle)
            out.append({"axle": axle, "row": row, "x": x, "w": x - wx, "t": th, "dist": car_y(th)})
    return out


def tyre_gauge(t: float, axle: str) -> float:
    first = min(c["t"] for c in captured() if c["axle"] == axle)
    return gauge_after(t - first)


def squash(t: float, axle: str = "front") -> float:
    p = tyre_gauge(t, axle)
    flat = R - RIM_R - 0.025
    s = VIS_GAIN * deflection(p)
    if p < FLAT_GAUGE:
        s = s + (flat - s) * (1 - p / FLAT_GAUGE)
    return min(s, flat)


def vent_speed(t: float, axle: str) -> float:
    """Speed of the air jet out of a quill (m/s): sonic while choked, then from Bernoulli."""
    p = tyre_gauge(t, axle)
    if t < min(c["t"] for c in captured() if c["axle"] == axle) or p <= 0:
        return 0.0
    if p + P_ATM > 1.893 * P_ATM:
        return math.sqrt(GAMMA * R_AIR * T_AIR)
    rho = (p + P_ATM) / (R_AIR * T_AIR)
    return math.sqrt(2 * p / rho)


def pose_for_angle(target_deg: float, near_t: float) -> float:
    """A time just after near_t when the front tyre's middle quill points at target_deg (0 = straight down, 90 = forward), so a
    slow shot can open with the quills facing the camera."""
    mid = [c for c in captured() if c["axle"] == "front"][1]
    a_mat = mid["dist"] / R
    best, best_err = near_t, 9.0
    for k in range(4000):
        t = near_t + k * 0.00005
        a = math.degrees((a_mat - car_y(t) / R) % (2 * math.pi))
        err = abs((a - target_deg + 180) % 360 - 180)
        if err < best_err:
            best, best_err = t, err
    return best


def state(t: float) -> dict:
    return {"t": t, "x": X_LANE, "y": car_y(t), "psi": 0.0, "dist": car_y(t), "speed": car_speed(t),
            "gauge_front_psi": tyre_gauge(t, "front") / PSI, "gauge_rear_psi": tyre_gauge(t, "rear") / PSI,
            "squash": squash(t, "front"), "squash_rear": squash(t, "rear")}


def spike_physics() -> dict:
    problems = []
    tf = time_to_flat()
    if not 20 <= tf <= 40:
        problems.append(f"flat after {tf:.0f} s (narration: about half a minute)")
    if tf / BLOWOUT_TAU < 500:
        problems.append("deflation is not far slower than a blowout")
    caps = captured()
    if len(caps) != 2 * QUILLS_PER_TYRE or any(abs(c["w"]) > 0.09 for c in caps):
        problems.append("a captured quill is not under the tyre's tread")
    if any(c["t"] < 0 for c in caps if c["axle"] == "front") or abs(min(c["t"] for c in caps)) > 1e-6:
        problems.append("the first quill does not go in at t = 0")
    v_at_flat = car_speed(tf + min(c["t"] for c in caps))
    st = stop_time()
    if st > tf + 10:
        problems.append(f"the car is still rolling {st - tf:.0f} s after the tyres are flat")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "time_to_flat_s": round(tf, 1),
            "slower_than_blowout_x": round(tf / BLOWOUT_TAU), "stop_s": round(st, 1), "speed_at_flat_mph": round(v_at_flat / MPH, 1),
            "captured": [(c["axle"], c["row"], round(c["w"], 3), round(c["t"], 4)) for c in caps]}


if __name__ == "__main__":
    import json
    print(json.dumps(spike_physics(), indent=1))
