"""EP.04 crumple zone: one-dimensional frontal-crash simulation and the geometric crush map. Pure Python/numpy (no Blender), shared by the renderer and the gates.

Simplified and NOT calibrated to any real vehicle or crash test: a car of mass M hits a rigid barrier at V0. The nose structure crushes against a force-stroke
curve (short linear ramp, then a constant plateau); the plateau is set so the car stops after a chosen stroke. The "rigid" comparison car has the same mass, speed
and barrier but a stroke of a few centimetres. Both are hypothetical counterfactuals, not measured crash tests."""
from __future__ import annotations

import os

import numpy as np

FPS = 30
RENDER_HZ = 2000            # the crash lasts <0.1 s and the film slows it down: pose sampling must be far finer than the frame rate (EP.03 stutter lesson)
G = 9.81
V0_KMH = 50.0
MASS = 1400.0
RAMP = 0.06                 # m of stroke over which the crush force builds up
PROFILES = {
    "crumple": {"stroke": 0.62, "rebound": 0.0, "label": "CRUMPLE"},
    "rigid": {"stroke": 0.05, "rebound": 0.25, "label": "RIGID"},
}
CRUSH_LENGTH = 0.95         # m of nose structure ahead of the passenger cell that may crush
COMPACTION = 0.75           # fraction of the crushed zone that is squeezed out at full crush
LEAD_SIM = 1.2              # simulate() starts the nose this far from the barrier


def simulate(profile: str, v0_kmh: float = V0_KMH, mass: float = MASS, lead: float = LEAD_SIM, hz: int = RENDER_HZ, tail_s: float = 0.25) -> dict:
    """d = distance the car has moved since the start (cabin reference), s = permanent crush stroke, a = deceleration in g."""
    p = PROFILES[profile]
    v0 = v0_kmh / 3.6
    stroke = p["stroke"]
    f0 = 0.5 * mass * v0 * v0 / (stroke - 0.5 * RAMP)      # plateau force that absorbs the kinetic energy exactly within `stroke`
    dt = 1e-5
    n_out = int((lead / v0 + 6 * stroke / v0 + tail_s) * hz)
    t_arr, d_arr, s_arr, v_arr, a_arr = (np.zeros(n_out) for _ in range(5))
    d, v, s, t, next_i, a = 0.0, v0, 0.0, 0.0, 0, 0.0
    rebounded = False
    while next_i < n_out:
        if d > lead:
            s = max(s, d - lead)
        if d > lead and v > 0 and not rebounded:
            f = f0 * min(1.0, (d - lead) / RAMP)
            a = f / mass
            v -= a * dt
            if v <= 0:
                v, rebounded, a = -p["rebound"] * v0, True, 0.0
        elif v < 0 and d > lead:
            a = 0.0
        else:
            a = 0.0 if v > 0 or rebounded else a
        d += v * dt
        t += dt
        if t * hz >= next_i:
            t_arr[next_i], d_arr[next_i], s_arr[next_i], v_arr[next_i], a_arr[next_i] = t, d, s, v, a / G
            next_i += 1
    return {"t": t_arr, "d": d_arr, "s": s_arr, "v": v_arr, "g": a_arr, "lead": lead, "v0": v0, "mass": mass, "stroke": stroke, "hz": hz}


def summary(rec: dict) -> dict:
    stop = int(np.argmax(rec["v"] <= 0)) if np.any(rec["v"] <= 0) else len(rec["t"]) - 1
    contact = int(np.argmax(rec["d"] > rec["lead"]))
    t_stop = float(rec["t"][stop] - rec["t"][contact])
    return {"peak_g": float(rec["g"].max()), "stop_time_s": t_stop, "stroke_m": float(rec["s"].max()),
            "average_decel_g": float(rec["v0"] / t_stop / G) if t_stop > 0 else float("inf"),
            "average_force_kn": float(rec["mass"] * rec["v0"] / t_stop / 1000.0) if t_stop > 0 else float("inf")}


def rebound_distance(travel_m: float, stroke_m: float) -> float:
    """Distance back from maximum compression after contact."""
    return max(0.0, LEAD_SIM + stroke_m - travel_m) if stroke_m > 0 else 0.0


