"""EP.23 exploding manhole covers (pure Python + numpy). Render-world coordinates: a city street runs along +y; the manhole is in the
right-hand travel lane at (MX, MY). Under it an electrical vault (a concrete box 3.0 x 1.8 x 2.1 m inside, its ceiling 0.65 m under
the road, reached through a 0.72 m round neck) carries power cables along its long walls between duct banks at both ends, with a splice
in the middle of the east wall.

Two clocks:
- smoulder (t = seconds since the insulation at the splice began to burn): road-salt meltwater has eaten through the insulation; arcs
  come and go and the burning insulation gives off flammable gas at Q_GAS. The vault is taken as well mixed; it trades air with the
  street through the gaps of a solid cover only slowly (Q_LEAK) but through a vented cover's holes quickly (Q_VENT). Under a solid
  cover the gas passes its lower flammable limit (5 %) after about eight minutes; under a vented cover it levels off near 2 %, below
  half the limit, so it cannot burn.
- blast (t = seconds after an arc ignites the gas at the splice): the flame burns through the vault in T_BURN and the hot gas expands
  (closed-vessel pressure ratio PR); the pressure pushes the cover up; gas and flame escape through the gap that opens under it
  (orifice flow, sonic at most); the push fades once the cover is out of its frame (the jet spreads, Z_JET). The cover leaves at about
  11 m/s, flies about 20 ft up turning over once, lands beside the hole and wobbles to rest like a dropped coin. A latched cover is
  caught 3.5 in up by two latches: the gas vents through the ring-shaped gap and the cover drops back onto its seat.
Simplified explanation model, not the data of any utility or cover maker."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

IN, LB, FT = 0.0254, 0.45359237, 0.3048
G = 9.81
P0 = 101325.0
RHO_AIR = 1.2
GAMMA = 1.35
MX, MY = 1.6, 0.0                         # manhole centre on the street (m)
R_COVER = 0.38                            # 30 in cover
T_COVER = 0.045
M_COVER = 300 * LB                        # "up to three hundred pounds" (136 kg)
A_COVER = math.pi * R_COVER ** 2
R_NECK = 0.36                             # the opening under the cover
A_NECK = math.pi * R_NECK ** 2
VAULT_L, VAULT_W, VAULT_H = 3.0, 1.8, 2.1
Z_CEIL, Z_FLOOR = -0.65, -2.75
V_VAULT = VAULT_L * VAULT_W * VAULT_H + A_NECK * -Z_CEIL
SPLICE = (MX + 0.72, MY + 0.15, -1.55)   # the burning splice on the east wall's middle cable
CABLE_TOP = -1.18                         # top of the highest cable on the east wall
LFL = 0.05                                # lower flammable limit of the gas (volume share)
Q_GAS = 1.2e-3                            # flammable gas from the smouldering insulation (m^3/s)
Q_LEAK = 0.4e-3                           # air exchange under a solid cover (m^3/s)
Q_VENT = 60e-3                            # air exchange through a vented cover's holes (m^3/s)
VENT_SHARE = 0.16                         # open share of the vented cover
T_IGNITE = 540.0                          # smoulder time of the igniting arc (s)
PR = 2.7                                  # closed-vessel pressure ratio of the lean mixture
T_BURN = 0.16                             # time for the flame to burn through the vault (s)
C_D = 0.62
A_LEAK = 2 * 0.025 * 0.05                 # the two pick holes of a solid cover
Z_SEAT = 0.04                             # the cover sits this deep in its frame
Z_JET = 0.30                              # the push fades over this height once the cover is out of the frame
Z_LATCH = 3.5 * IN                        # a latched cover is caught here
DRIFT = (0.62, 0.22)                      # sideways drift while it flies (m/s)
REST_E = 0.12                             # bounce on landing
WOBBLE_A0, WOBBLE_T = 0.10, 1.6           # tilt when it lands (rad) and time to settle (s)
DT = 2e-5


# --- smoulder clock ---------------------------------------------------------------------------------------------------------------
def concentration(t: float, vented: bool = False) -> float:
    """Flammable-gas share in the vault after t s of smouldering (well mixed, constant source)."""
    if t <= 0:
        return 0.0
    q_out = Q_GAS + (Q_VENT if vented else Q_LEAK)
    c_ss = Q_GAS / q_out
    return c_ss * (1.0 - math.exp(-t * q_out / V_VAULT))


def time_to_lfl(vented: bool = False) -> float | None:
    q_out = Q_GAS + (Q_VENT if vented else Q_LEAK)
    c_ss = Q_GAS / q_out
    if c_ss <= LFL:
        return None
    return -V_VAULT / q_out * math.log(1.0 - LFL / c_ss)


@lru_cache(maxsize=None)
def arcs() -> tuple:
    """Arcs at the splice while it smoulders: (start s, length s, strength 0..1); the last one ignites the gas."""
    rng = np.random.default_rng(23)
    out, t = [], 0.7
    while t < T_IGNITE - 3.0:
        out.append((round(t, 3), round(float(rng.uniform(0.08, 0.32)), 3), round(float(rng.uniform(0.55, 1.0)), 3)))
        t += float(rng.uniform(0.5, 1.4)) if t < 14.0 else float(rng.exponential(7.0)) + 0.8      # a burst as the insulation fails
    out.append((T_IGNITE - 0.05, 0.25, 1.0))
    return tuple(out)


def arc_level(t: float) -> float:
    """Arc brightness 0..1 at smoulder time t (flickers inside each arc)."""
    for a, d, s in arcs():
        if a <= t < a + d:
            u = (t - a) / d
            return s * (0.55 + 0.45 * abs(math.sin(97.0 * t + 3.0 * a))) * (1.0 - 0.6 * u)
    return 0.0


DRIP_CYCLE = 6.0


@lru_cache(maxsize=None)
def drips() -> tuple:
    """Meltwater drops in a repeating DRIP_CYCLE s pattern: (release s, x, y, z from, z to). Some fall from the cover's gaps down the
    neck to the floor; most run along the ceiling from the neck and fall onto the cables on the east wall and the splice."""
    rng = np.random.default_rng(230)
    out = []
    for k in range(26):
        t0 = float(rng.uniform(0, DRIP_CYCLE))
        if k < 6:
            a = rng.uniform(0, 2 * math.pi)
            out.append((t0, MX + 0.31 * math.cos(a), MY + 0.31 * math.sin(a), -0.05, Z_FLOOR + 0.03))
        else:
            y = float(rng.uniform(-1.25, 1.25)) if k % 3 else SPLICE[1] + float(rng.uniform(-0.25, 0.25))
            z_to = SPLICE[2] + 0.075 if abs(y - SPLICE[1]) < 0.3 else CABLE_TOP
            out.append((t0, SPLICE[0] + float(rng.uniform(-0.03, 0.03)), y, Z_CEIL - 0.01, z_to))
    return tuple(sorted(out))


def drop_height(t: float, drip: tuple) -> float | None:
    """Height of a drop at time t (None while it gathers or after it hits)."""
    t0, _, _, z0, z1 = drip
    tau = (t - t0) % DRIP_CYCLE
    z = z0 - 0.5 * G * tau * tau
    return z if z > z1 else None


# --- blast clock ------------------------------------------------------------------------------------------------------------------
def burn(t: float) -> float:
    if t <= 0:
        return 0.0
    u = min(1.0, t / T_BURN)
    return u * u * (3 - 2 * u)


@lru_cache(maxsize=None)
def _blast(kind: str) -> dict:
    """Integrate the vault gas and the cover (kind 'solid' or 'latched') from ignition to rest."""
    latched = kind == "latched"
    t, m, z, v = 0.0, 1.0, 0.0, 0.0
    t_lift = t_free = t_out = t_land = t_caught = t_back = None
    work = 0.0
    landed_hops = 0
    rec = {k: [] for k in ("t", "p", "z", "v", "q", "m")}
    q_cum, peak_p, z_max = 0.0, 0.0, 0.0
    step = 0
    while t < 6.0:
        b = burn(t)
        p = P0 * m * (1.0 + (PR - 1.0) * b)
        dp = max(0.0, p - P0)
        gap = min(A_NECK, 2 * math.pi * R_NECK * max(z, 0.0)) if t_land is None else A_NECK
        a_open = A_LEAK + gap
        rho = RHO_AIR * m
        u = min(math.sqrt(2 * dp / rho), math.sqrt(GAMMA * p / rho)) if dp > 0 else 0.0
        mdot = C_D * a_open * rho * u
        q = mdot / rho if rho > 0 else 0.0
        m -= mdot / (RHO_AIR * V_VAULT) * DT
        q_cum += q * DT
        peak_p = max(peak_p, dp)
        f = 0.0
        if t_land is None:
            f = dp * A_COVER * (1.0 if z <= Z_SEAT else math.exp(-(z - Z_SEAT) / Z_JET))
        drag = 0.5 * RHO_AIR * 1.0 * A_COVER * 0.6 * v * abs(v)
        acc = (f - drag) / M_COVER - G
        floor = T_COVER if t_land is not None else 0.0
        if z <= floor and v <= 0.0 and acc <= 0.0:
            z, v = floor, 0.0
        else:
            if t_lift is None:
                t_lift = t
            work += f * v * DT
            v += acc * DT
            z += v * DT
            if latched and z >= Z_LATCH:
                if t_caught is None:
                    t_caught = t
                z, v = Z_LATCH, min(v, 0.0)
            if latched and t_caught is not None and z <= 0.0 and v < 0 and t_back is None:
                t_back = t
                z, v = 0.0, 0.0
            if t_free is None and z > Z_SEAT:
                t_free = t
            if not latched and t_out is None and z > Z_SEAT + 3 * Z_JET:
                t_out = t
            if not latched and t_out is not None and z <= T_COVER and v < 0:          # down on the street beside the hole
                landed_hops += 1
                if t_land is None:
                    t_land = t
                z = T_COVER
                v = -REST_E * v if landed_hops == 1 else 0.0
        z_max = max(z_max, z)
        if step % 50 == 0:
            for k, val in (("t", t), ("p", dp), ("z", z), ("v", v), ("q", q), ("m", m)):
                rec[k].append(val)
        t += DT
        step += 1
    arr = {k: np.array(val) for k, val in rec.items()}
    return {"rec": arr, "t_lift": t_lift, "t_free": t_free, "t_out": t_out, "t_land": t_land, "t_caught": t_caught, "t_back": t_back, "work": work,
            "peak_p": peak_p, "z_max": z_max, "q_cum": q_cum, "m_end": m}


def _interp(kind: str, key: str, t: float) -> float:
    r = _blast(kind)["rec"]
    if t <= 0:
        return 0.0 if key != "m" else 1.0
    return float(np.interp(t, r["t"], r[key]))


def pressure(t: float, kind: str = "solid") -> float:
    """Vault overpressure (Pa) t s after ignition."""
    return _interp(kind, "p", t)


def outflow(t: float, kind: str = "solid") -> float:
    """Gas and flame escaping through the opening (m^3/s)."""
    return _interp(kind, "q", t)


def lift(t: float, kind: str = "solid") -> float:
    """Height of the cover's underside above its seat (m)."""
    return _interp(kind, "z", t)


