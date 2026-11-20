"""EP.09 hydroplaning: same road, same puddle, same speed, two tread depths (pure Python, no Blender).

The road runs straight, then bends gently left (radius R). A puddle covers the lane at the start of the bend. Both drivers steer the same way
to follow the bend (a simple look-ahead driver: aim at a point on the lane centre ahead, steering limited). The car is a single-track
("bicycle") model with saturating tyre side forces.
Water: on dry or wet road the tyres grip (MU_WET in the puddle). Above an onset speed the water cannot leave the contact patch fast enough,
a wedge of water lifts the tyre and its side grip collapses ("hydroplaning"). The onset follows the rule of thumb found in NASA tests
(Horne): v [mph] ~ 9 * sqrt(tyre pressure [psi]) for a tyre that cannot clear the water. Deep, open grooves clear water and push the onset
up; worn grooves lower it. ONSET_FACTOR is a modelling choice per tread, stated here; the film says "worn tyres float sooner", not a number.
- "new": 8 mm grooves; onset well above the test speed, so it keeps (wet) grip.
- "worn": 1.6 mm grooves; onset below the test speed, so in the puddle the front tyres float and the car runs wide off the bend.
Qualitative explanation model, not calibrated to any real tyre or car."""
from __future__ import annotations

import math
from functools import lru_cache

G = 9.81
M, IZ = 1400.0, 2300.0
WHEELBASE = 2.31
A = 1.10
B = WHEELBASE - A
TYRE_R = 0.281
MU_DRY, MU_WET = 0.95, 0.75
C_AXLE = 70000.0
V0 = 25.0                       # 90 km/h
PSI = 32.0
TREAD_MM = {"new": 8.0, "worn": 1.6}
ONSET_FACTOR = {"new": 1.35, "worn": 0.85}
STRAIGHT_Y = 18.0               # the bend starts here
R_BEND = 110.0
PUDDLE_Y0, PUDDLE_Y1 = 24.0, 44.0
PUDDLE_HALF_W = 2.4             # covers the lane (and a bit more)
LOOKAHEAD = 14.0
STEER_MAX = math.radians(7.0)
DT = 0.0005
T_END = 4.0
CAR_HALF_W = 0.85


def horne_mph(psi: float = PSI) -> float:
    """NASA rule of thumb (Horne): hydroplaning speed in mph ~ 9 * sqrt(tyre pressure in psi)."""
    return 9.0 * math.sqrt(psi)


def onset_ms(tread: str) -> float:
    return horne_mph() * 0.44704 * ONSET_FACTOR[tread]


def lane_x(y: float) -> float:
    """Lane centre (x) at distance y along the road; the bend turns left (towards -x)."""
    if y <= STRAIGHT_Y:
        return 0.0
    d = min(y - STRAIGHT_Y, R_BEND * 0.999)
    return -(R_BEND - math.sqrt(R_BEND * R_BEND - d * d))


def lane_heading(y: float) -> float:
    if y <= STRAIGHT_Y:
        return 0.0
    d = min(y - STRAIGHT_Y, R_BEND * 0.999)
    return math.asin(d / R_BEND)


def in_puddle(x: float, y: float) -> bool:
    return PUDDLE_Y0 <= y <= PUDDLE_Y1 and abs(x - lane_x(y)) <= PUDDLE_HALF_W


def grip_fraction(tread: str, speed: float, wet: bool) -> float:
    """Front side grip as a fraction of dry grip. In water, above the onset speed the tyre floats: grip falls to a few percent."""
    if not wet:
        return 1.0
    base = MU_WET / MU_DRY
    v_on = onset_ms(tread)
    lift = min(1.0, max(0.0, (speed - v_on) / 3.0))          # partial -> full float over 3 m/s
    return base * (1.0 - 0.94 * lift)


def _fy(alpha, mu, fz):
    cap = mu * fz
    return cap * math.tanh(C_AXLE * alpha / cap)