def crush_map(p0: np.ndarray, s: float, nose: float, length: float = CRUSH_LENGTH, rho: float = COMPACTION, cabin_y: float | None = None) -> np.ndarray:
    """Car-frame crush of the nose: points within the compaction depth d_c = s / rho behind the nose are squeezed (linear map) so the nose ends s further back,
    with buckling (hood folds up, fenders bulge); everything deeper is untouched, so the passenger cell never moves. p0: (N, 3) points in the car frame, +Y forward."""
    p = p0.copy()
    if s <= 1e-9:
        return p
    d_c = min(s / rho, length)
    s = min(s, rho * d_c)
    y, z, x = p0[:, 1], p0[:, 2], p0[:, 0]
    depth = nose - y
    inside = (depth > -0.05) & (depth < d_c)      # points a hair ahead of the measured nose (float error, plate thickness) are pushed back with the nose
    u = np.clip(depth / d_c, 0.0, 1.0)
    p[:, 1] = np.where(inside, (nose - d_c) + (1.0 - u) * (d_c - s), y)
    prog = min(1.0, d_c / length)
    lobe = np.sin(np.pi * u)
    ripple = np.sin(11.0 * u + 3.0 * x)
    hood = (z > 0.62).astype(float)
    dz = prog * (0.30 * lobe * hood * (1.0 - 0.5 * u) + 0.03 * ripple * lobe) - 0.05 * prog * (1.0 - hood) * (1.0 - u)
    p[:, 2] = np.where(inside, z + dz, z)
    p[:, 0] = np.where(inside, x * (1.0 + 0.14 * prog * lobe), x)
    return p


FOLDS = 3                    # accordion folds of the crush rails inside the crushed zone
FOLD_AMPLITUDE = 0.085       # m: how far a fold swings up and down (the rail tube radius is 0.045 m)


def rail_fold(p0: np.ndarray, s: float, nose: float, length: float = CRUSH_LENGTH, rho: float = COMPACTION) -> np.ndarray:
    """The crush rails and the bumper beam: the same squeeze along the car as crush_map, plus an accordion: the rail buckles into alternating up and down folds that get deeper and
    tighter as the compression grows (a plain squeeze would only make the tube shorter, which cannot be seen). Points ahead of the crushed zone and behind it do not fold."""
    p = crush_map(p0, s, nose, length, rho)
    d_c = min(s / rho, length)
    if d_c <= 1e-9:
        return p
    depth = nose - p0[:, 1]
    inside = (depth > -0.05) & (depth < d_c)
    u = np.clip(depth / d_c, 0.0, 1.0)
    amp = FOLD_AMPLITUDE * min(1.0, d_c / 0.30)
    dz = amp * np.sin(2.0 * np.pi * FOLDS * u) * np.sin(np.pi * u) ** 0.6
    p[:, 2] = np.where(inside, p[:, 2] + dz, p[:, 2])
    return p


def wheel_y(y_wheel: float, s: float, nose: float, radius: float = 0.281, clearance: float = 0.02) -> float:
    """Front wheel position after a crush of stroke s: the tyre is rigid, so once the crushed nose line (nose - s) reaches the front of the tyre the wheel is pushed back with it
    (it never ends up in front of the crushed nose, i.e. never through the barrier)."""
    return min(y_wheel, nose - s - radius - clearance)


# ----------------------------------------------------------------------------- film timeline (v2: one continuous crumple crash, the rigid crash once, no split screen)
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CUES_FILE = Path(os.environ.get("EP04_CUES", ROOT / "examples" / "experiments" / "crumple-zone-real-cues.json"))
SLOW = 0.09                 # kept for old callers; the v2 film uses per-segment time warps below
FILM = os.environ.get("EP04_FILM", "preview")
T_CONTACT = LEAD_SIM / (V0_KMH / 3.6)       # simulated time of first contact (s)


@lru_cache(maxsize=None)
def recs() -> dict:
    return {k: simulate(k) for k in PROFILES}


