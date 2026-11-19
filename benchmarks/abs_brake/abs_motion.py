"""EP.06 ABS: one emergency stop, two cars (pure Python, no Blender).

Both cars start at the same speed, the driver brakes hard at t = 0 and steers the same lane change to miss a box on the road.
- "abs": the anti-lock system keeps every wheel rolling near the peak of the tyre's grip (slip cycles between SLIP_LO and SLIP_HI while the
  brake pressure is eased and reapplied about ABS_HZ times a second). A rolling tyre can still make side force, so the car follows the
  steering (kinematic bicycle model) while braking; braking and cornering share one friction circle.
- "locked": no ABS. The wheels lock within LOCK_TIME_S, a sliding tyre's friction acts against the direction of travel, so the car slides
  straight on whatever the front wheels point at, and hits the box.
Qualitative explanation model, not calibrated to any real car. No stopping-distance claim is made from it (the film does not say ABS stops shorter)."""
from __future__ import annotations

import math
from functools import lru_cache

G = 9.81
V0 = 22.2                 # m/s, 80 km/h
MU_PEAK = 0.90            # rolling tyre near peak slip (ABS)
MU_SLIDE = 0.75           # locked, sliding tyre
WHEELBASE = 2.31            # the CC0 sedan, measured by load_source_car
TYRE_R = 0.281
LOCK_TIME_S = 0.15        # the unlocked wheel spins down to zero in this time
ABS_HZ = 10.0
SLIP_LO, SLIP_HI = 0.05, 0.20
DT = 0.001
T_END = 4.0

# the lane change the ABS car drives (path along the road, reference point): x(y) = -SHIFT * smoothstep((y - Y0) / (Y1 - Y0)).
# The steering angle is DERIVED from this path's curvature (bicycle model) in the ABS run and the locked car's driver turns the wheel the same way at the same time.
SHIFT, PATH_Y0, PATH_Y1 = 2.0, 2.0, 28.0


def _path(y: float) -> tuple[float, float, float]:
    """(x, dx/dy, d2x/dy2) of the lane change."""
    L = PATH_Y1 - PATH_Y0
    u = (y - PATH_Y0) / L
    if u <= 0 or u >= 1:
        return (0.0 if u <= 0 else -SHIFT), 0.0, 0.0
    return -SHIFT * u * u * (3 - 2 * u), -SHIFT * 6 * u * (1 - u) / L, -SHIFT * (6 - 12 * u) / (L * L)


# the box on the road (centre of its near face), lane centre
BOX_Y = 28.0
BOX_HALF = (0.45, 0.45, 0.45)       # x, y, z half sizes (m): a large cardboard box
CAR_HALF_W = 0.90
CAR_NOSE = 1.93                     # nose ahead of the reference point (m)
CAR_TAIL = 2.07


def steer(t: float) -> float:
    """Front wheel angle (rad, + = left) the driver applies at time t: the one the ABS car needs for its lane change; the locked car's driver does the same."""
    rows, _ = _run("abs")
    return rows[min(len(rows) - 1, max(0, int(round(t / DT))))][7]


def abs_cycle(t: float) -> tuple[float, float]:
    """(brake pressure 0..1, wheel slip) of the ABS car: pressure builds until the wheel starts to lock, is eased, then reapplied."""
    if t < 0:
        return 0.0, 0.0
    if t < 0.08:
        return t / 0.08, SLIP_LO * t / 0.08
    ph = ((t - 0.08) * ABS_HZ) % 1.0
    if ph < 0.55:                       # pressure rising, slip growing toward the lock threshold
        u = ph / 0.55
        return 0.70 + 0.30 * u, SLIP_LO + (SLIP_HI - SLIP_LO) * u
    if ph < 0.70:                       # wheel about to lock: pressure eased quickly
        u = (ph - 0.55) / 0.15
        return 1.0 - 0.55 * u, SLIP_HI - (SLIP_HI - SLIP_LO) * u
    u = (ph - 0.70) / 0.30              # wheel spins back up, pressure reapplied
    return 0.45 + 0.25 * u, SLIP_LO


@lru_cache(maxsize=None)
def _run(variant: str) -> tuple:
    x = y = 0.0
    psi = 0.0                           # heading, rad (+ = left of +Y)
    vx, vy = 0.0, V0                    # world velocity
    wheel_angle = 0.0
    rows = []
    box = None
    n = int(round(T_END / DT))
    for i in range(n + 1):
        t = i * DT
        v = math.hypot(vx, vy)
        if variant == "abs":
            p, slip = abs_cycle(t)
            dxdy, d2 = _path(y)[1:]
            kappa = d2 / (1 + dxdy * dxdy) ** 1.5
            d = -math.atan(WHEELBASE * kappa)      # + = left; this path moves to -x (left of the +Y travel direction)
            if v > 0.05:
                ay = v * v * kappa
                if abs(ay) > MU_PEAK * G:
                    raise ValueError("lane change needs more grip than the tyres have")
                ax = math.sqrt(max(0.0, (MU_PEAK * G * 0.95) ** 2 - ay * ay)) * min(1.0, t / 0.08)
                v = max(0.0, v - ax * DT)
                psi = -math.atan(dxdy)
                vx, vy = -v * math.sin(psi), v * math.cos(psi)
            else:
                vx = vy = v = 0.0
            omega = v * (1 - slip) / TYRE_R
        else:
            d = steer(t)
            p = min(1.0, t / 0.08) if t >= 0 else 0.0
            slip = 1.0 if t >= LOCK_TIME_S else t / LOCK_TIME_S
            if v > 0.05:
                a = MU_SLIDE * G * min(1.0, t / 0.08)
                nv = max(0.0, v - a * DT)
                vx, vy = vx * nv / v, vy * nv / v
                v = nv
            else:
                vx = vy = v = 0.0
            omega = v * (1 - slip) / TYRE_R
        x += vx * DT
        y += vy * DT
        wheel_angle += omega * DT
        # box: hit when the locked car's nose reaches the near face while overlapping it sideways
        nose_y = y + CAR_NOSE * math.cos(psi)
        if box is None and nose_y >= BOX_Y and abs(x) < CAR_HALF_W + BOX_HALF[0]:
            box = {"t": t, "car_v": v}
        rows.append((t, x, y, psi, v, omega, wheel_angle, d, p, slip))
    return tuple(rows), box


