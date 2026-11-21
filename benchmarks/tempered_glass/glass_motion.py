"""EP.14 tempered glass (pure Python + numpy, no Blender): why a car side window explodes into little cubes.

Side window (the CC0 sedan's driver-side front glass, two pieces unfolded into one outline in (u, v) = (length along the door, height)):
tempered, so its surfaces are held in compression and its core in tension. An emergency hammer breaks through the surface at P0; a crack
front runs out from there at V_CRACK (about 1,500 m/s, nearly a mile per second) and the stored energy dices the pane into cells of
roughly CELL metres, which then burst outward and fall. Annealed (ordinary) glass hit the same way breaks into a few long radial shards.
Windshield: laminated (two sheets on a plastic interlayer), so a stone makes a star of radial cracks and rings, and nothing falls out.
Tempering: the pane leaves the furnace at about 640 C and is quenched with air; the surface stiffens first, the core cools later and
shrinks, leaving the surface in compression (about -100 MPa) and the core in tension (about +50 MPa, half of it for a parabolic
profile). Fully tempered glass is about four times as strong as annealed glass. Simplified explanation model, not a fracture
simulation: the crack pattern is a jittered grid and the pieces fly ballistically."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G = 9.81
V_CRACK = 1500.0                   # m/s, crack branching speed in soda-lime glass (0.93 mile per second)
MILE = 1609.344
CELL = 0.0135                      # m, dice size of the shattered pane
THICK = 0.004                      # m
STRENGTH_RATIO = 4.0               # fully tempered vs annealed
SURFACE_MPA, CORE_MPA = -100.0, 50.0
T_RELEASE = 0.0006                 # s after the hit when the diced pane starts to come apart (after the crack front has crossed it)

# window outline in (u, v): u = distance along the window from its rear edge (main pane along +y, then the angled front piece), v = z
MAIN_X0, MAIN_X1 = -0.5956, -0.5925        # x of the main pane at its rear (y 0.0539) and front (y 0.4916) edges
Y_REAR, Y_JOINT = 0.0539, 0.4916
FRONT_END = np.array([-0.6615, 0.7381])     # (x, y) of the front piece's leading corner
FRONT_LEN = float(np.hypot(FRONT_END[0] - MAIN_X1, FRONT_END[1] - Y_JOINT))
U_JOINT = Y_JOINT - Y_REAR
OUTLINE = np.array([(0.0, 0.9095), (U_JOINT + FRONT_LEN, 0.9095), (U_JOINT, 1.0865), (0.4066 - Y_REAR, 1.1475), (0.0, 1.1475)])
P0 = np.array([0.255, 1.02])                # where the hammer tip meets the glass
OUT_MAIN = np.array([-1.0, 0.007, 0.0])
OUT_FRONT = np.array([-0.963, -0.27, 0.0])
LEDGE_X, LEDGE_Z = -0.79, 0.85             # door top under the window: pieces cannot fall through it


def uv_to_world(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Car-frame points of window coordinates (vectorised)."""
    u, v = np.asarray(u, float), np.asarray(v, float)
    out = np.zeros(np.broadcast(u, v).shape + (3,))
    main = u <= U_JOINT
    f = np.clip(u / U_JOINT, 0, 1)
    out[..., 0] = np.where(main, MAIN_X0 + (MAIN_X1 - MAIN_X0) * f, 0.0)
    out[..., 1] = np.where(main, Y_REAR + u, 0.0)
    d = np.clip(u - U_JOINT, 0, None) / FRONT_LEN
    out[..., 0] = np.where(main, out[..., 0], MAIN_X1 + (FRONT_END[0] - MAIN_X1) * d)
    out[..., 1] = np.where(main, out[..., 1], Y_JOINT + (FRONT_END[1] - Y_JOINT) * d)
    out[..., 2] = v
    return out


def outward(u: np.ndarray) -> np.ndarray:
    u = np.asarray(u, float)
    return np.where((u <= U_JOINT)[..., None], OUT_MAIN, OUT_FRONT)


def _inside(p: np.ndarray, poly: np.ndarray = OUTLINE) -> np.ndarray:
    x, y = p[..., 0], p[..., 1]
    ins = np.zeros(x.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1)
        ins ^= cond
    return ins


