"""EP.26 rolling barrier (pure Python + numpy). Render-world coordinates: a road runs along +y; the barrier stands along its right edge
with the rollers' faces at x = X_FACE. A 1,500 kg sedan slides into it at 100 km/h (62 mph) and 25 degrees, the crash-test case
the film quotes. The car is a planar rigid body (position, heading, yaw) whose right side and corners are checked against the
barrier face every step:

- normal force: the foam rollers and the posts behind them give way (stiffness K_N per contact point, the rollers' foam damping C_N
  takes energy out: that is "the foam squashes to soak up the hit");
- along the barrier: a plain steel rail scrapes, so the car meets sliding friction MU_STEEL * N; on the rolling barrier each roller
  the car's side passes is spun up to the side's slip speed (rolling, no scraping): the drag is only what it takes to spin the rollers
  up (their rotational energy, "the spinning turns part of the crash into rotation") plus a little bearing friction MU_ROLL.
The gate compares the two barriers for the same crash: how much speed the car keeps, its exit angle and yaw, the peak sideways g,
and where the energy went. A roller spins down slowly after the car has passed. Simplified explanation model, not the test report
of any product.

After the barrier (for the picture only, not part of the gate): the driver reacts after REACT_S, steers back to the middle of the
lane and brakes; the path follows the heading again as the tyres grip. The foam and the posts spring back after the car has passed
(RELAX_S)."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

KMH = 1 / 3.6
MPH = 0.44704
G = 9.81
X_FACE = 4.05                           # the rollers' faces (the steel rail's face in the steel case)
M_CAR = 1500.0
CAR_FRONT, CAR_REAR, CAR_HALF_W = 1.926, 2.065, 0.804      # the CC0 sedan, measured (reference point to nose, to tail; half width)
I_CAR = M_CAR * ((CAR_FRONT + CAR_REAR) ** 2 + (2 * CAR_HALF_W) ** 2) / 12
V0 = 100 * KMH
ANGLE0 = math.radians(25.0)
K_N = 0.8e5                              # per contact point (N/m): foam and posts
C_HC = 0.25                              # foam damping (Hunt-Crossley): force K_N * pen * (1 + C_HC * closing speed); no jump at first touch
MU_STEEL = 0.35
MU_ROLL = 0.03
ROLL_R = 0.175                           # roller radius (m)
ROLL_H = 0.36
ROLL_M = 6.0                             # one EVA foam roller (kg)
ROLL_PITCH = 0.55                        # rollers along the barrier (m)
ROLL_STACK = 2                           # two rollers per post
SPIN_TAU = 2.5                           # spin-down time after the car has passed (s)
N_SIDE = 9                               # contact points along the car's right side, front corner to rear corner
DT = 5e-5
T_END = 1.6
REACT_S = 0.25                           # after the barrier: the driver's reaction time
STEER_TAU = 0.45                         # then steers back to the middle of the lane (LANE_X)
LANE_X = 1.8
GRIP_TAU = 0.15                          # the path follows the heading again as the tyres grip
BRAKE = 4.5                              # and the driver brakes (m/s^2)
T_AFTER = 7.0
TYRE_R = 0.281                           # the CC0 sedan's tyre radius (m)
SQ_MAX = 0.12                            # how far a roller's foam squashes at most (m); the rest the posts and rails give way
SPREAD_M = 2.0                           # the rails spread a post's give over about this length either side
RELAX_S = (0.25, 0.4)                    # the foam, then the posts, spring back over about this long after the car has passed


def _points():
    xs = np.full(N_SIDE, CAR_HALF_W)
    ys = np.linspace(CAR_FRONT, -CAR_REAR, N_SIDE)
    front_left = np.array([[-CAR_HALF_W, CAR_FRONT]])
    return np.vstack([np.stack([xs, ys], 1), front_left])


def start_pose() -> tuple[float, float, float]:
    """Reference point and heading at t = 0, when the front right corner first touches the barrier face."""
    psi = ANGLE0
    fr = np.array([CAR_HALF_W, CAR_FRONT])
    c, s = math.cos(psi), math.sin(psi)
    wx = c * fr[0] + s * fr[1]          # car frame (right, forward) -> world (x, y): forward = (sin psi, cos psi), right = (cos psi, -sin psi)
    wy = -s * fr[0] + c * fr[1]
    return X_FACE - wx, 0.0 - wy, psi


@lru_cache(maxsize=None)
def crash(barrier: str) -> dict:
    """Integrate the car against the 'roller' or 'steel' barrier from first contact; also the car's straight approach before it."""
    x, y, psi = start_pose()
    vx, vy, r = V0 * math.sin(psi), V0 * math.cos(psi), 0.0
    pts = _points()
    mu = MU_STEEL if barrier == "steel" else MU_ROLL
    rec = {k: [] for k in ("t", "x", "y", "psi", "vx", "vy", "r", "ay_lat", "defl", "n_total")}
    e_foam = e_fric = e_spin = 0.0
    spun = {}
    t = 0.0
    step = 0
    contact_end = None
    max_defl = 0.0
    while t < T_END:
        c, s = math.cos(psi), math.sin(psi)
        fx_tot = fy_tot = mz = 0.0
        n_tot = 0.0
        deepest = 0.0
        for px_c, py_c in pts:
            wx = x + c * px_c + s * py_c
            wy = y - s * px_c + c * py_c
            pen = wx - X_FACE
            if pen <= 0:
                continue
            vpx = vx + r * (-s * px_c + c * py_c) * 1.0
            vpy = vy - r * (c * px_c + s * py_c)
            n = K_N * pen * (1.0 + C_HC * vpx)
            if n <= 0:
                continue
            deepest = max(deepest, pen)
            n_tot += n
            e_foam += K_N * pen * C_HC * vpx * vpx * DT if vpx > 0 else 0.0
            slip = vpy
            ft = -mu * n * math.tanh(slip / 0.2)
            e_fric += abs(ft * slip) * DT
            if barrier == "roller" and abs(slip) > 0.05:
                k_roll = int(math.floor(wy / ROLL_PITCH))
                if k_roll not in spun:
                    e = 0.25 * ROLL_M * slip * slip * ROLL_STACK
                    spun[k_roll] = (t, abs(slip))
                    e_spin += e
            fx = -n
            fy = ft
            fx_tot += fx
            fy_tot += fy
            rx, ry = wx - x, wy - y
            mz += rx * fy - ry * fx
        if barrier == "roller":
            # spinning up the rollers the side passes takes energy: an even drag along the barrier while in contact
            if n_tot > 0:
                vy_side = vy
                drag = ROLL_STACK * ROLL_M * vy_side * vy_side / (4 * ROLL_PITCH)
                fy_tot += -math.copysign(drag, vy_side)
        ax, ay = fx_tot / M_CAR, fy_tot / M_CAR
        lat = -(ax * c - ay * s)
        vx += ax * DT
        vy += ay * DT
        r += (-mz / I_CAR) * DT
        x += vx * DT
        y += vy * DT
        psi += r * DT
        max_defl = max(max_defl, deepest)
        if n_tot == 0 and step > 200 and contact_end is None and max_defl > 0.01:
            contact_end = t
        if step % 20 == 0:
            for k_, v_ in (("t", t), ("x", x), ("y", y), ("psi", psi), ("vx", vx), ("vy", vy), ("r", r), ("ay_lat", lat), ("defl", deepest), ("n_total", n_tot)):
                rec[k_].append(v_)
        t += DT
        step += 1
    arr = {k: np.array(v) for k, v in rec.items()}
    speed = np.hypot(arr["vx"], arr["vy"])
    i_end = int(np.searchsorted(arr["t"], contact_end)) if contact_end else len(arr["t"]) - 1
    head = math.atan2(arr["vx"][i_end], arr["vy"][i_end])
    lat_g = np.convolve(np.abs(arr["ay_lat"]), np.ones(10) / 10, mode="same") / G           # 10 ms average, like the test reports
    ke0 = 0.5 * M_CAR * V0 ** 2
    ke1 = 0.5 * M_CAR * speed[i_end] ** 2 + 0.5 * I_CAR * arr["r"][i_end] ** 2
    return {"rec": arr, "contact_end": contact_end, "exit_speed": float(speed[i_end]), "exit_angle_deg": math.degrees(head),
            "exit_heading_deg": math.degrees(arr["psi"][i_end]), "yaw_rate_exit": float(arr["r"][i_end]), "peak_lat_g": float(lat_g.max()),
            "max_defl": max_defl, "e_foam": e_foam, "e_fric": e_fric, "e_spin": e_spin, "ke0": ke0, "ke1": ke1, "spun": spun}


