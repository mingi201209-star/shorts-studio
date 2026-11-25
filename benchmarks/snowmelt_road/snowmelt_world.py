"""EP.31 world (pure Python + numpy), shared by the renderer, the timeline, the sound and the gates: a street in a snow-country town
(Nagaoka style: two-storey houses with snow on the roofs, covered sidewalks, utility poles) running along +y, its centre line at
x = 0. Nozzles sit in the centre line every NOZZLE_PITCH m and throw low fans of water to both sides; a car keeps left (heading -y
it drives at x = +LANE_X); snow falls everywhere. Under the street: the supply main under the centre line fed by a well at Y_WELL
that reaches the water-bearing gravel deep down. All lengths in metres, times in seconds."""
from __future__ import annotations

import math

import numpy as np

from benchmarks.snowmelt_road import snowmelt_motion as sm

ROAD_HALF = 3.5                      # two 3.5 m lanes
GUTTER = 0.5                         # concrete gutter strip with grates beyond the road edge
WALK = 2.2                           # covered sidewalk (gangi) in front of the houses
FRONT = ROAD_HALF + GUTTER + WALK    # house fronts at |x| = 6.2
Y0, Y1 = -160.0, 220.0               # the modelled street
CROSS_Y = (-70.0, 48.0, 150.0)       # side streets (snow-covered)
CROSS_HALF = 3.2
NOZZLE_Y = np.arange(-120.0, 196.0, sm.NOZZLE_PITCH)
WET_HALF = 2.7                       # the jets keep this much of the road clear and wet

# under the street (section shots): the well, the main and the layers
Y_WELL = -28.5
Z_WELL_TOP = -0.4                    # the casing ends in a pit under a cover in the centre line
Z_MAIN = -0.9
R_CASING, R_MAIN, R_RISER = 0.22, 0.10, 0.025               # (the casing drawn a little wider than life)
Z_SOIL_BOT = -12.0                   # sand and soil above it (rides down when the ground sinks)
Z_AQ_TOP, Z_AQ_BOT = -44.0, -58.0    # the water-bearing gravel the well draws from (clay and silt above it)
Z_SCREEN = (-56.5, -46.0)            # the slotted part of the casing in the gravel
Z_PUMP = -54.0
Z_DEEP = -260.0
SINK_MAX = 2.2                       # how far the ground drops in the subsidence shot (drawn larger than life)

# the newer design: a window of road where the asphalt is shown see-through over a grid of warm pipes
PIPE_Y = (8.0, 26.0)
PIPE_Z = -0.07
PIPE_PITCH = 0.32
R_HEAT = 0.022

# the car
LANE_X = 1.75
CAR_V = 7.0                          # 25 km/h in the snow
CAR_T_REF, CAR_Y_REF = 100.0, 24.0   # where the car is at story time 100 s (the opening)

G = 9.81
JET_YAWS = (-30.0, -4.0, 22.0)
DROPS = 34                           # droplets drawn along each jet


def car_y(t: float) -> float | None:
    """The car's reference point (y) at story time t, or None when it is off the modelled street."""
    y = CAR_Y_REF - CAR_V * (t - CAR_T_REF)
    return y if Y0 + 12.0 < y < Y1 - 12.0 else None


def jet_table() -> np.ndarray:
    """Per nozzle and jet: (side, speed, elevation, yaw, phase); deterministic. Shape (n_nozzles, 6, 5)."""
    rng = np.random.default_rng(3101)
    out = np.zeros((len(NOZZLE_Y), 2 * len(JET_YAWS), 5))
    for k in range(len(NOZZLE_Y)):
        j = 0
        for side in (-1.0, 1.0):
            for yaw in JET_YAWS:
                out[k, j] = (side, rng.uniform(3.2, 4.8), math.radians(rng.uniform(20.0, 34.0)), math.radians(yaw + rng.uniform(-8, 8)), rng.uniform())
                j += 1
    return out


JETS = jet_table()


def jet_reach() -> float:
    """Farthest any jet throws water across the road (m)."""
    v, el = JETS[..., 1], JETS[..., 2]
    return float((v * v * np.sin(2 * el) / G * np.abs(np.cos(JETS[..., 3]))).max())


def droplets(t: float, y_lo: float, y_hi: float, sides=(-1.0, 1.0), sink: float = 0.0):
    """Droplets of the jets of the nozzles with y_lo <= y <= y_hi at story time t: positions (n, 3), velocities (n, 3), age share (n,).
    Each jet's droplets run along its arc (flight time T) at evenly spread phases, spreading a little as they fly."""
    ks = np.nonzero((NOZZLE_Y >= y_lo) & (NOZZLE_Y <= y_hi))[0]
    if len(ks) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0)
    J = JETS[ks]                                                      # (k, 6, 5)
    keep = np.isin(J[..., 0], np.asarray(sides))
    side, v0, el, yaw, ph = (J[..., i][..., None] for i in range(5))
    vh, vz = v0 * np.cos(el), v0 * np.sin(el)
    T = 2 * vz / G
    seed = np.sin((np.arange(DROPS)[None, None, :] + 1.0) * 12.9898 + ph * 78.233) * 43758.5453
    jit = (seed - np.floor(seed)) - 0.5
    i = (np.arange(DROPS)[None, None, :] + 0.8 * jit) / DROPS          # droplets unevenly spaced: the stream breaks up
    u = np.mod(i + t / T + ph, 1.0)                                   # share of the flight
    tau = u * T
    spread = 0.16 * u * u + 0.02 * u
    x = side * (vh * tau * np.cos(yaw)) + spread * jit
    y = NOZZLE_Y[ks][:, None, None] + vh * tau * np.sin(yaw) + spread * np.roll(jit, 3, axis=-1)
    z = np.maximum(0.03 + vz * tau - 0.5 * G * tau * tau + 0.5 * spread * np.roll(jit, 7, axis=-1), 0.004) - sink
    vx = np.broadcast_to(side * vh * np.cos(yaw), x.shape)
    vy = np.broadcast_to(vh * np.sin(yaw), x.shape)
    vzz = vz - G * tau
    m = np.broadcast_to(keep[..., None], x.shape)
    pos = np.stack([x[m], y[m], z[m]], axis=1)
    vel = np.stack([vx[m], vy[m], vzz[m]], axis=1)
    return pos, vel, u[m]


