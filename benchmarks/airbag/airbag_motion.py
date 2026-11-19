"""EP.08 airbag: the SAME crash as EP.04/EP.05 (crumple car into a wall at 64 km/h), the same modern belt, two cars: with and without a
driver airbag (pure Python, no Blender).

The torso comes from EP.05's belt model (belt_motion, variant "modern"). The head is a second mass on a springy neck that keeps moving
after the belt holds the chest, toward the steering wheel.
- "off": no airbag. The head swings until it meets the steering-wheel hub (stiff) and stops in a few millimetres: a very high peak.
- "on": the crash sensor fires the igniter FIRE_DELAY_S after first contact; gas from the inflator fills the bag in FILL_S. The full bag
  stands BAG_DEPTH_M in front of the hub. The head meets the bag, and the bag pushes back while gas escapes through its vents: a soft,
  long stop. The bag is already deflating as the head sinks in (it is DESIGNED to empty, so it does not bounce the head back).
Illustrative one-dimensional model, not calibrated to any real car or airbag; the film description says so."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from benchmarks.belt_limiter import belt_motion as bm

G = 9.81
M_HEAD = 5.0                 # kg head
K_NECK, C_NECK = 3000.0, 25.0  # head-to-torso spring and damper (forward bend)
HEAD_GAP_M = 0.48            # head to steering-wheel hub before the crash
K_HUB, C_HUB = 800_000.0, 900.0
FIRE_DELAY_S = 0.012         # the sensor decides and fires the igniter
FILL_S = 0.028               # inflator fills the bag (about 30 ms)
BAG_DEPTH_M = 0.30           # full bag in front of the hub
K_BAG, C_BAG = 6000.0, 220.0  # gas spring and damping of the bag on the head
VENT_START_S = 0.010         # after full: vents let the gas out, the bag softens
VENT_TAU_S = 0.040
HEAD_OK_G, HEAD_SEVERE_G = 50.0, 150.0


def contact_time_s() -> float:
    return bm.contact_time_s()


def fill(t: float) -> float:
    """Bag fill 0..1 at simulated time t (by volume, before venting)."""
    u = (t - contact_time_s() - FIRE_DELAY_S) / FILL_S
    return float(np.clip(u, 0.0, 1.0))


def vent(t: float) -> float:
    """Fraction of the gas still in the bag (1 = full) once the vents open."""
    t_full = contact_time_s() + FIRE_DELAY_S + FILL_S + VENT_START_S
    if t <= t_full:
        return 1.0
    return float(0.25 + 0.75 * np.exp(-(t - t_full) / VENT_TAU_S))


@lru_cache(maxsize=None)
def response(variant: str) -> dict:
    if variant not in ("on", "off"):
        raise KeyError(variant)
    torso = bm.response("modern")
    t = torso["t"]
    rec = bm._crash()
    a_car = rec["g"] * G
    r_t = torso["r"]
    h = hv = 0.0
    n = len(t)
    h_out, g_out, bag_out, comp_out = (np.zeros(n) for _ in range(4))
    sub = 40
    for i in range(1, n):
        dt = (t[i] - t[i - 1]) / sub
        a_i = 0.5 * (a_car[i] + a_car[i - 1])
        r0, r1 = r_t[i - 1], r_t[i]
        f_contact = 0.0
        for k in range(sub):
            tt = t[i - 1] + (k + 1) * dt
            r = r0 + (r1 - r0) * (k + 1) / sub
            rv = (r1 - r0) / (t[i] - t[i - 1])
            f_neck = K_NECK * (h - r) + C_NECK * (hv - rv)
            f_contact = 0.0
            if variant == "on":
                depth = BAG_DEPTH_M * fill(tt) * (0.55 + 0.45 * vent(tt))      # the bag face moves back as gas escapes
                comp = h - (HEAD_GAP_M - depth)
                if comp > 0 and fill(tt) > 0:
                    f_contact = vent(tt) * K_BAG * comp + (C_BAG * hv if hv > 0 else 0.0)
            if h > HEAD_GAP_M:
                f_contact += K_HUB * (h - HEAD_GAP_M) + (C_HUB * hv if hv > 0 else 0.0)
            hv += (a_i - (f_neck + f_contact) / M_HEAD) * dt
            h += hv * dt
            if h < 0:
                h, hv = 0.0, max(hv, 0.0)
        h_out[i] = h
        g_out[i] = f_contact / (M_HEAD * G)
        if variant == "on":
            bag_out[i] = fill(t[i]) * (0.55 + 0.45 * vent(t[i]))
            comp_out[i] = max(0.0, h - (HEAD_GAP_M - BAG_DEPTH_M * bag_out[i]))
    return {"t": t, "head_m": h_out, "head_g": g_out, "peak_head_g": np.maximum.accumulate(g_out), "bag": bag_out, "bag_press_m": comp_out,
            "torso_m": r_t}


def at(variant: str, sim_time: float) -> dict:
    res = response(variant)

    def pick(key):
        return float(np.interp(sim_time, res["t"], res[key]))
    peak = pick("peak_head_g")
    return {"head_m": pick("head_m"), "head_g": pick("head_g"), "peak_head_g": peak, "torso_m": pick("torso_m"),
            "injury": float(np.clip((peak - HEAD_OK_G) / (HEAD_SEVERE_G - HEAD_OK_G), 0.0, 1.0)),
            "bag": pick("bag") if variant == "on" else 0.0, "fill": fill(sim_time) if variant == "on" else 0.0,
            "vent": vent(sim_time) if variant == "on" else 1.0, "bag_press_m": pick("bag_press_m") if variant == "on" else 0.0,
            "neck_bend_m": pick("head_m") - pick("torso_m")}


def airbag_physics() -> dict:
    """Gate: what the narration says is what the model does."""
    on, off = response("on"), response("off")
    problems = []
    p_on, p_off = float(on["peak_head_g"][-1]), float(off["peak_head_g"][-1])
    if not p_off > 2.0 * p_on:
        problems.append(f"the airbag does not clearly lower the head load ({p_on:.0f} g vs {p_off:.0f} g)")
    if float(off["head_m"].max()) < HEAD_GAP_M:
        problems.append("without the airbag the head never reaches the steering wheel")
    if float(on["head_m"].max()) >= HEAD_GAP_M:
        problems.append("with the airbag the head still reaches the hub")
    tc = contact_time_s()
    t_full = tc + FIRE_DELAY_S + FILL_S
    first_bag_contact = next((float(tt) for tt, c in zip(on["t"], on["bag_press_m"]) if c > 0.002), None)
    if first_bag_contact is None or first_bag_contact < t_full - 0.004:
        problems.append("the head reaches the bag before it is full")
    if not vent(t_full + 0.08) < 0.7:
        problems.append("the bag does not empty through its vents")
    t_hub = next((float(tt) for tt, hh in zip(off["t"], off["head_m"]) if hh >= HEAD_GAP_M), None)
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "peak_head_g_on": round(p_on, 1), "peak_head_g_off": round(p_off, 1),
            "bag_full_ms_after_contact": round((t_full - tc) * 1000, 1), "head_meets_bag_ms": round((first_bag_contact - tc) * 1000, 1) if first_bag_contact else None,
            "head_hits_hub_ms": round((t_hub - tc) * 1000, 1) if t_hub else None, "max_head_on_m": round(float(on["head_m"].max()), 3)}