@lru_cache(maxsize=None)
def _run(tread: str) -> tuple:
    fzf, fzr = M * G * B / WHEELBASE, M * G * A / WHEELBASE
    x = y = psi = 0.0
    vx, vy, r = V0, 0.0, 0.0
    wheel_angle = 0.0
    rows = []
    for i in range(int(round(T_END / DT)) + 1):
        t = i * DT
        # driver: look ahead to the lane centre
        ly = y + LOOKAHEAD
        tx, ty = lane_x(ly), ly
        ang = math.atan2(-(tx - x), ty - y) - psi            # heading +psi turns toward -x
        ff = WHEELBASE / R_BEND if y + A > STRAIGHT_Y else 0.0           # feed-forward for the bend the driver can see
        d = max(-STEER_MAX, min(STEER_MAX, ff + 2.0 * WHEELBASE * math.sin(ang) / LOOKAHEAD * 1.6))
        speed = math.hypot(vx, vy)
        wet_f = in_puddle(x + -math.sin(psi) * A, y + math.cos(psi) * A)   # front axle position
        wet_r = in_puddle(x - -math.sin(psi) * B, y - math.cos(psi) * B)
        gf = grip_fraction(tread, speed, wet_f)
        gr = grip_fraction(tread, speed, wet_r)
        u = max(vx, 0.5)
        af = d - math.atan2(vy + A * r, u)
        ar = -math.atan2(vy - B * r, u)
        fyf = _fy(af, MU_DRY * gf, fzf)
        fyr = _fy(ar, MU_DRY * gr, fzr)
        drag = 0.015 * M * G + 0.4 * u * u
        ax = (-drag - fyf * math.sin(d)) / M + vy * r
        ay = (fyf * math.cos(d) + fyr) / M - vx * r
        rr = (A * fyf * math.cos(d) - B * fyr) / IZ
        vx = max(0.0, vx + ax * DT)
        vy += ay * DT
        r += rr * DT
        psi += r * DT
        x += (vx * -math.sin(psi) - vy * math.cos(psi)) * DT
        y += (vx * math.cos(psi) - vy * math.sin(psi)) * DT
        wheel_angle += vx / TYRE_R * DT
        rows.append((t, x, y, psi, speed, r, d, wheel_angle, gf, gr, wet_f, wet_r))
    return tuple(rows)


def at(tread: str, t: float) -> dict:
    if t < 0:
        return {"t": t, "x": 0.0, "y": V0 * t, "heading": 0.0, "speed": V0, "yaw_rate": 0.0, "steer": 0.0, "wheel_angle": V0 * t / TYRE_R,
                "grip_front": 1.0, "grip_rear": 1.0, "wet_front": False, "wet_rear": False, "lane_offset": 0.0}
    rows = _run(tread)
    i = min(len(rows) - 1, max(0, int(round(t / DT))))
    t_, x, y, psi, sp, r, d, wa, gf, gr, wf, wr = rows[i]
    return {"t": t_, "x": x, "y": y, "heading": psi, "speed": sp, "yaw_rate": r, "steer": d, "wheel_angle": wa, "grip_front": gf, "grip_rear": gr,
            "wet_front": wf, "wet_rear": wr, "lane_offset": x - lane_x(y)}


def hydro_physics() -> dict:
    """Gate: what the narration says is what the model does."""
    problems = []
    if not onset_ms("worn") < V0 < onset_ms("new"):
        problems.append("the test speed is not between the worn and new onset speeds")
    worn = [at("worn", i / 50) for i in range(int(T_END * 50))]
    new = [at("new", i / 50) for i in range(int(T_END * 50))]
    worn_min = min(s["grip_front"] for s in worn)
    new_min = min(s["grip_front"] for s in new)
    if worn_min > 0.15:
        problems.append(f"the worn tyres never float (front grip >= {worn_min:.2f})")
    if new_min < 0.6:
        problems.append(f"the new tyres lose too much grip ({new_min:.2f})")
    worn_off = max(abs(s["lane_offset"]) for s in worn)
    new_off = max(abs(s["lane_offset"]) for s in new)
    if worn_off < 2.5:
        problems.append(f"the worn car stays in its lane (max offset {worn_off:.1f} m)")
    if new_off > 0.8:
        problems.append(f"the new car leaves its lane (max offset {new_off:.1f} m)")
    if max(abs(s["steer"]) for s in worn) < max(abs(s["steer"]) for s in new):
        problems.append("the worn car's driver does not steer harder than the new car's")
    float_s = next((s["t"] for s in worn if s["grip_front"] < 0.15), None)
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "onset_kmh_worn": round(onset_ms("worn") * 3.6, 1),
            "onset_kmh_new": round(onset_ms("new") * 3.6, 1), "horne_kmh": round(horne_mph() * 1.609, 1), "worn_min_grip": round(worn_min, 3),
            "new_min_grip": round(new_min, 3), "worn_max_offset_m": round(worn_off, 2), "new_max_offset_m": round(new_off, 2), "worn_floats_from_s": float_s}