def cover_speed(t: float, kind: str = "solid") -> float:
    return _interp(kind, "v", t)


def launch_speed() -> float:
    r = _blast("solid")
    i = int(np.searchsorted(r["rec"]["t"], r["t_out"]))
    return float(r["rec"]["v"][i])


def apex() -> float:
    return _blast("solid")["z_max"]


def landing_time() -> float:
    return _blast("solid")["t_land"]


def drift(t: float) -> tuple[float, float]:
    """Sideways offset of the flying cover from the hole's centre (m)."""
    r = _blast("solid")
    t0 = r["t_free"]
    if t <= t0:
        return 0.0, 0.0
    tl = r["t_land"]
    tau = min(t, tl) - t0
    return DRIFT[0] * tau, DRIFT[1] * tau


def tumble(t: float) -> float:
    """Turn of the flying cover about the axis across its drift (rad): one full turn in the air, so it lands face up."""
    r = _blast("solid")
    t0, tl = r["t_free"], r["t_land"]
    if t <= t0:
        return 0.0
    u = min(1.0, (t - t0) / (tl - t0))
    return 2 * math.pi * u


@lru_cache(maxsize=None)
def _wobble() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Euler's-disk settling after the landing: tilt shrinks while the roll around the rim speeds up."""
    ts = np.arange(0.0, WOBBLE_T + 0.4, 1e-3)
    tilt = WOBBLE_A0 * np.clip(1.0 - ts / WOBBLE_T, 0.0, 1.0) ** 0.8
    rate = np.sqrt(G / (R_COVER * np.maximum(tilt, 0.004)))
    rate = np.minimum(rate, 70.0) * (tilt > 1e-4)
    phase = np.concatenate([[0.0], np.cumsum(0.5 * (rate[1:] + rate[:-1]) * 1e-3)])
    return ts, tilt, phase