def sample(rec: dict, t: float) -> dict:
    """Pose at simulated time t (s): linear interpolation of the 2000 Hz record, constant-speed run-up before t = 0, and constant-velocity continuation after the record ends."""
    v0, hz = rec["v0"], rec["hz"]
    if t <= 0.0:
        return {"d": v0 * t, "s": 0.0, "v": v0, "g": 0.0}
    x = t * hz
    n = len(rec["t"])
    if x >= n - 1:
        last = n - 1
        v = float(rec["v"][last])
        return {"d": float(rec["d"][last]) + v * (t - float(rec["t"][last])), "s": float(rec["s"][last]), "v": v, "g": 0.0}
    i = int(x)
    f = x - i
    return {k: float(rec[k][i] * (1 - f) + rec[k][i + 1] * f) for k in ("d", "s", "v", "g")}


def stop_time_after_contact(profile: str) -> float:
    return summary(recs()[profile])["stop_time_s"]


T_STOP = {k: stop_time_after_contact(k) for k in PROFILES}       # crumple ~0.087 s, rigid ~0.0055 s after contact
RATE_SHAPE = 0.6             # 0.75 would make the crush advance at a constant film speed; a smaller value keeps it a little faster at the start and slowing towards the stop
APPROACH_BLEND_S = 0.02      # simulated seconds before contact over which the run-up slows down to the crash time scale


def _smooth(x: float | np.ndarray):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def rate_fn(tp: np.ndarray, r0: float, approach_rate: float, ramp: tuple[float, float, float] | None) -> np.ndarray:
    """Film speed relative to real time as a function of simulated time since contact tp. Same function for both cars up to the rigid car's stop: the crash itself is
    shown at one time scale (a little faster near the start, slowing towards the stop so the stop is not rushed). ramp = (tp_a, tp_b, rate_after): after the rigid car has
    stopped the film speeds up again so that the bounce is seen at a readable speed."""
    tp = np.asarray(tp, float)
    x = np.clip(-tp / APPROACH_BLEND_S, 0.0, 1.0)
    pre = r0 + (approach_rate - r0) * _smooth(x)
    u = np.clip(tp / T_STOP["crumple"], 0.0, 1.0)
    post = r0 / (1.0 - RATE_SHAPE * u)
    r = np.where(tp < 0, pre, post)
    if ramp is not None:
        a, b, after = ramp[:3]
        w = _smooth((tp - a) / (b - a))
        r = np.exp(np.log(r) * (1 - w) + np.log(after) * w)
        if len(ramp) > 3:      # second step: the driver's lunge is over, the film speeds up again for the bounce
            c, d, after2 = ramp[3:6]
            w2 = _smooth((tp - c) / (d - c))
            r = np.exp(np.log(r) * (1 - w2) + np.log(after2) * w2)
    return r


@lru_cache(maxsize=None)
def _integrate(r0: float, approach_rate: float, ramp: tuple | None):
    tp = np.concatenate([np.linspace(-1.2, 0.9, 210001), np.linspace(0.9, 12.0, 11101)[1:]])      # fine near the crash, coarser for the long rebound
    rate = rate_fn(tp, r0, approach_rate, ramp)
    tau = np.concatenate([[0.0], np.cumsum(0.5 * (1 / rate[1:] + 1 / rate[:-1]) * np.diff(tp))])
    return tp, tau - float(np.interp(0.0, tp, tau))      # tau = film seconds relative to the moment of contact


def _approach_distance(r0: float, approach_rate: float, ramp, contact_film_s: float) -> float:
    """Distance to the barrier (m) at the first film frame when the contact lands contact_film_s into the segment."""
    tp, tau = _integrate(r0, approach_rate, ramp)
    tp_start = float(np.interp(-contact_film_s, tau, tp))      # tau is increasing with tp
    return -tp_start * (V0_KMH / 3.6)


@lru_cache(maxsize=None)
def solve_approach_rate(r0: float, approach_m: float, ramp, contact_film_s: float) -> float:
    """Film speed of the run-up (relative to real time) such that the car starts approach_m metres from the barrier and touches it contact_film_s into the segment."""
    lo, hi = r0 * 1.0001, 2.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        # a faster run-up covers more distance in the same film time
        if _approach_distance(r0, mid, ramp, contact_film_s) < approach_m:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


