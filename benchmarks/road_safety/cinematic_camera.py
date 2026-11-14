"""Cinematic Camera Director: plan a continuous camera move and audit it.

Pure Python (no Blender), unit-tested. Two jobs:

* plan(): turn a few key poses (position, aim point, lens) into one smooth
  per-frame path (cubic Hermite with Catmull-Rom tangents, zero velocity at the
  ends). The aim point may be a key position or ride a moving subject.
* audit(): measure a per-frame path against what the "Cinematic Reality Mode"
  plan calls a failure: a camera that stops or drifts without purpose, jumps
  between frames, flies inside an object, loses its subject, or whips too fast.

The audit is a measurement of the camera path in the simulated scene. It does
not say whether the picture is realistic or whether the move is good cinema.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

Vec = tuple[float, float, float]

SENSOR_WIDTH = 36.0          # mm, matches the renderers
PICTURE_ROWS = (0.0, 1400.0)  # rows of the 1080x1920 frame that carry picture (the rest is the caption band)
FRAME = (1080.0, 1920.0)


def _sub(a: Vec, b: Vec) -> Vec: return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a: Vec, b: Vec) -> Vec: return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a: Vec, k: float) -> Vec: return (a[0] * k, a[1] * k, a[2] * k)
def _dot(a: Vec, b: Vec) -> float: return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _len(a: Vec) -> float: return math.sqrt(_dot(a, a))
def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _unit(a: Vec) -> Vec:
    n = _len(a)
    return (0.0, 0.0, 0.0) if n == 0 else (a[0] / n, a[1] / n, a[2] / n)


@dataclass(frozen=True)
class Key:
    """A key pose at time t (s). `aim` is a fixed point, or None to follow the plan's subject track."""
    t: float
    position: Vec
    aim: Vec | None = None
    lens: float = 32.0
    cut_before: bool = False      # a declared hard cut: the audit allows a jump into this key


@dataclass
class Pose:
    t: float
    position: Vec
    aim: Vec
    lens: float
    cut: bool = False