def wobble(t: float) -> tuple[float, float]:
    """(tilt rad, direction of the low side rad) t s after ignition (0 while it flies)."""
    tl = landing_time()
    if t <= tl:
        return 0.0, 0.0
    ts, tilt, phase = _wobble()
    return float(np.interp(t - tl, ts, tilt)), float(np.interp(t - tl, ts, phase))


def fireball(t: float, kind: str = "solid") -> float:
    """Radius of the burning gas pushed out above the street (m): the expelled volume, burning, cooling to smoke over a second."""
    r = _blast(kind)["rec"]
    if t <= 0:
        return 0.0
    ts = r["t"]
    dt = ts[1] - ts[0]
    vol = np.cumsum(r["q"]) * dt
    v_t = float(np.interp(t, ts, vol))
    return (3 * v_t / (4 * math.pi)) ** (1 / 3) * (1.0 if t < 1.0 else math.exp(-(t - 1.0) / 2.0))


def cover_state(t: float, kind: str) -> dict:
    """Where the cover is t s after ignition: centre (x, y, z of its middle; its top is flush with the street when seated), the turn
    while it flies, and the tilt while it settles."""
    zc = lift(t, kind) - T_COVER / 2
    if kind == "solid":
        dx, dy = drift(t)
        ang = tumble(t)
        tilt, ph = wobble(t)
        return {"x": MX + dx, "y": MY + dy, "z": zc, "tumble": ang, "tilt": tilt, "tilt_dir": ph}
    return {"x": MX, "y": MY, "z": zc, "tumble": 0.0, "tilt": 0.0, "tilt_dir": 0.0}