def _approach(t: float) -> tuple[float, float, float]:
    x0, y0, psi = start_pose()
    return x0 + V0 * math.sin(psi) * t, y0 + V0 * math.cos(psi) * t, psi


@lru_cache(maxsize=None)
def after(barrier: str) -> dict:
    """The car after the barrier: from contact end + REACT_S the driver steers straight and brakes (picture only)."""
    c = crash(barrier)
    r = c["rec"]
    t = c["contact_end"] + REACT_S
    x, y, psi, vx, vy = (float(np.interp(t, r["t"], r[k])) for k in ("x", "y", "psi", "vx", "vy"))
    v, course = math.hypot(vx, vy), math.atan2(vx, vy)
    out = {k: [] for k in ("t", "x", "y", "psi", "speed")}
    dt = 0.002
    while t < T_AFTER:
        for k_, v_ in (("t", t), ("x", x), ("y", y), ("psi", psi), ("speed", v)):
            out[k_].append(v_)
        psi += (min(0.08, max(-0.08, 0.06 * (LANE_X - x))) - psi) * dt / STEER_TAU
        course += (psi - course) * dt / GRIP_TAU
        v = max(0.0, v - BRAKE * dt)
        x += v * math.sin(course) * dt
        y += v * math.cos(course) * dt
        t += dt
    return {k: np.array(v_) for k, v_ in out.items()}