def at(variant: str, t: float) -> dict:
    if t < 0:      # before the driver brakes: both cars cruise straight at V0 (used for the run-in that loops back to the first frame)
        return {"t": t, "x": 0.0, "y": V0 * t, "heading": 0.0, "speed": V0, "wheel_omega": V0 / TYRE_R, "wheel_angle": V0 * t / TYRE_R, "steer": 0.0,
                "pressure": 0.0, "slip": 0.0, "box": box_pose(variant, 0.0)}
    rows, box = _run(variant)
    i = min(len(rows) - 1, max(0, int(round(t / DT))))
    t_, x, y, psi, v, omega, wa, d, p, slip = rows[i]
    return {"t": t_, "x": x, "y": y, "heading": psi, "speed": v, "wheel_omega": omega, "wheel_angle": wa, "steer": d, "pressure": p, "slip": slip,
            "box": box_pose(variant, t)}


def box_pose(variant: str, t: float) -> dict:
    """The box: resting on the road, or (locked car only) knocked forward and tumbling after the hit. Ballistic with ground friction."""
    rest = {"x": 0.0, "y": BOX_Y + BOX_HALF[1], "z": BOX_HALF[2], "rx": 0.0, "hit": False}
    _, box = _run(variant)
    if box is None or t < box["t"]:
        return rest
    tau = t - box["t"]
    v0 = 1.25 * box["car_v"]
    vz0 = 2.2
    t_air = 2 * vz0 / G
    if tau <= t_air:
        y = rest["y"] + v0 * tau
        z = rest["z"] + vz0 * tau - 0.5 * G * tau * tau
        rx = 7.0 * tau
    else:
        y_land = rest["y"] + v0 * t_air
        ts = tau - t_air
        a = 0.6 * G
        stop = v0 / a
        ts = min(ts, stop)
        y = y_land + v0 * ts - 0.5 * a * ts * ts
        z = rest["z"]
        rx = 7.0 * t_air + 3.0 * ts
    return {"x": 0.0, "y": y, "z": z, "rx": rx, "hit": True}


def min_box_clearance(variant: str) -> float:
    """Smallest sideways gap (m) between the car body and the box while the car's length overlaps the box along the road; negative = contact."""
    rows, _ = _run(variant)
    gap = math.inf
    for (t, x, y, psi, *_rest) in rows:
        front, back = y + CAR_NOSE, y - CAR_TAIL
        if front >= BOX_Y and back <= BOX_Y + 2 * BOX_HALF[1]:
            gap = min(gap, abs(x) - CAR_HALF_W - BOX_HALF[0])
    return gap


def abs_physics() -> dict:
    """Gate: what the narration says is what the model does."""
    problems = []
    lk = [at("locked", t) for t in (0.3, 0.8, 1.2)]
    ab = [at("abs", t) for t in (0.3, 0.8, 1.2)]
    if any(r["wheel_omega"] != 0.0 for r in lk if r["speed"] > 0.5):
        problems.append("locked wheels still turn while the car moves")
    if any(abs(r["heading"]) > 1e-9 for r in lk):
        problems.append("the locked car changes heading although its tyres slide")
    if not all(r["wheel_omega"] > 0 for r in ab):
        problems.append("ABS wheels stop turning")
    if max(abs(at("abs", t)["heading"]) for t in (0.6, 0.9, 1.1)) < math.radians(2):
        problems.append("the ABS car does not follow the steering")
    _, hit_locked = _run("locked")
    _, hit_abs = _run("abs")
    if hit_locked is None:
        problems.append("the locked car never reaches the box")
    if hit_abs is not None or min_box_clearance("abs") < 0.2:
        problems.append(f"the ABS car does not clear the box (gap {min_box_clearance('abs'):.2f} m)")
    cycles = sum(1 for i in range(1, 1500) if abs_cycle(i * DT)[0] < abs_cycle((i - 1) * DT)[0] - 0.01 and abs_cycle((i - 1) * DT)[0] > 0.99)
    if cycles < 8:
        problems.append(f"ABS eases the brake only {cycles} times in 1.5 s")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "locked_hit_s": round(hit_locked["t"], 3) if hit_locked else None,
            "locked_speed_at_hit_kmh": round(hit_locked["car_v"] * 3.6, 1) if hit_locked else None, "abs_box_gap_m": round(min_box_clearance("abs"), 2),
            "abs_releases_in_1_5s": cycles}