def state(t: float, variant: str) -> dict:
    """Everything the renderer and the sound need at time t of a variant ('smoulder', 'vented', 'blast', 'latched')."""
    if variant in ("smoulder", "vented"):
        vented = variant == "vented"
        return {"variant": variant, "t": t, "gas": concentration(t, vented), "gas_vs_lfl": concentration(t, vented) / LFL,
                "arc": arc_level(t) if t < T_IGNITE else 0.0, "cover": {"x": MX, "y": MY, "z": -T_COVER / 2, "tumble": 0.0, "tilt": 0.0, "tilt_dir": 0.0},
                "pressure": 0.0, "outflow": 0.0, "burn": 0.0, "fireball": 0.0, "char": char(t)}
    kind = "latched" if variant == "latched" else "solid"
    return {"variant": variant, "t": t, "gas": concentration(T_IGNITE) * (1.0 - burn(t)), "gas_vs_lfl": concentration(T_IGNITE) / LFL * (1.0 - burn(t)),
            "arc": 1.0 if -0.05 <= t < 0.02 else 0.0, "cover": cover_state(t, kind), "pressure": pressure(t, kind), "outflow": outflow(t, kind),
            "burn": burn(t), "fireball": fireball(t, kind), "char": 1.0}


def char(t: float) -> float:
    """How much of the splice's insulation has burnt (0..1) after t s of smouldering (drawn as char and embers)."""
    return min(1.0, max(0.0, t / 240.0)) ** 0.6 if t > 0 else 0.0