def pose(t: float, barrier: str = "roller") -> dict:
    """Car reference point, heading and speed at time t (s from first contact; before it, the straight approach; after the barrier,
    the driver's recovery)."""
    if t <= 0:
        x, y, psi = _approach(t)
        return {"x": x, "y": y, "psi": psi, "speed": V0, "defl": 0.0, "in_contact": False}
    a = after(barrier)
    if t >= a["t"][0]:
        tt = min(t, a["t"][-1])
        f = {k: float(np.interp(tt, a["t"], a[k])) for k in ("x", "y", "psi", "speed")}
        return {**f, "defl": 0.0, "in_contact": False}
    r = crash(barrier)["rec"]
    f = {k: float(np.interp(t, r["t"], r[k])) for k in ("x", "y", "psi", "vx", "vy", "defl", "n_total")}
    return {"x": f["x"], "y": f["y"], "psi": f["psi"], "speed": math.hypot(f["vx"], f["vy"]), "defl": f["defl"], "in_contact": f["n_total"] > 0}


@lru_cache(maxsize=None)
def _distance_table(barrier: str):
    ts = np.arange(0.0, T_AFTER, 0.002)
    sp = np.array([pose(float(x), barrier)["speed"] for x in ts])
    d = np.concatenate([[0.0], np.cumsum(0.5 * (sp[1:] + sp[:-1]) * np.diff(ts))])
    return ts, d


def distance(t: float, barrier: str = "roller") -> float:
    """Path length (m) the car has driven since first contact (negative before it): turns the wheels."""
    if t <= 0:
        return V0 * t
    ts, d = _distance_table(barrier)
    return float(np.interp(t, ts, d)) + (0.0 if t <= ts[-1] else 0.0)


def wheel_angle(t: float, barrier: str = "roller") -> float:
    return distance(t, barrier) / TYRE_R


def side_pen(t: float, ys, barrier: str = "roller") -> np.ndarray:
    """How far the car's right side (and front corner) reaches past the barrier face at each y in ys (m, 0 where it does not)."""
    ys = np.asarray(ys, dtype=float)
    out = np.zeros_like(ys)
    if t <= 0:
        return out
    p = pose(t, barrier)
    if not p["in_contact"] and p["defl"] <= 0:
        return out
    c, s = math.cos(p["psi"]), math.sin(p["psi"])
    py = np.linspace(CAR_FRONT, -CAR_REAR, 61)
    wx = p["x"] + c * CAR_HALF_W + s * py
    wy = p["y"] - s * CAR_HALF_W + c * py
    fx = np.linspace(-CAR_HALF_W, CAR_HALF_W, 21)                      # the front face too, for the first instants
    wx = np.concatenate([wx, p["x"] + c * fx + s * CAR_FRONT])
    wy = np.concatenate([wy, p["y"] - s * fx + c * CAR_FRONT])
    pen = wx - X_FACE
    for i, y in enumerate(ys):
        m = (np.abs(wy - y) < ROLL_PITCH / 2) & (pen > 0)
        if m.any():
            out[i] = pen[m].max()
    return out