@lru_cache(maxsize=None)
def warp_table(r0: float, approach_m: float, ramp: tuple | None, contact_film_s: float):
    """(film seconds since the segment start, simulated seconds since contact): integrates dtau = dtp / rate. Contact lands exactly at contact_film_s."""
    ar = solve_approach_rate(r0, approach_m, ramp, contact_film_s)
    tp, tau = _integrate(r0, ar, ramp)
    return tau + contact_film_s, tp


def frame_time(frame: int) -> float:
    """Film frame (1-based) -> simulated time (s) since simulate()'s start."""
    seg = segment_at(frame)
    if "static_t" in seg:
        return seg["static_t"]
    tau = (frame - seg["first"]) / FPS
    taus, tp = warp_table(seg["r0"], seg["approach_m"], seg.get("ramp"), seg["contact_film_s"])
    return T_CONTACT + float(np.interp(tau, taus, tp))


def film_speed(frame: int) -> float:
    """How fast the film runs compared with real time at this frame (simulated seconds per film second); 1.0 = real time."""
    seg = segment_at(frame)
    if "static_t" in seg:
        return 0.0
    nxt = frame + 1 if frame < seg["last"] else frame
    prv = frame if frame < seg["last"] else frame - 1
    return (frame_time(nxt) - frame_time(prv)) * FPS


def pose(frame: int, panel: str | None = None) -> dict:
    """Simulated pose of the car shown in this frame: d (cabin advance), s (crush stroke), v, g."""
    seg = segment_at(frame)
    return sample(recs()[panel or seg["panels"][0]], frame_time(frame))


def nose_y(frame: int, panel: str | None = None) -> float:
    """World y of the front of the car (the crushed nose line, -LEAD_SIM + d - s): it is at 0 (the barrier face) from the first contact on."""
    ps = pose(frame, panel)
    return -LEAD_SIM + ps["d"] - ps["s"]


def first_contact_film_s(seg_id: str = "K") -> float:
    return next(s for s in SEGMENTS if s["id"] == seg_id)["contact_film_s"]


def _cues() -> dict:
    return json.loads(CUES_FILE.read_text())


def cue_start(prefix: str, nth: int = 0) -> float:
    hits = [c["start"] for c in _cues()["cues"] if c["text"].replace("\\N", " ").startswith(prefix)]
    return float(hits[nth])


def frame_of(seconds: float) -> int:
    """First film frame (1-based) of a spoken moment."""
    return int(round(seconds * FPS)) + 1


TARGET_S = float(_cues()["target_seconds"])
TOTAL_FRAMES = int(round(TARGET_S * FPS))
CABIN_BEAT = "quietly keeps its"      # first caption phrase of the cabin sentence
RIGID_BEAT = "and now a rigid"
RIGID_CONTACT_CUE = "almost instantly"
CLOSE_BEAT = "The front is meant"
HOOK_CONTACT_S = 0.45                         # first contact: the crash begins well inside the first 2 seconds
_F_CABIN, _F_RIGID, _F_CLOSE = frame_of(cue_start(CABIN_BEAT)), frame_of(cue_start(RIGID_BEAT)), frame_of(cue_start(CLOSE_BEAT))
# one crash time scale for both cars: the crumple car's crush (and so its stop) ends when the cabin sentence begins
R0 = float(T_STOP["crumple"] * (1.0 - RATE_SHAPE / 2.0) / ((_F_CABIN - 1) / FPS - HOOK_CONTACT_S - 0.35))
_RIGID_CONTACT_FILM = max(0.8, cue_start(RIGID_CONTACT_CUE) - cue_start(RIGID_BEAT))
SEGMENTS = [
    {"id": "K", "first": 1, "last": _F_RIGID - 1, "panels": ("crumple",), "layout": "full", "camera": "K", "r0": R0, "approach_m": 6.0,
     "contact_film_s": HOOK_CONTACT_S, "xray_keys": ()},
    {"id": "R", "first": _F_RIGID, "last": _F_CLOSE - 1, "panels": ("rigid",), "layout": "full", "camera": "R", "r0": R0, "approach_m": 8.0,
     "contact_film_s": _RIGID_CONTACT_FILM, "ramp": (T_STOP["rigid"] - 0.0006, T_STOP["rigid"] + 0.003, 0.08, 0.040, 0.046, 0.6), "xray_keys": ()},
    {"id": "C", "first": _F_CLOSE, "last": TOTAL_FRAMES, "panels": ("crumple",), "layout": "full", "camera": "C", "r0": R0, "approach_m": 0.0,
     "contact_film_s": 0.0, "static_t": 1.0, "xray_keys": ()},
]
assert SEGMENTS[0]["last"] + 1 == SEGMENTS[1]["first"] and SEGMENTS[1]["last"] + 1 == SEGMENTS[2]["first"]
SYNC_TOLERANCE_S = 0.4
SYNC_EVENTS = [("A car hits a wall", "the car touches the barrier as the bumper \"hits\" is spoken", frame_of(HOOK_CONTACT_S)),
               (RIGID_BEAT, "rigid-front car starts its approach", _F_RIGID), (RIGID_CONTACT_CUE, "rigid car touches the barrier", _F_RIGID + int(round(_RIGID_CONTACT_FILM * FPS))),
               (CLOSE_BEAT, "closing view of the deformed front and intact cabin", _F_CLOSE)]