def _clamp_to_outline(p: np.ndarray) -> np.ndarray:
    """Points outside the outline move to the nearest point on its boundary."""
    out = p.copy()
    bad = ~_inside(p)
    if not bad.any():
        return out
    q = p[bad]
    best = np.full(len(q), np.inf)
    proj = q.copy()
    n = len(OUTLINE)
    for i in range(n):
        a, b = OUTLINE[i], OUTLINE[(i + 1) % n]
        ab = b - a
        t = np.clip(((q - a) @ ab) / (ab @ ab), 0, 1)
        c = a + t[:, None] * ab
        d = np.linalg.norm(q - c, axis=1)
        m = d < best
        best[m], proj[m] = d[m], c[m]
    out[bad] = proj
    return out


@lru_cache(maxsize=None)
def cells() -> tuple:
    """Diced pane: quads of a jittered lattice inside the outline. Returns (corners (N, 4, 2), centres (N, 2))."""
    rng = np.random.default_rng(14)
    umin, vmin = OUTLINE.min(0) - CELL
    umax, vmax = OUTLINE.max(0) + CELL
    nu, nv = int((umax - umin) / CELL) + 2, int((vmax - vmin) / CELL) + 2
    gu, gv = np.meshgrid(umin + np.arange(nu) * CELL, vmin + np.arange(nv) * CELL, indexing="ij")
    lat = np.stack([gu, gv], -1) + rng.uniform(-0.32, 0.32, (nu, nv, 2)) * CELL
    quads = np.stack([lat[:-1, :-1], lat[1:, :-1], lat[1:, 1:], lat[:-1, 1:]], 2).reshape(-1, 4, 2)
    cen = quads.mean(1)
    keep = _inside(cen)
    quads = quads[keep]
    quads = _clamp_to_outline(quads.reshape(-1, 2)).reshape(-1, 4, 2)
    a, b = quads[:, 2] - quads[:, 0], quads[:, 3] - quads[:, 1]
    area = 0.5 * np.abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])          # 2D cross product (numpy 2 dropped 2D np.cross)
    keep = area > 0.15 * CELL * CELL
    return quads[keep], quads[keep].mean(1)


def crack_time(centres: np.ndarray) -> np.ndarray:
    return np.linalg.norm(centres - P0, axis=1) / V_CRACK


def crack_radius(t: float) -> float:
    return max(0.0, t) * V_CRACK


@lru_cache(maxsize=None)
def _launch() -> tuple:
    """Per-piece launch velocity (world), spin axis*rate, and start points (world)."""
    rng = np.random.default_rng(1414)
    quads, cen = cells()
    d = np.linalg.norm(cen - P0, axis=1)
    out = outward(cen[:, 0])
    speed = 1.3 + 2.2 * np.exp(-d / 0.09) + rng.uniform(0.0, 0.5, len(cen))      # the hammer pushes the middle hardest
    radial = np.zeros((len(cen), 3))
    radial[:, 1] = (cen[:, 0] - P0[0]) / (d + 1e-6)
    radial[:, 2] = (cen[:, 1] - P0[1]) / (d + 1e-6)
    vel = out * speed[:, None] + radial * rng.uniform(0.1, 0.6, len(cen))[:, None] + rng.normal(0, 0.12, (len(cen), 3))
    spin = rng.normal(0, 1, (len(cen), 3))
    spin /= np.linalg.norm(spin, axis=1, keepdims=True)
    rate = rng.uniform(15, 60, len(cen))
    start = uv_to_world(cen[:, 0], cen[:, 1])
    return vel, spin * rate[:, None], start


