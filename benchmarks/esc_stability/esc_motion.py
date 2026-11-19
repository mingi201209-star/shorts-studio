"""EP.07 ESC (electronic stability control): one swerve on a wet road, two cars (pure Python, no Blender).

Single-track ("bicycle") model with saturating tyre side forces on a wet road. The rear tyres have a little less grip than the fronts
(e.g. wet road, worn rears), so a hard swerve makes the rear slide first: oversteer.
- "off": no stability control. Once the rear saturates the yaw rate runs away and the car spins.
- "esc": a yaw-rate sensor and a steering-angle sensor feed a reference yaw rate (what the driver asks for). When the car turns faster
  than that (oversteer), the system brakes the OUTSIDE FRONT wheel; its braking force acts at half the track width from the centre line and
  makes a yaw moment that turns the car back. Brake force is capped by that tyre's grip.
Both drivers steer the same way at the same time. Qualitative explanation model, not calibrated to any real car."""
from __future__ import annotations

import math
from functools import lru_cache

G = 9.81
M = 1400.0
IZ = 2300.0
WHEELBASE = 2.31              # the CC0 sedan, measured by load_source_car
A = 1.10                      # centre of mass to front axle
B = WHEELBASE - A             # to rear axle
TRACK = 1.42                  # wheel centre to wheel centre (2 x 0.709)
MU_F, MU_R = 0.62, 0.52       # wet road; the rears give up first
C_F, C_R = 70000.0, 70000.0   # cornering stiffness, N/rad (axle)
V0 = 22.2                     # 80 km/h
DT = 0.0005
T_END = 4.5
TYRE_R = 0.281
CAR_NOSE, CAR_TAIL, CAR_HALF_W = 1.93, 2.07, 0.90

BOX_Y = 36.0                  # in the right lane: both drivers swerve into the left lane to pass it
BOX_HALF = (0.45, 0.45, 0.45)

# driver: swerve left around the box, then steer back right (the same in both cars)
STEER = [(0.00, 0.0), (0.25, 0.0), (0.55, math.radians(4.0)), (0.95, math.radians(4.0)), (1.35, math.radians(-4.0)),
         (1.85, math.radians(-4.0)), (2.30, 0.0), (T_END, 0.0)]

ESC_THRESHOLD = 0.06          # rad/s above the reference before the system acts
ESC_GAIN = 30000.0            # N per rad/s of excess yaw rate
ESC_RAMP_S = 0.08             # brake pressure builds in this time