def splashes(t: float, y_lo: float, y_hi: float, sides=(-1.0, 1.0), sink: float = 0.0, age_max: float = 0.3) -> np.ndarray:
    """Where the jets' droplets came down in the last age_max seconds (the water film rings there): (n, 3) of x, y, age."""
    ks = np.nonzero((NOZZLE_Y >= y_lo) & (NOZZLE_Y <= y_hi))[0]
    if len(ks) == 0:
        return np.zeros((0, 3))
    J = JETS[ks]
    keep = np.isin(J[..., 0], np.asarray(sides))
    side, v0, el, yaw, ph = (J[..., i][..., None] for i in range(5))
    vh, vz = v0 * np.cos(el), v0 * np.sin(el)
    T = 2 * vz / G
    seed = np.sin((np.arange(DROPS)[None, None, :] + 1.0) * 12.9898 + ph * 78.233) * 43758.5453
    jit = (seed - np.floor(seed)) - 0.5
    i = (np.arange(DROPS)[None, None, :] + 0.8 * jit) / DROPS
    u = np.mod(i + t / T + ph, 1.0)
    age = u * T                                                       # time since this droplet slot last came down
    x = side * (vh * T * np.cos(yaw)) + 0.18 * jit
    y = NOZZLE_Y[ks][:, None, None] + vh * T * np.sin(yaw) + 0.18 * np.roll(jit, 3, axis=-1)
    m = np.broadcast_to(keep[..., None], x.shape) & (age < age_max)
    return np.stack([x[m], y[m], age[m]], axis=1)


# --- falling snow ----------------------------------------------------------------------------------------------------------------------
def _flake_table(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.column_stack([rng.uniform(size=n), rng.uniform(size=n), rng.uniform(size=n), rng.uniform(0.75, 1.3, n),
                            rng.uniform(0.04, 0.22, n), rng.uniform(0.25, 0.8, n), rng.uniform(0, 2 * np.pi, n), rng.uniform(size=n)])


NEAR = _flake_table(2600, 311)
FAR = _flake_table(5200, 312)
MACRO = _flake_table(500, 313)
NEAR_BOX = (14.0, 14.0, 9.0)
FAR_BOX = (90.0, 90.0, 34.0)
MACRO_BOX = (2.4, 2.4, 2.4)
WIND_X = 0.35                         # light drift across the street (m/s)


def surface_z(x: np.ndarray) -> np.ndarray:
    """Height where a flake stops: the road (it lands in the water film), else the snow on the gutter, sidewalks and banks."""
    return np.where(np.abs(x) < ROAD_HALF, 0.0, 0.25)


def flakes(t: float, near_c, far_c, sink: float = 0.0, macro_c=None):
    """Snowflakes at story time t in two boxes (one round a point just in front of the camera, one larger and further out), anchored
    to the world so they fall past the camera rather than with it; close-ups add a dense small box of big wet flakes. Returns (pos (n,3), size (n,), near mask (n,)) for the flakes
    still in the air, and the landing spots (m,2) of near flakes that met the wet road in the last 0.45 s (ripples)."""
    out_p, out_s, out_n, rip = [], [], [], []
    layers = [(NEAR, near_c, NEAR_BOX, True), (FAR, far_c, FAR_BOX, False)]
    if macro_c is not None:
        layers.append((MACRO, macro_c, MACRO_BOX, "macro"))
    for tab, c, box, near in layers:
        ux, uy, ph, v, amp, fq, sp, sz = tab.T
        Lx, Ly, H = box
        z_top = c[2] + H / 2
        fall = np.mod(v * t + ph * H, H)                              # how far below the box top
        z = z_top - fall
        sway = amp * np.sin(2 * np.pi * fq * t + sp)
        x0 = Lx * ux + WIND_X * (t - fall / v) + sway
        y0 = Ly * uy + 0.6 * amp * np.cos(2 * np.pi * fq * t + sp)
        x = c[0] - Lx / 2 + np.mod(x0 - (c[0] - Lx / 2), Lx)
        y = c[1] - Ly / 2 + np.mod(y0 - (c[1] - Ly / 2), Ly)
        surf = surface_z(x) - sink
        air = z > surf
        size = (0.006 + 0.006 * sz) if near == "macro" else (0.003 + 0.005 * sz) if near else (0.008 + 0.010 * sz)
        out_p.append(np.column_stack([x[air], y[air], z[air]]))
        out_s.append(size[air])
        out_n.append(np.full(int(air.sum()), bool(near)))
        if near:
            age = (surf - z) / v
            hit = (~air) & (age < 0.45) & (np.abs(x) < WET_HALF)
            rip.append(np.column_stack([x[hit], y[hit], age[hit]]))
    return np.vstack(out_p), np.concatenate(out_s), np.concatenate(out_n), (np.vstack(rip) if rip else np.zeros((0, 3)))


def subside(u: float) -> float:
    """Share of the drop shown at share u of the subsidence shot (eased; complete by 85 % of the shot)."""
    x = min(1.0, max(0.0, (u - 0.05) / 0.8))
    return x * x * (3 - 2 * x)