def barrier_give(t: float, ys, barrier: str = "roller") -> tuple[np.ndarray, np.ndarray]:
    """(foam squash, posts' give) at each roller y: the foam squashes up to SQ_MAX, the rest the posts and rails give way, spread
    along the rails over SPREAD_M either side so the barrier bows smoothly."""
    ys = np.asarray(ys, dtype=float)
    pen = side_pen(t, ys, barrier)
    excess = np.maximum(0.0, pen - (SQ_MAX if barrier == "roller" else 0.0))
    give = np.zeros_like(ys)
    for j in np.nonzero(excess)[0]:
        d = np.abs(ys - ys[j]) / SPREAD_M
        give = np.maximum(give, excess[j] * np.clip(1 - d * d, 0, 1) ** 2)
    squash = np.clip(pen - give, 0.0, SQ_MAX) if barrier == "roller" else np.zeros_like(ys)
    return squash, give


def barrier_state(t: float, ys, barrier: str = "roller") -> tuple[np.ndarray, np.ndarray]:
    """barrier_give with the spring-back: the foam and the posts recover over RELAX_S after the car has passed."""
    ys = np.asarray(ys, dtype=float)
    sq, gv = np.zeros_like(ys), np.zeros_like(ys)
    if t <= 0:
        return sq, gv
    for tau in np.linspace(0.0, 1.2, 25):
        if t - tau <= 0:
            break
        a, b = barrier_give(t - tau, ys, barrier)
        sq = np.maximum(sq, a * math.exp(-tau / RELAX_S[0]))
        gv = np.maximum(gv, b * math.exp(-tau / RELAX_S[1]))
    return sq, gv


@lru_cache(maxsize=None)
def _sparks() -> tuple:
    """Sparks where the car's side scrapes the steel rail (deterministic): (birth t, position, velocity, life)."""
    rng = np.random.default_rng(26)
    r = crash("steel")["rec"]
    out = []
    for i, t in enumerate(r["t"]):
        if r["n_total"][i] <= 0 or i % 4:
            continue
        c, s = math.cos(r["psi"][i]), math.sin(r["psi"][i])
        for py_c in np.linspace(CAR_FRONT, -CAR_REAR, 13):
            wx = r["x"][i] + c * CAR_HALF_W + s * py_c
            wy = r["y"][i] - s * CAR_HALF_W + c * py_c
            if wx - X_FACE <= 0.002 or rng.random() > 0.3:
                continue
            slip = r["vy"][i] - r["r"][i] * (c * CAR_HALF_W + s * py_c)
            pos = (wx - 0.03, wy, rng.uniform(0.42, 0.72))
            vel = (rng.uniform(-4.0, -0.5), slip * rng.uniform(0.35, 0.85), rng.uniform(0.3, 3.5))
            out.append((float(t), pos, vel, rng.uniform(0.12, 0.45)))
    return tuple(out)


def spark_points(t: float) -> list[tuple[np.ndarray, np.ndarray]]:
    pts = []
    for tb, p, vel, life in _sparks():
        tau = t - tb
        if 0 <= tau <= life:
            p, vel = np.array(p), np.array(vel)
            pos = p + vel * tau + np.array([0.0, 0.0, -0.5 * G * tau * tau])
            if pos[2] < 0.01:
                continue
            pts.append((pos, vel + np.array([0.0, 0.0, -G * tau])))
    return pts


def roller_spin(k: int, t: float, barrier: str = "roller") -> float:
    """Turned angle (rad) of the roller pair at index k (y from k*PITCH) at time t: spun up when the car's side passes, then spinning down."""
    spun = crash(barrier)["spun"]
    if k not in spun or t <= spun[k][0]:
        return 0.0
    t0, v = spun[k]
    w0 = v / ROLL_R
    tau = t - t0
    return w0 * SPIN_TAU * (1 - math.exp(-tau / SPIN_TAU))


