"""EP.20 "can opener" low rail bridge (pure Python + numpy). Render-world coordinates: the street runs along +y, the box truck drives
in the right-hand lane (x = X_LANE) toward a rail bridge. A steel crash beam hangs across the street just in front of the bridge
(beam centre y = 0); its underside is the posted clearance, 11 ft 8 in (12 ft 4 in after the 2019 raise of 8 in).

The truck's box is 13 ft tall, so its top 16 in cannot pass. Simulated time t = 0 when the front of the box meets the beam's face.
After that the beam stands still while the truck rolls on underneath it: the band of the box above the clearance is stopped. The
front wall and its header crush first (a short, hard pulse); then the roof skin (0.040 in aluminium, thinner than a dime, riveted to
the top rails and laid over roof bows every 24 in) peels off and rolls up against the beam, the rivets popping one by one, while the
side walls above the clearance fold outward and each roof bow buckles as it reaches the beam. The cab is lower than the beam and
passes under untouched. The driver hits the brakes after a reaction time; the truck stops with most of the roof peeled.

Variants: "old" (11 ft 8 in), "raised" (12 ft 4 in: the same truck still hits, 8 in of its box), "warned" (the over-height detector
upstream sees the truck, flashes the warning and turns the signal red; t = 0 when the box crosses the detector beam; the driver
stops at the stop line) and "raising" (t is the fraction of the 2019 raise done, 0..1). Simplified explanation model, not a crash
reconstruction of any real event."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

MPH = 0.44704
FT, IN = 0.3048, 0.0254
G = 9.81
CLEAR_OLD = 11 * FT + 8 * IN            # 3.556 m, the famous posted clearance
RAISE = 8 * IN                          # the October 2019 raise
CLEAR_NEW = CLEAR_OLD + RAISE           # 12 ft 4 in
TRUCK_H = 13 * FT                       # top of the box
CAB_H = 2.95                            # top of the cab (and its roof fairing)
SKIN_T = 0.040 * IN                     # roof skin, a common box-body spec
DIME_T = 1.35e-3                        # US dime
BOW_PITCH = 24 * IN
RIVET_PITCH = 4 * IN
BOX_L, BOX_W, BOX_FLOOR = 6.40, 2.44, 1.15
CAB_FRONT = 2.55                        # bumper, ahead of the box front (local y = 0)
X_LANE = 1.80
BEAM_T, BEAM_D = 0.30, 0.76             # flange width along the street, depth
FACE_Y = -BEAM_T / 2                    # the beam's approach face
M = 8000.0                              # loaded 26,000 lb class box truck, kg
V0 = 15 * MPH
X_HDR = 0.30                            # travel over which the front wall and header crush
F_HDR_PER_M = 230e3                     # N per metre of band above the clearance (16 in band: about 93 kN)
F_SKIN = 12e3                           # roof skin peel + rivets popping, N
K_WALL = 45e3                           # side walls folding outward and their posts bending, N per metre of band
E_BOW = 1200.0                          # J to buckle one roof bow
X_BOW = 0.10
T_REACT = 0.7                           # the bang, then the brakes
A_BRAKE = 5.0
Y_SENSOR = -40.0                        # over-height detector beam across the street (warned variant)
Y_STOP = -17.0                          # stop line of the signal before the cross street
SIGNAL_YELLOW = (0.2, 1.4)              # warned variant: the detector turns the light yellow, then red
WARN_REACT = 0.9


def band(variant: str) -> float:
    return TRUCK_H - (CLEAR_NEW if variant == "raised" else CLEAR_OLD)


def clearance(variant: str, t: float = 0.0) -> float:
    if variant == "raised":
        return CLEAR_NEW
    if variant == "raising":
        return CLEAR_OLD + RAISE * min(1.0, max(0.0, t))
    return CLEAR_OLD


def bows() -> list[float]:
    """Roof bows as distances from the box front (local y = -p)."""
    out, p = [], 0.30
    while p < BOX_L - 0.2:
        out.append(round(p, 4))
        p += BOW_PITCH
    return out


def rivets() -> list[float]:
    """Rivets along each top rail, as distances from the box front."""
    return [round(0.05 + j * RIVET_PITCH, 4) for j in range(int((BOX_L - 0.1) / RIVET_PITCH) + 1)]


def resist(d: float, variant: str) -> tuple[float, float, float]:
    """Header pulse, steady peel and bow buckling forces (N) at d metres of travel past the beam face."""
    if d <= 0:
        return 0.0, 0.0, 0.0
    b = band(variant)
    f_hdr = F_HDR_PER_M * b * math.pi / 2 * math.sin(math.pi * d / X_HDR) if d < X_HDR else 0.0      # half sine; mean F_HDR_PER_M * b
    f_peel = (F_SKIN + K_WALL * b) * min(1.0, d / 0.05)
    f_bow = 0.0
    for p in bows():
        if p <= d < p + X_BOW:
            f_bow += E_BOW / X_BOW * math.pi / 2 * math.sin(math.pi * (d - p) / X_BOW)
    return f_hdr, f_peel, f_bow


@lru_cache(maxsize=None)
def _crash(variant: str) -> dict:
    dt = 1e-4
    t, d, v = 0.0, 0.0, V0
    ts, ds, vs, fs = [0.0], [0.0], [V0], [0.0]
    w_hdr = w_peel = w_bow = w_brake = 0.0
    while v > 0 and t < 10:
        fh, fp, fb = resist(d, variant)
        fbr = M * A_BRAKE if t >= T_REACT else 0.0
        f = fh + fp + fb + fbr
        a = -f / M
        dv = a * dt
        if v + dv <= 0:                       # stops inside this step
            step = v * v / (2 * -a) if a < 0 else 0.0
            w_hdr += fh * step; w_peel += fp * step; w_bow += fb * step; w_brake += fbr * step
            t += v / -a
            d += step
            v = 0.0
        else:
            step = (v + 0.5 * dv) * dt
            w_hdr += fh * step; w_peel += fp * step; w_bow += fb * step; w_brake += fbr * step
            d += step
            v += dv
            t += dt
        ts.append(t); ds.append(d); vs.append(v); fs.append(f)
    return {"t": np.array(ts), "d": np.array(ds), "v": np.array(vs), "f": np.array(fs), "stop_t": t, "stop_d": d,
            "work": {"header": w_hdr, "peel": w_peel, "bows": w_bow, "brakes": w_brake}}


def travel(t: float, variant: str = "old") -> float:
    """Distance the box front has travelled past the beam face (negative before contact)."""
    if variant == "warned":
        return warned_y(t) - Y_SENSOR
    if variant == "raising":
        return -60.0                          # no truck in the raise time-lapse: parked out of the street
    if t <= 0:
        return V0 * t
    c = _crash(variant)
    if t >= c["stop_t"]:
        return float(c["stop_d"])
    return float(np.interp(t, c["t"], c["d"]))


def speed(t: float, variant: str = "old") -> float:
    if variant == "warned":
        return warned_speed(t)
    if variant == "raising":
        return 0.0
    if t <= 0:
        return V0
    c = _crash(variant)
    return 0.0 if t >= c["stop_t"] else float(np.interp(t, c["t"], c["v"]))


def braking(t: float, variant: str = "old") -> bool:
    if variant == "warned":
        return t >= WARN_REACT and warned_speed(t) > 0
    if variant == "raising":
        return False
    return t >= T_REACT


def peel(t: float, variant: str = "old") -> float:
    """Length of roof skin peeled off (m)."""
    if variant in ("warned", "raising"):
        return 0.0
    return max(0.0, min(travel(t, variant), BOX_L))


def bows_buckled(t: float, variant: str = "old") -> int:
    p = peel(t, variant)
    return sum(1 for b in bows() if b < p)


def rivets_popped(t: float, variant: str = "old") -> int:
    """Rivets torn out on both top rails."""
    p = peel(t, variant)
    return 2 * sum(1 for r in rivets() if r < p)


def pop_time(dist: float, variant: str = "old") -> float | None:
    """When the peel front reaches a point dist metres behind the box front (None if it never does)."""
    c = _crash(variant)
    if dist > c["stop_d"]:
        return None
    return float(np.interp(dist, c["d"], c["t"]))


# --- warned variant: the detector sees the truck, the signal turns red, the driver stops at the stop line ---------------------------
def _warn_decel() -> float:
    y_brake = Y_SENSOR + V0 * WARN_REACT            # box front when the brakes go on
    stop_front = Y_STOP - 1.0 - CAB_FRONT           # the bumper stops a metre short of the line
    return V0 * V0 / (2 * (stop_front - y_brake))


def warned_y(t: float) -> float:
    """World y of the box front in the warned variant (t = 0 when it crosses the detector beam)."""
    if t <= WARN_REACT:
        return Y_SENSOR + V0 * t
    a = _warn_decel()
    tau = min(t - WARN_REACT, V0 / a)
    return Y_SENSOR + V0 * WARN_REACT + V0 * tau - 0.5 * a * tau * tau


def warned_speed(t: float) -> float:
    if t <= WARN_REACT:
        return V0
    return max(0.0, V0 - _warn_decel() * (t - WARN_REACT))


def signal(t: float, variant: str) -> str:
    """Traffic signal before the bridge: green, yellow or red."""
    if variant != "warned" or t < SIGNAL_YELLOW[0]:
        return "green"
    return "yellow" if t < SIGNAL_YELLOW[1] else "red"


def warning_on(t: float, variant: str) -> bool:
    return variant == "warned" and t >= 0.0


# --- world placement -------------------------------------------------------------------------------------------------------------
def box_front_y(t: float, variant: str = "old") -> float:
    if variant == "warned":
        return warned_y(t)
    return FACE_Y + travel(t, variant)


def state(t: float, variant: str = "old") -> dict:
    return {"t": t, "variant": variant, "x": X_LANE, "y": box_front_y(t, variant), "speed": speed(t, variant), "peel": peel(t, variant),
            "clearance": clearance(variant, t), "band": max(0.0, TRUCK_H - clearance(variant, t)), "braking": braking(t, variant),
            "bows": bows_buckled(t, variant), "rivets": rivets_popped(t, variant), "signal": signal(t, variant), "warning": warning_on(t, variant)}


def opener_physics() -> dict:
    problems = []
    if abs(CLEAR_OLD - 3.556) > 1e-3 or abs(CLEAR_NEW - (12 * FT + 4 * IN)) > 1e-6:
        problems.append("clearances are not 11 ft 8 in and 12 ft 4 in")
    if round((TRUCK_H - CLEAR_OLD) / IN) != 16:
        problems.append("the truck is not sixteen inches too tall")
    if TRUCK_H <= CLEAR_NEW:
        problems.append("after the raise this truck would fit (narration: trucks still hit it)")
    if CAB_H > CLEAR_OLD - 0.15:
        problems.append("the cab would not roll under")
    if SKIN_T >= DIME_T:
        problems.append("the roof skin is not thinner than a dime")
    out = {}
    for variant in ("old", "raised"):
        c = _crash(variant)
        ke = 0.5 * M * V0 * V0
        w = sum(c["work"].values())
        if abs(w - ke) / ke > 0.01:
            problems.append(f"{variant}: energy does not balance ({w:.0f} J of work for {ke:.0f} J)")
        if not 2.5 < c["stop_d"] < BOX_L - 0.8:
            problems.append(f"{variant}: the truck stops after {c['stop_d']:.2f} m (want a long peel and the back of the roof intact)")
        peak_g = float(np.max(c["f"]) / M / G)
        if peak_g > 2.5:
            problems.append(f"{variant}: a {peak_g:.1f} g jolt is not a box being peeled")
        out[variant] = {"stop_s": round(c["stop_t"], 3), "peeled_m": round(c["stop_d"], 2), "peak_g": round(peak_g, 2),
                        "work_kj": {k: round(v / 1e3, 1) for k, v in c["work"].items()}}
    if not _crash("raised")["stop_d"] > _crash("old")["stop_d"]:
        problems.append("the smaller band after the raise should resist less")
    if warned_y(60.0) + CAB_FRONT > Y_STOP:
        problems.append("the warned truck does not stop before the stop line")
    if signal(SIGNAL_YELLOW[1] + 0.01, "warned") != "red":
        problems.append("the detector does not turn the light red")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "too_tall_in": round((TRUCK_H - CLEAR_OLD) / IN, 1),
            "after_raise_too_tall_in": round((TRUCK_H - CLEAR_NEW) / IN, 1), "skin_mm": round(SKIN_T * 1e3, 3), "dime_mm": DIME_T * 1e3,
            "impact_mph": round(V0 / MPH, 1), "bows": len(bows()), "rivets_per_rail": len(rivets()), **out}


if __name__ == "__main__":
    import json
    print(json.dumps(opener_physics(), indent=1))