def steer(t: float) -> float:
    if t <= STEER[0][0]:
        return STEER[0][1]
    for (t0, d0), (t1, d1) in zip(STEER, STEER[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            return d0 + (d1 - d0) * u
    return STEER[-1][1]


def _fy(alpha: float, c: float, mu: float, fz: float) -> float:
    """Side force: linear for small slip angles, saturating at mu * Fz."""
    cap = mu * fz
    return cap * math.tanh(c * alpha / cap)


def reference_yaw_rate(vx: float, delta: float) -> float:
    """What the driver asks for: the neutral-steer yaw rate, limited by what the road can give."""
    if vx < 1.0:
        return 0.0
    r = vx * delta / WHEELBASE
    lim = 0.85 * MU_F * G / vx
    return max(-lim, min(lim, r))


@lru_cache(maxsize=None)
def _run(variant: str) -> tuple:
    fzf, fzr = M * G * B / WHEELBASE, M * G * A / WHEELBASE
    x = y = psi = 0.0
    vx, vy, r = V0, 0.0, 0.0                      # body-frame velocities, yaw rate (+ = turning left)
    esc_force = 0.0
    wheel_angle = 0.0
    rows = []
    n = int(round(T_END / DT))
    for i in range(n + 1):
        t = i * DT
        d = steer(t)
        u = max(vx, 0.5)
        af = d - math.atan2(vy + A * r, u)
        ar = -math.atan2(vy - B * r, u)
        fyf = _fy(af, C_F, MU_F, fzf)
        fyr = _fy(ar, C_R, MU_R, fzr)
        want = 0.0
        side = 0
        if variant == "esc":
            excess = abs(r) - abs(reference_yaw_rate(vx, d)) if abs(r) > 0.02 else 0.0
            if excess > ESC_THRESHOLD and vx > 2.0:
                want = min(ESC_GAIN * (excess - ESC_THRESHOLD), 0.8 * MU_F * fzf / 2)
                side = 1 if r > 0 else -1            # yawing left: outside front = right wheel
        esc_force += (want - esc_force) * min(1.0, DT / ESC_RAMP_S)
        # braking the outside front wheel: force backwards at +-TRACK/2 -> yaw moment opposing the rotation
        side_now = side if side else (1 if r > 0 else -1)
        mz_esc = -side_now * esc_force * TRACK / 2 if esc_force > 1.0 else 0.0
        fx_brake = esc_force
        drag = 0.015 * M * G + 0.4 * u * u           # rolling resistance + air, the drivers do not brake
        ax = (-fx_brake - drag - fyf * math.sin(d)) / M + vy * r
        ay = (fyf * math.cos(d) + fyr) / M - vx * r
        rr = (A * fyf * math.cos(d) - B * fyr + mz_esc) / IZ
        vx = max(0.0, vx + ax * DT)
        vy += ay * DT
        r += rr * DT
        if vx < 0.3:
            vx, vy, r = 0.0, vy * 0.98, r * 0.98
        psi += r * DT
        x += (vx * -math.sin(psi) - vy * math.cos(psi)) * DT   # +Y forward, +x to the right; body lateral +vy points left
        y += (vx * math.cos(psi) - vy * math.sin(psi)) * DT
        wheel_angle += vx / TYRE_R * DT
        speed = math.hypot(vx, vy)
        slide_r = abs(ar) > 0.10
        rows.append((t, x, y, psi, speed, r, d, wheel_angle, esc_force, side_now if esc_force > 1.0 else 0, abs(ar), abs(af), slide_r))
    return tuple(rows)


def at(variant: str, t: float) -> dict:
    if t < 0:
        return {"t": t, "x": 0.0, "y": V0 * t, "heading": 0.0, "speed": V0, "yaw_rate": 0.0, "steer": 0.0, "wheel_angle": V0 * t / TYRE_R,
                "esc_force": 0.0, "esc_side": 0, "rear_slip": 0.0, "front_slip": 0.0, "rear_sliding": False, "ref_yaw_rate": 0.0}
    rows = _run(variant)
    i = min(len(rows) - 1, max(0, int(round(t / DT))))
    t_, x, y, psi, sp, r, d, wa, f, side, sr, sf, sl = rows[i]
    return {"t": t_, "x": x, "y": y, "heading": psi, "speed": sp, "yaw_rate": r, "steer": d, "wheel_angle": wa, "esc_force": f, "esc_side": side,
            "rear_slip": sr, "front_slip": sf, "rear_sliding": sl, "ref_yaw_rate": reference_yaw_rate(sp, d)}


def trail(variant: str, t: float, step: float = 0.02) -> list[tuple[float, float, float]]:
    """(time, x, y) of the car while its rear tyres were sliding, up to t: for the skid marks."""
    out = []
    k = 0.0
    while k <= t:
        s = at(variant, k)
        if s["rear_sliding"]:
            out.append((k, s["x"], s["y"], s["heading"]))
        k += step
    return out


def esc_physics() -> dict:
    """Gate: what the narration says is what the model does."""
    problems = []
    off_max = max(abs(at("off", i / 50)["heading"]) for i in range(int(T_END * 50)))
    esc_max = max(abs(at("esc", i / 50)["heading"]) for i in range(int(T_END * 50)))
    if off_max < math.radians(90):
        problems.append(f"the car without ESC does not spin (max heading {math.degrees(off_max):.0f} deg)")
    if esc_max > math.radians(25):
        problems.append(f"the ESC car does not stay pointed down the road (max heading {math.degrees(esc_max):.0f} deg)")
    if all(at("esc", i / 50)["esc_force"] < 100 for i in range(int(T_END * 50))):
        problems.append("ESC never brakes a wheel")
    first_slide = next((i / 100 for i in range(int(T_END * 100)) if at("off", i / 100)["rear_sliding"]), None)
    first_esc = next((i / 100 for i in range(int(T_END * 100)) if at("esc", i / 100)["esc_force"] > 300), None)
    if first_slide is None:
        problems.append("the rear tyres of the car without ESC never slide")
    for i in range(int(T_END * 50)):                  # the braked wheel is always the outside front: opposite side to the turn
        s = at("esc", i / 50)
        if s["esc_force"] > 300 and s["esc_side"] * s["yaw_rate"] < 0:
            problems.append(f"at {i / 50:.2f}s ESC brakes the inside wheel")
            break
    for i in range(int(2.5 * 50)):                    # both drivers steer the same
        if at("esc", i / 50)["steer"] != at("off", i / 50)["steer"]:
            problems.append("the drivers steer differently")
            break
    spin_t = next((i / 100 for i in range(int(T_END * 100)) if abs(at("off", i / 100)["heading"]) > math.radians(60)), None)
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "off_max_heading_deg": round(math.degrees(off_max)),
            "esc_max_heading_deg": round(math.degrees(esc_max)), "off_rear_slides_from_s": first_slide, "esc_brakes_from_s": first_esc,
            "off_past_60deg_s": spin_t}