def segment_at(frame: int) -> dict:
    for seg in SEGMENTS:
        if seg["first"] <= frame <= seg["last"]:
            return seg
    raise ValueError(frame)


def visible_panel(frame: int) -> str:
    return segment_at(frame)["panels"][0]


def visible_panels(frame: int) -> tuple[str, ...]:
    return segment_at(frame)["panels"]


def xray_factor(frame: int) -> float:
    """Ghost body factor 0..1 of this frame from the segment's keys ((film seconds since the segment start, factor), linear between keys)."""
    seg = segment_at(frame)
    keys = XRAY_KEYS.get(seg["id"], ())
    if not keys:
        return 0.0
    tau = (frame - seg["first"]) / FPS
    xs, ys = zip(*keys)
    return float(np.interp(tau, xs, ys))


def _tau(seconds: float, seg_id: str) -> float:
    seg = next(s for s in SEGMENTS if s["id"] == seg_id)
    return seconds - (seg["first"] - 1) / FPS


#: ghost-body factor keys per segment (film seconds since the segment start, factor): the scan line starts when the hidden rails are named and runs while the crash goes on
XRAY_KEYS: dict[str, tuple] = {
    "K": ((0.0, 0.0), (_tau(cue_start("as the hidden rails"), "K"), 0.0), (_tau(cue_start("as the hidden rails"), "K") + 1.8, 1.0)),
    "R": ((0.0, 0.0), (_tau(cue_start("It has almost nothing"), "R"), 0.0), (_tau(cue_start("It has almost nothing"), "R") + 1.2, 1.0)),
    "C": ((0.0, 0.0), (_tau(cue_start("but the cabin is not."), "C") - 1.0, 0.0), (_tau(cue_start("but the cabin is not."), "C") + 0.6, 1.0)),
}


#: cabin see-through factor 0..1 per segment: the front turns see-through first (XRAY_KEYS), the cabin follows so that the driver can be seen; at 0 the cabin stays solid
CABIN_XRAY_KEYS: dict[str, tuple] = {
    "K": ((0.0, 0.0), (_tau(cue_start("energy over a longer"), "K"), 0.0), (_tau(cue_start("energy over a longer"), "K") + 1.0, 1.0)),
    "R": ((0.0, 0.0), (_tau(cue_start("It has almost nothing"), "R"), 0.0), (_tau(cue_start("It has almost nothing"), "R") + 1.2, 1.0)),
    "C": ((0.0, 0.0), (_tau(cue_start("but the cabin is not."), "C"), 0.0), (_tau(cue_start("but the cabin is not."), "C") + 1.0, 1.0)),
}


def cabin_xray_factor(frame: int) -> float:
    seg = segment_at(frame)
    keys = CABIN_XRAY_KEYS.get(seg["id"], ())
    if not keys:
        return 0.0
    xs, ys = zip(*keys)
    return float(np.interp((frame - seg["first"]) / FPS, xs, ys))


def _ghost_start_frame() -> int:
    k = SEGMENTS[0]
    return next(f for f in range(k["first"], k["last"] + 1) if xray_factor(f) > 0.02)


SYNC_EVENTS.append(("as the hidden rails", "the scan line starts to turn the body see-through", _ghost_start_frame()))