def manhole_physics() -> dict:
    """Gate: the numbers the film quotes or shows come out of this model and hang together."""
    problems = []
    t_lfl = time_to_lfl(False)
    c_vent = concentration(3600.0, True)
    s = _blast("solid")
    la = _blast("latched")
    v0 = launch_speed()
    ke_pe = 0.5 * M_COVER * v0 ** 2
    r = s["rec"]
    i_out = int(np.searchsorted(r["t"], s["t_out"]))
    z_out = float(r["z"][i_out])
    # work done by the gas on the cover up to t_out = kinetic + potential energy then (+ drag losses, small)
    w_needed = ke_pe + M_COVER * G * z_out
    if abs(round(M_COVER / LB) - 300) > 0:
        problems.append("the cover does not weigh 300 lb")
    if t_lfl is None or not 300 < t_lfl < 900:
        problems.append(f"under a solid cover the gas does not reach its flammable limit in 5-15 minutes ({t_lfl})")
    if concentration(T_IGNITE) <= LFL:
        problems.append("the igniting arc comes before the gas can burn")
    if time_to_lfl(True) is not None or c_vent > 0.5 * LFL:
        problems.append(f"under a vented cover the gas reaches {c_vent:.3f} (rule: under half the flammable limit)")
    if s["t_out"] is None or s["t_land"] is None:
        problems.append("the solid cover never leaves or never lands")
    else:
        if not 3.0 < s["z_max"] - T_COVER < 9.0:
            problems.append(f"the cover flies {s['z_max'] - T_COVER:.1f} m up (expected 10-30 ft)")
        dx, dy = drift(s["t_land"])
        if math.hypot(dx, dy) < 2 * R_COVER:
            problems.append("the cover lands back over its hole")
        if abs(s["work"] - w_needed) / w_needed > 0.05 and s["work"] < w_needed:
            problems.append(f"energy: gas work {s['work']:.0f} J < {w_needed:.0f} J of motion")
    if not 20e3 < s["peak_p"] < 2.0e5:
        problems.append(f"peak overpressure {s['peak_p'] / 1e3:.0f} kPa outside 20-200")
    if la["t_caught"] is None or abs(la["z_max"] - Z_LATCH) > 1e-3 or la["t_back"] is None or la["t_back"] > 1.5:
        problems.append("the latched cover is not caught at 3.5 in and back on its seat within 1.5 s")
    if abs(s["m_end"] - 1.0 / PR) > 0.02:
        problems.append(f"the vault does not vent down to the outside pressure (mass share {s['m_end']:.3f})")
    return {
        "status": "FAIL" if problems else "PASS", "problems": problems,
        "cover_lb": round(M_COVER / LB), "cover_kg": round(M_COVER, 1), "vault_m3": round(V_VAULT, 2),
        "solid_minutes_to_lfl": round(t_lfl / 60, 1) if t_lfl else None, "gas_share_at_spark": round(concentration(T_IGNITE), 4),
        "vented_gas_share_max": round(c_vent, 4), "vented_share_of_lfl": round(c_vent / LFL, 2),
        "lift_off_overpressure_kpa": round(M_COVER * G / A_COVER / 1e3, 2), "peak_overpressure_kpa": round(s["peak_p"] / 1e3, 1),
        "peak_overpressure_psi": round(s["peak_p"] / 6894.76, 1), "launch_speed_ms": round(v0, 2), "apex_m": round(s["z_max"] - T_COVER, 2),
        "apex_ft": round((s["z_max"] - T_COVER) / FT, 1), "landing_s": round(s["t_land"], 3), "landing_offset_m": round(math.hypot(*drift(s["t_land"])), 2),
        "gas_work_j": round(s["work"]), "motion_energy_at_exit_j": round(w_needed), "latched_peak_lift_in": round(la["z_max"] / IN, 2),
        "latched_back_s": round(la["t_back"], 3) if la["t_back"] else None, "latched_peak_overpressure_kpa": round(la["peak_p"] / 1e3, 1),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(manhole_physics(), indent=1))
