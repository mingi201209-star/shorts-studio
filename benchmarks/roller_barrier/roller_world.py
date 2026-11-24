"""EP.26 world layout (pure numpy): a two-lane mountain road (3.6 m lanes, yellow centre line) cut into a hillside, with the rolling
barrier along its right (downhill) edge, in roller_motion's frame. Just after the hero bend the road runs along +y with its centre
line at x = 0 and the barrier face at x = X_FACE. Before the bend the road comes in straight at 25 degrees; the car drives along its
lane there and does not make the sharp left bend, so it meets the barrier at 25 degrees (the crash-test angle) just past the bend.
Further away the road winds on (more bends) for the aerial shots. Distances along the road are arc lengths of the centre line; along
the barrier, of the rollers' axis line, with s = 0 at y = 0 on the hero straight, so roller k sits at s = (k + 0.5) * pitch, where
roller_motion puts it (k = floor(y / pitch))."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from benchmarks.roller_barrier import roller_motion as rm

LANE = 3.6
HALF = LANE                              # road half width (two lanes)
AXIS_OFF = rm.X_FACE + rm.ROLL_R         # the rollers' axes, from the centre line (right side)
R_HERO = 10.0                            # the hero bend's centre-line radius (m): a sharp left bend of 25 degrees
ANG = rm.ANGLE0
STEP = 0.5
TREE_CLEAR = (6.0, -12.5)                # tree crowns stay beyond these signed distances (the bank below the barrier, the rock cut)
# (kind, length or angle in degrees, radius): before the hero bend, in driving order, ending with the straight that leads into it
BEFORE = [("straight", 120.0, 0.0), ("arc", 60.0, 45.0), ("straight", 95.0, 0.0)]
AFTER = [("straight", 85.0, 0.0), ("arc", -55.0, 40.0), ("straight", 70.0, 0.0), ("arc", 75.0, 32.0), ("straight", 160.0, 0.0)]


def _hero_end_y() -> float:
    """y of the hero bend's end (on x = 0) so that the incoming road's lane-centre line is the car's approach line."""
    x0, y0, psi = rm.start_pose()
    u = np.array([math.sin(psi), math.cos(psi)])
    n = np.array([math.cos(psi), -math.sin(psi)])                    # right normal of the approach
    centre_pt = np.array([x0, y0]) - LANE / 2 * n                    # the road's centre line is half a lane to the left of the car
    # bend start S = C + R (cos a, -sin a), C = (-R, yE); S must lie on the centre line through centre_pt along u
    sx = -R_HERO + R_HERO * math.cos(ANG)
    # (S - centre_pt) . n = 0  ->  (sx - cx) n_x + (yE - R sin a - cy) n_y = 0
    return float(centre_pt[1] + R_HERO * math.sin(ANG) - (sx - centre_pt[0]) * n[0] / n[1])


def _run(start, heading, pieces, step=STEP):
    """Sample a centre line from a start point and heading (radians, clockwise from +y) through pieces; returns points, headings."""
    pts, hs = [np.array(start, float)], [heading]
    p, h = np.array(start, float), heading
    for kind, a, r in pieces:
        if kind == "straight":
            n = max(1, int(round(a / step)))
            for _ in range(n):
                p = p + (a / n) * np.array([math.sin(h), math.cos(h)])
                pts.append(p.copy())
                hs.append(h)
        else:
            turn = math.radians(a)                                       # + = right turn (heading grows)
            length = abs(turn) * r
            n = max(2, int(round(length / step)))
            for _ in range(n):
                h0 = h
                h = h + turn / n
                hm = 0.5 * (h0 + h)
                p = p + (length / n) * np.array([math.sin(hm), math.cos(hm)])
                pts.append(p.copy())
                hs.append(h)
    return np.array(pts), np.array(hs)


@lru_cache(maxsize=None)
def centre_line() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dense centre line in driving order: points (n, 2), headings (n,), arc length s (n,) with s = 0 at the hero bend's end."""
    ye = _hero_end_y()
    e = np.array([0.0, ye])
    after_p, after_h = _run(e, 0.0, AFTER)
    hero_back, hero_h = _run(e, math.pi, [("arc", 25.0, R_HERO)])    # the left bend driven backwards: heading grows from 180
    start = hero_back[-1]
    before_rev = [(k, a, r) for k, a, r in reversed(BEFORE)]
    back_p, back_h = _run(start, hero_h[-1], [(k, -a if k == "arc" else a, r) for k, a, r in before_rev])
    pts = np.vstack([back_p[::-1], hero_back[::-1][1:], after_p[1:]])
    hs = np.concatenate([(back_h[::-1] + math.pi), (hero_h[::-1][1:] + math.pi), after_h[1:]])
    hs = (hs + math.pi) % (2 * math.pi) - math.pi
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    i_e = len(back_p) - 1 + len(hero_back) - 1
    s -= s[i_e]
    return pts, hs, s


def normals(hs: np.ndarray) -> np.ndarray:
    """Right-hand normals for headings (clockwise from +y)."""
    return np.stack([np.cos(hs), -np.sin(hs)], 1)


def offset_line(off: float) -> np.ndarray:
    pts, hs, _ = centre_line()
    return pts + off * normals(hs)