def _hermite(p0, p1, m0, m1, u):
    u2, u3 = u * u, u * u * u
    return ((2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1)


def _tangents(ts: Sequence[float], vals: Sequence[float]) -> list[float]:
    n = len(vals)
    out = []
    for i in range(n):
        if i == 0 or i == n - 1:
            out.append(0.0)                      # come to rest at both ends
        else:
            out.append((vals[i + 1] - vals[i - 1]) / (ts[i + 1] - ts[i - 1]))
    return out


def plan(keys: Sequence[Key], fps: int, subject: Callable[[float], Vec] | None = None) -> list[Pose]:
    """One pose per frame from t = keys[0].t to keys[-1].t inclusive."""
    if len(keys) < 2:
        raise ValueError("a camera move needs at least two keys")
    ts = [k.t for k in keys]
    if any(b <= a for a, b in zip(ts, ts[1:])):
        raise ValueError("key times must increase")
    px, py, pz = ([k.position[i] for k in keys] for i in range(3))
    mx, my, mz = (_tangents(ts, v) for v in (px, py, pz))
    lens = [k.lens for k in keys]

    def aim_at(k: Key, t: float) -> Vec:
        if k.aim is not None:
            return k.aim
        if subject is None:
            raise ValueError("a key follows the subject but no subject track was given")
        return subject(t)

    n = int(round((ts[-1] - ts[0]) * fps)) + 1
    poses, seg = [], 0
    for f in range(n):
        t = ts[0] + f / fps
        while seg < len(keys) - 2 and t > ts[seg + 1] + 1e-9:
            seg += 1
        t0, t1 = ts[seg], ts[seg + 1]
        u = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        h = (t1 - t0)
        pos = (_hermite(px[seg], px[seg + 1], mx[seg] * h, mx[seg + 1] * h, u),
               _hermite(py[seg], py[seg + 1], my[seg] * h, my[seg + 1] * h, u),
               _hermite(pz[seg], pz[seg + 1], mz[seg] * h, mz[seg + 1] * h, u))
        a0, a1 = aim_at(keys[seg], t), aim_at(keys[seg + 1], t)
        s = u * u * (3 - 2 * u)
        aim = _add(_mul(a0, 1 - s), _mul(a1, s))
        ln = lens[seg] + (lens[seg + 1] - lens[seg]) * s
        cut = keys[seg + 1].cut_before and abs(t - t1) < 0.5 / fps
        poses.append(Pose(t, pos, aim, ln, cut))
    # a declared cut replaces the interpolation across that key with a jump: mark the first frame at/after it
    for i, k in enumerate(keys):
        if k.cut_before and i > 0:
            idx = min(range(n), key=lambda j: abs(poses[j].t - k.t))
            poses[idx].cut = True
    return poses


def basis(pose: Pose) -> tuple[Vec, Vec, Vec]:
    """Right, up and forward unit vectors of the camera (world z is up)."""
    fwd = _unit(_sub(pose.aim, pose.position))
    right = _unit(_cross(fwd, (0.0, 0.0, 1.0)))
    if _len(right) == 0:                        # looking straight up or down
        right = (1.0, 0.0, 0.0)
    up = _cross(right, fwd)
    return right, up, fwd


def project(pose: Pose, point: Vec) -> tuple[float, float, float]:
    """(x in 0..1 across the frame, row in 0..1920, depth in m) of a world point; depth <= 0 is behind the camera."""
    right, up, fwd = basis(pose)
    rel = _sub(point, pose.position)
    depth = _dot(rel, fwd)
    if depth <= 1e-6:
        return (0.5, 0.0, depth)
    fx = pose.lens / SENSOR_WIDTH              # focal length in frame widths
    x = 0.5 + fx * _dot(rel, right) / depth
    row = FRAME[1] / 2.0 - (fx * _dot(rel, up) / depth) * FRAME[0]
    return (x, row, depth)


@dataclass
class Sphere:
    centre: Vec
    radius: float
    name: str = "obstacle"


def _ray_hits_sphere(origin: Vec, target: Vec, s: Sphere) -> bool:
    d = _sub(target, origin)
    dist = _len(d)
    if dist == 0:
        return False
    u = _mul(d, 1.0 / dist)
    oc = _sub(origin, s.centre)
    b = _dot(oc, u)
    c = _dot(oc, oc) - s.radius ** 2
    disc = b * b - c
    if disc < 0:
        return False
    t = -b - math.sqrt(disc)
    return 0.0 < t < dist - 1e-6


@dataclass
class Limits:
    max_speed: float = 40.0            # m/s of the camera
    max_accel: float = 80.0            # m/s^2
    max_aim_rate: float = 120.0        # deg/s of the view direction
    max_hold_seconds: float = 1.0      # longest allowed stretch with (almost) no camera or aim motion
    still_speed: float = 0.05          # m/s below which the camera counts as still
    still_aim_rate: float = 0.5        # deg/s below which the aim counts as still
    min_subject_visible: float = 0.8   # fraction of frames with the subject in frame and unoccluded
    min_clearance: float = 0.15        # m from any obstacle surface
    max_jump: float = 5.0              # m between consecutive frames that is not a declared cut


@dataclass
class Audit:
    status: str
    problems: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def audit(poses: Sequence[Pose], fps: int, subject: Callable[[float], Vec] | None = None,
          obstacles: Sequence[Sphere] = (), limits: Limits = Limits()) -> Audit:
    problems: list[str] = []
    n = len(poses)
    speeds, aim_rates = [0.0], [0.0]
    for a, b in zip(poses, poses[1:]):
        step = _len(_sub(b.position, a.position))
        if step > limits.max_jump and not b.cut:
            problems.append(f"t={b.t:.2f}s: camera jumps {step:.1f} m between frames without a declared cut")
        speeds.append(0.0 if b.cut else step * fps)
        da = _unit(_sub(a.aim, a.position))
        db = _unit(_sub(b.aim, b.position))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, _dot(da, db)))))
        aim_rates.append(0.0 if b.cut else ang * fps)
    accel = [0.0] + [abs(speeds[i] - speeds[i - 1]) * fps if not poses[i].cut else 0.0 for i in range(1, n)]
    if max(speeds) > limits.max_speed:
        problems.append(f"camera speed {max(speeds):.1f} m/s exceeds {limits.max_speed}")
    if max(accel) > limits.max_accel:
        problems.append(f"camera acceleration {max(accel):.1f} m/s^2 exceeds {limits.max_accel}")
    if max(aim_rates) > limits.max_aim_rate:
        problems.append(f"aim turns {max(aim_rates):.0f} deg/s, above {limits.max_aim_rate}")
    # purposeless stillness: a long hold with no camera and no aim motion
    run, longest = 0, 0
    for s, r in zip(speeds, aim_rates):
        run = run + 1 if (s < limits.still_speed and r < limits.still_aim_rate) else 0
        longest = max(longest, run)
    if longest / fps > limits.max_hold_seconds:
        problems.append(f"camera holds still for {longest / fps:.2f} s (limit {limits.max_hold_seconds})")
    # obstacles
    worst = float("inf")
    for p in poses:
        for s in obstacles:
            worst = min(worst, _len(_sub(p.position, s.centre)) - s.radius)
    if obstacles and worst < limits.min_clearance:
        problems.append(f"camera comes within {worst:.2f} m of an obstacle surface (min {limits.min_clearance})")
    # subject visibility
    visible = None
    if subject is not None:
        ok = 0
        for p in poses:
            target = subject(p.t)
            x, row, depth = project(p, target)
            in_frame = depth > 0 and 0.03 <= x <= 0.97 and PICTURE_ROWS[0] + 20 <= row <= PICTURE_ROWS[1] - 20
            blocked = any(_ray_hits_sphere(p.position, target, s) for s in obstacles)
            ok += 1 if (in_frame and not blocked) else 0
        visible = ok / n
        if visible < limits.min_subject_visible:
            problems.append(f"the subject is in frame and unoccluded in only {visible:.0%} of frames "
                            f"(needs {limits.min_subject_visible:.0%})")
    metrics = {"frames": n, "max_speed_mps": round(max(speeds), 2), "max_accel_mps2": round(max(accel), 2),
               "max_aim_rate_dps": round(max(aim_rates), 1), "longest_hold_s": round(longest / fps, 2),
               "min_clearance_m": None if not obstacles else round(worst, 3),
               "subject_visible_fraction": None if visible is None else round(visible, 3)}
    return Audit("FAIL" if problems else "PASS", problems, metrics)