def roller_squash(y_roll: float, t: float, barrier: str = "roller") -> float:
    """How far the roller at y_roll is pressed in (m): the car's side penetration at that y."""
    if t <= 0:
        return 0.0
    p = pose(t, barrier)
    c, s = math.cos(p["psi"]), math.sin(p["psi"])
    best = 0.0
    for py_c in np.linspace(CAR_FRONT, -CAR_REAR, 21):
        wx = p["x"] + c * CAR_HALF_W + s * py_c
        wy = p["y"] - s * CAR_HALF_W + c * py_c
        if abs(wy - y_roll) < ROLL_PITCH / 2:
            best = max(best, wx - X_FACE)
    return max(0.0, best)


def roller_physics() -> dict:
    """Gate: the same crash into both barriers; the rolling barrier keeps more of the car's speed, sends it back at a shallower angle
    with less yaw, and puts part of the crash into the rollers' spin, while the steel rail's scraping takes far more energy."""
    ro, st = crash("roller"), crash("steel")
    problems = []
    if ro["contact_end"] is None or st["contact_end"] is None:
        problems.append("the car never leaves a barrier")
    if not ro["exit_speed"] > st["exit_speed"]:
        problems.append("the rolling barrier does not keep more of the car's speed")
    if not ro["exit_speed"] / V0 > 0.75:
        problems.append(f"the car keeps only {ro['exit_speed'] / V0:.2f} of its speed on the rollers")
    if not ro["exit_angle_deg"] < math.degrees(ANGLE0) * 0.6:
        problems.append(f"the rollers do not steer the car back (exit at {ro['exit_angle_deg']:.1f} deg)")
    if not ro["e_spin"] > 0:
        problems.append("no energy goes into the rollers' spin")
    if not st["e_fric"] > 3 * ro["e_fric"] + ro["e_spin"]:
        problems.append("the steel rail does not scrape off much more energy")
    if not 0.1 < ro["max_defl"] < 0.8:
        problems.append(f"the barrier gives way {ro['max_defl']:.2f} m (expected 0.1-0.8)")
    return {
        "status": "FAIL" if problems else "PASS", "problems": problems, "impact_kmh": 100, "impact_mph": round(V0 / MPH, 1),
        "impact_angle_deg": 25.0, "car_kg": M_CAR,
        "roller": {"exit_speed_kmh": round(ro["exit_speed"] / KMH, 1), "kept_share": round(ro["exit_speed"] / V0, 3), "exit_angle_deg": round(ro["exit_angle_deg"], 1),
                   "yaw_deg_s": round(math.degrees(ro["yaw_rate_exit"]), 1), "peak_lat_g": round(ro["peak_lat_g"], 1), "deflection_m": round(ro["max_defl"], 3),
                   "foam_kj": round(ro["e_foam"] / 1e3, 1), "spin_kj": round(ro["e_spin"] / 1e3, 1), "friction_kj": round(ro["e_fric"] / 1e3, 1),
                   "rollers_spun": len(ro["spun"]), "contact_s": round(ro["contact_end"], 3) if ro["contact_end"] else None},
        "steel": {"exit_speed_kmh": round(st["exit_speed"] / KMH, 1), "kept_share": round(st["exit_speed"] / V0, 3), "exit_angle_deg": round(st["exit_angle_deg"], 1),
                  "yaw_deg_s": round(math.degrees(st["yaw_rate_exit"]), 1), "peak_lat_g": round(st["peak_lat_g"], 1), "deflection_m": round(st["max_defl"], 3),
                  "foam_kj": round(st["e_foam"] / 1e3, 1), "friction_kj": round(st["e_fric"] / 1e3, 1), "contact_s": round(st["contact_end"], 3) if st["contact_end"] else None},
        "impact_kj": round(0.5 * M_CAR * V0 ** 2 / 1e3, 1), "sideways_kj": round(0.5 * M_CAR * (V0 * math.sin(ANGLE0)) ** 2 / 1e3, 1),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(roller_physics(), indent=1))