@lru_cache(maxsize=None)
def barrier_axis() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The rollers' axis line (points, headings, arc length with s = 0 at y = 0 on the hero straight)."""
    pts, hs, _ = centre_line()
    ax = pts + AXIS_OFF * normals(hs)
    seg = np.linalg.norm(np.diff(ax, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    i0 = int(np.argmin(np.abs(ax[:, 1]) + 1e3 * (np.abs(ax[:, 0] - AXIS_OFF) > 1e-3)))
    s -= s[i0] - ax[i0, 1]                                              # s = y on the hero straight
    return ax, hs, s


def roller_stations(k0: int, k1: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Axis positions (n, 2), headings and indices for rollers k0..k1-1 (k at s = (k + 0.5) * pitch)."""
    ax, hs, s = barrier_axis()
    ks = np.arange(k0, k1)
    ss = (ks + 0.5) * rm.ROLL_PITCH
    ss = ss[(ss >= s[0]) & (ss <= s[-1])]
    ks = np.round(ss / rm.ROLL_PITCH - 0.5).astype(int)
    x = np.interp(ss, s, ax[:, 0])
    y = np.interp(ss, s, ax[:, 1])
    h = np.interp(ss, s, np.unwrap(hs))
    return np.stack([x, y], 1), h, ks


def k_range() -> tuple[int, int]:
    _, _, s = barrier_axis()
    return int(math.ceil(s[0] / rm.ROLL_PITCH)), int(math.floor(s[-1] / rm.ROLL_PITCH))


def signed_offset(p: np.ndarray, chunk: int = 4000) -> tuple[np.ndarray, np.ndarray]:
    """Signed distance of points (n, 2) from the centre line (+ to the right, the downhill side) and the arc length there."""
    pts, hs, s = centre_line()
    nr = normals(hs)
    p = np.asarray(p, float)
    d_out, s_out = np.empty(len(p)), np.empty(len(p))
    for a in range(0, len(p), chunk):
        q = p[a:a + chunk]
        d2 = ((q[:, None, :] - pts[None, :, :]) ** 2).sum(-1)
        i = d2.argmin(1)
        d_out[a:a + chunk] = ((q - pts[i]) * nr[i]).sum(1)
        s_out[a:a + chunk] = s[i]
    return d_out, s_out


def lane_check() -> dict:
    """The car's approach runs along the middle of its lane on the incoming road; its first contact is on the hero straight."""
    problems = []
    for t in np.linspace(-3.5, -0.4, 32):
        p = rm.pose(float(t))
        d, _ = signed_offset(np.array([[p["x"], p["y"]]]))
        if abs(d[0] - LANE / 2) > 0.05:
            problems.append(f"t={t:.2f}: the car is {d[0]:.2f} m from the centre line (lane middle {LANE / 2})")
            break
    ye = _hero_end_y()
    first_k = min(rm.crash("roller")["spun"])
    if (first_k + 0.5) * rm.ROLL_PITCH < ye - 1.2:
        problems.append(f"the first roller hit (k={first_k}) is more than 1.2 m back on the bend")
    for t in np.linspace(0.6, 6.5, 30):
        p = rm.pose(float(t))
        d, _ = signed_offset(np.array([[p["x"], p["y"]]]))
        if not 0.4 < d[0] < 3.2:
            problems.append(f"t={t:.2f}: after the crash the car is {d[0]:.2f} m from the centre line")
            break
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "hero_bend_end_y": round(ye, 3)}


def smooth_noise(a, b, seed=0.0):
    return (0.5 * np.sin(0.21 * a + 0.7 + seed) * np.sin(0.17 * b + 1.1 * seed) + 0.3 * np.sin(0.6 * a + 1.3 * b + 2.0 + seed)
            + 0.2 * np.sin(1.7 * a - 0.9 * b + 4.0 + 2 * seed))


def ground_z(d, x, y):
    """Height of the land at signed distance d from the road's centre line (+ downhill side)."""
    z = np.full(d.shape, -0.03)
    r = d > 4.9
    dd = d[r] - 4.9
    u = np.clip((dd - 260.0) / 700.0, 0.0, 1.0)
    z[r] = -0.03 - 95.0 * (1.0 - np.exp(-dd / 95.0)) + 300.0 * u * u * (3 - 2 * u)      # down into the valley, up the mountain across it
    left = d < -5.0
    dl = -d[left] - 5.0
    z[left] = -0.03 + np.where(dl < 7.0, 1.45 * dl, 10.12 + 130.0 * (1.0 - np.exp(-(dl - 7.0) / 260.0)))
    amp = np.clip((np.abs(d) - 7.0) / 45.0, 0.0, 1.0)
    z += amp * (6.0 * smooth_noise(x * 0.12, y * 0.12, 1.0) + 2.0 * smooth_noise(x * 0.5, y * 0.5, 3.0))
    far = np.clip((np.abs(d) - 90.0) / 260.0, 0.0, 1.0)
    z += far * (45.0 * smooth_noise(x * 0.008, y * 0.008, 2.0) + 15.0 * smooth_noise(x * 0.025, y * 0.025, 4.0))
    cut = np.clip((-d - 5.2) / 1.0, 0.0, 1.0) * np.clip((13.0 + d) / 1.5, 0.0, 1.0)
    z += cut * 0.25 * smooth_noise(x * 4.0, y * 4.0, 5.0)
    return z