def piece_state(t: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centres (N, 3) and rotation vectors (N, 3) of the pieces at time t after the hit, plus a cracked flag per piece."""
    vel, spin, start = _launch()
    _, cen = cells()
    cracked = crack_time(cen) <= t
    tau = max(0.0, t - T_RELEASE)
    if tau <= 0:
        return start.copy(), np.zeros_like(start), cracked
    pos = start + vel * tau
    pos[:, 2] -= 0.5 * G * tau * tau
    # door top: a piece still over it cannot drop below it; past it, the road
    over = pos[:, 0] > LEDGE_X
    pos[:, 2] = np.where(over, np.maximum(pos[:, 2], LEDGE_Z), np.maximum(pos[:, 2], THICK))
    landed = (~over) & (pos[:, 2] <= THICK + 1e-6)
    # time on the ground: stop spinning and stay where it landed (first landing time from the ballistic path)
    rot_t = np.full(len(pos), tau)
    if landed.any():
        z0, vz = start[landed, 2], vel[landed, 2]
        tl = (vz + np.sqrt(vz * vz + 2 * G * np.maximum(z0 - THICK, 0.0))) / G
        rot_t[landed] = np.minimum(tau, tl)
        pos[landed, 0] = start[landed, 0] + vel[landed, 0] * rot_t[landed]
        pos[landed, 1] = start[landed, 1] + vel[landed, 1] * rot_t[landed]
        pos[landed, 2] = THICK
    rot = spin * rot_t[:, None]
    return pos, rot, cracked


def landed_fraction(t: float) -> float:
    pos, _, _ = piece_state(t)
    return float(np.mean(pos[:, 2] <= THICK + 1e-6))


# ---------------------------------------------------------------- annealed glass (ordinary): long radial shards
@lru_cache(maxsize=None)
def shards(n_rays: int = 11, rings=(0.03, 0.09, 0.2, 0.45)) -> tuple:
    """Polygons (u, v) of an annealed pane broken by the same hit: wedges between radial cracks, cut by a few rings."""
    rng = np.random.default_rng(7)
    ang = np.sort(rng.uniform(0, 2 * np.pi, n_rays))
    polys = []
    r_all = (0.0,) + tuple(rings)
    for i in range(n_rays):
        a0, a1 = ang[i], ang[(i + 1) % n_rays] + (2 * np.pi if i == n_rays - 1 else 0)
        for r0, r1 in zip(r_all[:-1], r_all[1:]):
            pts = [P0 + r0 * np.array([math.cos(a), math.sin(a)]) for a in (a0, a1)] if r0 > 0 else [P0]
            pts += [P0 + r1 * np.array([math.cos(a), math.sin(a)]) for a in (a1, a0)]
            poly = _clamp_to_outline(np.array(pts))
            if len(poly) >= 3 and np.ptp(poly[:, 0]) > 0.005 and np.ptp(poly[:, 1]) > 0.005:
                polys.append(poly)
    return tuple(polys)


def shard_aspect() -> float:
    """Median length / width of the annealed shards (long and thin = knife-like)."""
    r = []
    for p in shards():
        c = p - p.mean(0)
        s = np.linalg.svd(c, compute_uv=False)
        r.append(s[0] / max(s[-1], 1e-6))
    return float(np.median(r))


def cube_aspect() -> float:
    quads, _ = cells()
    r = []
    for q in quads:
        c = q - q.mean(0)
        s = np.linalg.svd(c, compute_uv=False)
        r.append(s[0] / max(s[-1], 1e-6))
    return float(np.median(r))


# ---------------------------------------------------------------- windshield (laminated): star of cracks, nothing falls out
WS_HIT = np.array([0.30, 0.0])      # (across, up-slope) on the windshield, metres from its centre


@lru_cache(maxsize=None)
def windshield_cracks() -> tuple:
    """Crack polylines in windshield plane coordinates (s across, w up the slope), each with its own start delay and length."""
    rng = np.random.default_rng(21)
    lines = []
    for k in range(9):
        a = 2 * np.pi * k / 9 + rng.uniform(-0.2, 0.2)
        L = rng.uniform(0.12, 0.30)
        pts = [WS_HIT.copy()]
        p, d = WS_HIT.copy(), np.array([math.cos(a), math.sin(a)])
        for _ in range(10):
            d = d + rng.normal(0, 0.12, 2)
            d /= np.linalg.norm(d)
            p = p + d * L / 10
            pts.append(p.copy())
        lines.append(np.array(pts))
    for r in (0.035, 0.075):
        ang = np.linspace(0, 2 * np.pi, 40)
        ring = WS_HIT + np.stack([np.cos(ang) * r * (1 + 0.15 * np.sin(5 * ang)), np.sin(ang) * r], -1)
        lines.append(ring)
    return tuple(lines)


def windshield_visible_length(t: float, line: np.ndarray) -> float:
    """Length of a crack line drawn by time t (cracks run at V_CRACK; the rings form behind the radial front)."""
    return max(0.0, t) * V_CRACK


# ---------------------------------------------------------------- emergency hammer (inside the car)
HAMMER_TIP_LOCAL = np.array([-0.085, 0.0, 0.33])     # hammer frame: shaft along +z from the (unseen) hand, head across x, steel tip at -x
HAMMER_PIVOT = None                                   # set below: the hand sits so the tip meets P0 on the inner face when the angle is 0


def _p0_world() -> np.ndarray:
    return uv_to_world(P0[0], P0[1]) + np.array([0.0015, 0.0, 0.0])      # inner face of the 3 mm pane


HAMMER_PIVOT = _p0_world() - HAMMER_TIP_LOCAL


def hammer_angle(t: float) -> float:
    """Back-swing (rad, about the car's y axis through the hand): 0.9 rad pulled back 0.35 s before the hit, 0 at the hit, then the tip
    follows through 3 cm as the pane gives way."""
    if t < 0:
        u = min(1.0, -t / 0.35)
        return 0.9 * u * u
    return -0.10 * min(1.0, t / 0.03)


def hammer_tip(t: float) -> np.ndarray:
    a = hammer_angle(t)
    c, s_ = math.cos(a), math.sin(a)
    x, _, z = HAMMER_TIP_LOCAL
    return HAMMER_PIVOT + np.array([x * c + z * s_, 0.0, -x * s_ + z * c])


# ---------------------------------------------------------------- strength test: a steel ball dropped on a tempered pane bounces off
BALL_R, BALL_DROP, RESTITUTION = 0.06, 1.0, 0.55
PANE_FLEX_MM, PANE_HZ, PANE_DAMP = 9.0, 26.0, 0.09


def ball_state(t: float) -> tuple[float, float]:
    """Height of the ball's bottom above the pane (m) and the pane's deflection at its centre (m, down positive), t seconds after release."""
    h, v, tt, hits = BALL_DROP, 0.0, 0.0, []
    dt = 1e-4
    while tt < t:
        v -= G * dt
        h += v * dt
        if h <= 0 and v < 0:
            hits.append((tt, -v))
            v = -v * RESTITUTION
            h = 0.0
        tt += dt
    flex = 0.0
    for th, vi in hits:
        tau = t - th
        w = 2 * math.pi * PANE_HZ
        flex += (PANE_FLEX_MM / 1000) * (vi / math.sqrt(2 * G * BALL_DROP)) * math.sin(w * tau) * math.exp(-PANE_DAMP * w * tau)
    return max(0.0, h), flex


# ---------------------------------------------------------------- ordinary (annealed) glass: the same window breaks into falling shards
@lru_cache(maxsize=None)
def _shard_launch() -> tuple:
    rng = np.random.default_rng(77)
    polys = shards()
    cen = np.array([p.mean(0) for p in polys])
    start = uv_to_world(cen[:, 0], cen[:, 1])
    out = outward(cen[:, 0])
    vel = out * rng.uniform(0.5, 1.4, len(polys))[:, None] + rng.normal(0, 0.15, (len(polys), 3))
    spin = rng.normal(0, 1, (len(polys), 3)) * rng.uniform(2, 7, len(polys))[:, None]
    return vel, spin, start


def shard_state(t: float) -> tuple[np.ndarray, np.ndarray]:
    vel, spin, start = _shard_launch()
    tau = max(0.0, t - T_RELEASE)
    pos = start + vel * tau
    pos[:, 2] -= 0.5 * G * tau * tau
    over = pos[:, 0] > LEDGE_X
    pos[:, 2] = np.where(over, np.maximum(pos[:, 2], LEDGE_Z), np.maximum(pos[:, 2], 0.02))
    return pos, spin * tau


# ---------------------------------------------------------------- windshield plane (car frame, from the CC0 mesh)
WS_CENTRE = np.array([0.0, 0.6914, 1.0498])
WS_UP = np.array([0.0, -0.6844, 0.7290])           # up the slope
WS_ACROSS = np.array([1.0, 0.0, 0.0])
WS_OUT = np.array([0.0, 0.7290, 0.6844])


def ws_point(s: np.ndarray, w: np.ndarray, lift: float = 0.0012) -> np.ndarray:
    s, w = np.asarray(s, float), np.asarray(w, float)
    return WS_CENTRE + s[..., None] * WS_ACROSS + w[..., None] * WS_UP + lift * WS_OUT


# ---------------------------------------------------------------- tempering
T_FURNACE = 640.0
PANE_SPEED = 0.55                     # m/s on the rollers; the pane's leading edge leaves the furnace mouth at t = 0
T_SET = 560.0                         # roughly where the glass stops flowing (the surface "hardens")


def temperatures(t: float) -> tuple[float, float]:
    """Surface and core temperature (C) t seconds into the quench: the surface drops fast, the core lags."""
    if t <= 0:
        return T_FURNACE, T_FURNACE
    ts = 20 + (T_FURNACE - 20) * math.exp(-t / 1.5)
    tc = 20 + (T_FURNACE - 20) * math.exp(-t / 6.0)
    return ts, tc


def stress(t: float) -> tuple[float, float]:
    """Built-up surface and core stress (MPa) during the quench: nothing until the core passes the set point after the surface."""
    ts, tc = temperatures(t)
    if tc >= T_SET:
        return 0.0, 0.0
    k = min(1.0, (T_SET - tc) / (T_SET - 300.0))
    return SURFACE_MPA * k, CORE_MPA * k


def glass_physics() -> dict:
    problems = []
    if abs(V_CRACK / MILE - 0.93) > 0.03:
        problems.append("crack speed is not 'nearly a mile per second'")
    quads, cen = cells()
    if not 400 <= len(quads) <= 1200:
        problems.append(f"{len(quads)} cubes (expected several hundred)")
    t_cross = float(crack_time(cen).max())
    if not t_cross < T_RELEASE:
        problems.append("the pane starts to fall apart before the crack front has crossed it")
    if cube_aspect() > 1.8:
        problems.append(f"cubes are not chunky (aspect {cube_aspect():.2f})")
    if shard_aspect() < 2.5:
        problems.append(f"annealed shards are not long and thin (aspect {shard_aspect():.2f})")
    ts, tc = temperatures(0.4)                         # early in the quench: the surface is set, the core is still soft
    if not ts < T_SET < tc:
        problems.append("the surface does not harden before the core")
    s, c = stress(60.0)
    if not (s < 0 < c and abs(s + 2 * c) < 1e-6):
        problems.append("final stresses are not surface compression balanced by core tension (parabolic profile)")
    if STRENGTH_RATIO != 4.0:
        problems.append("strength ratio is not 'about four times'")
    _, fl = ball_state(0.6)
    h_after, _ = ball_state(1.0)
    if not h_after > 0.05:
        problems.append("the ball does not bounce off the tempered pane")
    tip = hammer_tip(0.0)
    if np.linalg.norm(tip - _p0_world()) > 1e-6:
        problems.append("the hammer tip misses the impact point")
    lf = landed_fraction(1.2)
    if lf < 0.8:
        problems.append(f"only {lf:.0%} of the cubes are on the ground after 1.2 s")
    pos, _, _ = piece_state(1.2)
    if np.any((pos[:, 0] > LEDGE_X) & (pos[:, 2] < LEDGE_Z - 1e-6)):
        problems.append("a cube falls through the door")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "cubes": int(len(quads)), "crack_crosses_pane_ms": round(1000 * t_cross, 3),
            "crack_speed_mile_per_s": round(V_CRACK / MILE, 3), "cube_aspect": round(cube_aspect(), 2), "shard_aspect": round(shard_aspect(), 2),
            "shards": len(shards()), "landed_after_1_2s": round(lf, 2), "surface_core_mpa": [SURFACE_MPA, CORE_MPA]}


if __name__ == "__main__":
    import json
    print(json.dumps(glass_physics(), indent=1))
