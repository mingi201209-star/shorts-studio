"""One continuous camera move for the opening of the runaway-ramp film (frames 1-285, the hook and tyres_sink shots).

The truck is the anchor: the camera is keyed *relative to the truck's nose* and carried along with it, so the truck
stays in frame while the road, the bed and the horizon stream past. The path is designed with cinematic_camera.plan
(smooth Hermite, rest at both ends) and audited with cinematic_camera.audit against the real simulated truck track.
Pure Python (no Blender), so the path can be checked before any render.
"""
from __future__ import annotations

from benchmarks.road_safety import cinematic_camera as cam
from benchmarks.road_safety import runaway_ramp_motion as motion

FPS = 30
FIRST_FRAME, LAST_FRAME = 1, 285          # the two shots this move replaces (hook 1-140, tyres_sink 141-285)
HOOK = (1, 140, -0.72, 3.2)               # frames, simulated seconds (same mapping as render_runaway_ramp.SIM_RANGE)
SINK = (141, 285, 3.2, 5.6)

# (film seconds, camera offset from the nose (x, along the truck, z), aim offset from the nose, lens mm)
KEYS_ROUND2 = (
    (0.00, (2.7, 18.0, 0.45), (0.2, 0.0, 0.9), 24.0),      # the established opening: ground level, head-on (kept)
    (0.80, (2.9, 3.5, 0.60), (0.3, -2.0, 1.2), 24.0),      # swept alongside the entrance as the truck arrives (kept)
    (2.00, (3.3, -1.5, 0.60), (1.05, -1.4, 0.5), 26.0),    # beside the front tyre as it bites (kept)
    (3.00, (6.5, 3.5, 1.30), (0.0, -4.0, 1.3), 26.0),      # pulled out and ahead: nose and the truck's side in one frame
    (4.67, (4.4, 7.0, 0.80), (0.2, -2.5, 1.2), 28.0),      # ahead of the truck looking back: its face large, stones thrown at the wheels
    (6.00, (4.6, 4.0, 0.80), (0.3, -1.0, 0.9), 26.0),      # low and close past the front: spray around the front tyre
    (7.00, (6.5, -2.0, 1.20), (0.3, -6.0, 1.1), 26.0),     # along the right side: the nose, several wheels and the body length
    (8.20, (7.0, -5.0, 1.60), (0.5, -9.0, 0.9), 26.0),     # easing back along the side toward the rear wheels
    (9.4667, (7.2, -7.5, 2.00), (0.8, -10.0, 0.8), 26.0),  # rear tandem seen from far enough out to show how it sits on the truck
)


RATE_EARLY, RATE_LATE = 0.84, 0.5         # simulated seconds per film second at the start / end of the move
BLEND_CENTRE, BLEND_WIDTH = 4.67, 3.0     # film seconds: where the playback rate eases from early to late


def _rate(t: float) -> float:
    """Simulated seconds per film second at film time t: a smooth ease instead of the old hard step at the shot cut."""
    u = min(1.0, max(0.0, (t - (BLEND_CENTRE - BLEND_WIDTH / 2)) / BLEND_WIDTH))
    e = u * u * (3.0 - 2.0 * u)
    return RATE_EARLY + (RATE_LATE - RATE_EARLY) * e


def sim_time(frame: int) -> float:
    """Simulated seconds at a film frame of the opening move. Frame 1 and frame 285 land on the same simulated
    moments as the two shots it replaces (-0.72 s and 5.6 s); in between the playback rate changes smoothly."""
    if not FIRST_FRAME <= frame <= LAST_FRAME:
        raise ValueError(f"frame {frame} is outside the opening move")
    n = LAST_FRAME - FIRST_FRAME
    total = HOOK[2] * -1 + SINK[3]          # 6.32 simulated seconds
    cum = [0.0]
    for i in range(n):
        cum.append(cum[-1] + _rate((i + 0.5) / FPS) / FPS)
    scale = total / cum[-1]                  # normalise so the end lands exactly on 5.6 s
    return HOOK[2] + cum[frame - FIRST_FRAME] * scale


def nose_y(states, frame: int) -> float:
    """Nose position (m along the bed) at a film frame. Continuous through the moment the tyres touch the gravel:
    `states[k]` is the state after k+1 frames, so a zero state is prepended (the old renderer jumped 0.83 m there)."""
    t = sim_time(frame)
    if t < 0.0:
        return motion.SPEED0 * t
    ext = [0.0] + [st["x"] for st in states]
    i = min(int(t * motion.FPS), len(ext) - 2)
    f = t * motion.FPS - i
    return ext[i] + (ext[i + 1] - ext[i]) * f


# Round 3: frames 190-285 only. Frames 1-189 keep the round-2 path exactly; the tail starts from the round-2 pose and velocity at frame 189.
JOIN_FRAME = 189
ROUND3_KEYS = (
    # (film seconds, camera offset from the nose (x, along the truck, z), aim offset from the nose, lens mm)
    # Camera stays inside the gravel bed (x <= 3.3) and near the nose, looking back along the right side at an oblique angle: the front-right
    # wheel, the stones it throws and the cab share the frame, and the trailer wall is seen edge-on instead of filling the picture.
    (6.800, (3.1, 2.8, 0.50), (1.0, -0.8, 0.40), 28.0),     # low, ahead of the front-right wheel: stones thrown, tyre sinking
    (7.633, (3.3, 2.2, 0.70), (1.0, -3.0, 0.50), 26.0),
    (8.567, (3.3, 1.4, 0.95), (1.0, -5.5, 0.40), 24.0),
    (9.4667, (3.3, 0.6, 1.20), (1.0, -8.0, 0.30), 22.0),    # still near the nose: wheels, gravel and body in one frame
)


def _round2_path() -> list:
    keys = [cam.Key(t=k[0], position=k[1], aim=k[2], lens=k[3]) for k in KEYS_ROUND2]
    return cam.plan(keys, FPS)


def _hermite_value(t, ts, vals, tangents):
    """Cubic Hermite through knots ts with the given tangents, evaluated at t (ts increasing)."""
    k = max(i for i in range(len(ts) - 1) if ts[i] <= t + 1e-12) if t < ts[-1] else len(ts) - 2
    h = ts[k + 1] - ts[k]
    u = (t - ts[k]) / h
    return cam._hermite(vals[k], vals[k + 1], tangents[k] * h, tangents[k + 1] * h, u)


def _track(ts, vals, v0):
    """Catmull-Rom tangents with a given start velocity and rest at the end."""
    n = len(vals)
    tg = [v0]
    for i in range(1, n - 1):
        tg.append((vals[i + 1] - vals[i - 1]) / (ts[i + 1] - ts[i - 1]))
    tg.append(0.0)
    return tg


def relative_path() -> list:
    """Truck-relative camera poses, one per frame 1-285: the round-2 path up to JOIN_FRAME, then the round-3 tail."""
    old = _round2_path()
    path = list(old[:JOIN_FRAME])
    j = JOIN_FRAME - 1                                   # index of the join frame
    t0 = old[j].t
    dt = 1.0 / FPS
    ts = [t0] + [k[0] for k in ROUND3_KEYS]
    comps = []
    for c in range(3):
        pv = [old[j].position[c]] + [k[1][c] for k in ROUND3_KEYS]
        av = [old[j].aim[c]] + [k[2][c] for k in ROUND3_KEYS]
        v_p = (old[j + 1].position[c] - old[j - 1].position[c]) / (2 * dt)       # velocity at the join, carried into the tail
        v_a = (old[j + 1].aim[c] - old[j - 1].aim[c]) / (2 * dt)
        comps.append((pv, _track(ts, pv, v_p), av, _track(ts, av, v_a)))
    lens = [old[j].lens] + [k[3] for k in ROUND3_KEYS]
    for f in range(JOIN_FRAME + 1, LAST_FRAME + 1):
        t = (f - 1) * dt
        pos = tuple(_hermite_value(t, ts, comps[c][0], comps[c][1]) for c in range(3))
        aim = tuple(_hermite_value(t, ts, comps[c][2], comps[c][3]) for c in range(3))
        k = max(i for i in range(len(ts) - 1) if ts[i] <= t + 1e-12) if t < ts[-1] else len(ts) - 2
        u = min(1.0, max(0.0, (t - ts[k]) / (ts[k + 1] - ts[k])))
        sm = u * u * (3 - 2 * u)
        ln = lens[k] + (lens[k + 1] - lens[k]) * sm
        path.append(cam.Pose(t, pos, aim, ln, False))
    return path


def junction_report(states) -> dict:
    """Step, speed and turn-rate change across JOIN_FRAME -> JOIN_FRAME + 1 (world coordinates, as the viewer sees it)."""
    import math
    path = world_path(states)
    j = JOIN_FRAME - 1
    def step(a, b): return cam._len(cam._sub(b.position, a.position))
    def turn(a, b):
        da = cam._unit(cam._sub(a.aim, a.position)); db = cam._unit(cam._sub(b.aim, b.position))
        return math.degrees(math.acos(max(-1.0, min(1.0, cam._dot(da, db)))))
    s_before, s_at, s_after = step(path[j - 1], path[j]) * FPS, step(path[j], path[j + 1]) * FPS, step(path[j + 1], path[j + 2]) * FPS
    r_before, r_at, r_after = turn(path[j - 1], path[j]) * FPS, turn(path[j], path[j + 1]) * FPS, turn(path[j + 1], path[j + 2]) * FPS
    return {"speed_mps": [round(s_before, 2), round(s_at, 2), round(s_after, 2)],
            "turn_dps": [round(r_before, 1), round(r_at, 1), round(r_after, 1)],
            "speed_change_across_join_mps": round(abs(s_at - s_before), 2),
            "turn_rate_change_across_join_dps": round(abs(r_at - r_before), 1),
            "lens": [round(path[j - 1].lens, 2), round(path[j].lens, 2), round(path[j + 1].lens, 2)]}


def world_pose(rel: "cam.Pose", ny: float) -> "cam.Pose":
    return cam.Pose(rel.t, (rel.position[0], rel.position[1] + ny, rel.position[2]),
                    (rel.aim[0], rel.aim[1] + ny, rel.aim[2]), rel.lens, rel.cut)


def world_path(states) -> list:
    rel = relative_path()
    return [world_pose(p, nose_y(states, FIRST_FRAME + i)) for i, p in enumerate(rel)]


TRUCK_BOX = ((-1.28, 1.28), (-14.8, 0.0), (0.0, 4.0))   # x, y (from the nose backwards), z of the truck's bounding box (m)


def truck_corners_in_frame(pose: "cam.Pose", ny: float) -> int:
    """How many of the truck's 8 bounding-box corners are inside the picture area (rows 0-1400) for this pose.
    Few corners means the viewer sees a fragment (a wheel, a wall); many means the truck's outline is readable."""
    n = 0
    for x in TRUCK_BOX[0]:
        for y in TRUCK_BOX[1]:
            for z in TRUCK_BOX[2]:
                px, row, depth = cam.project(pose, (x, y + ny, z))
                if depth > 0 and 0.0 <= px <= 1.0 and 0.0 <= row <= cam.PICTURE_ROWS[1]:
                    n += 1
    return n


def truck_width_fraction(pose: "cam.Pose", ny: float) -> float:
    """Horizontal extent (0..1 of the frame width, clipped to the frame) of the truck's projected bounding box."""
    xs = []
    for x in TRUCK_BOX[0]:
        for y in TRUCK_BOX[1]:
            for z in TRUCK_BOX[2]:
                px, row, depth = cam.project(pose, (x, y + ny, z))
                if depth > 0:
                    xs.append(px)
    if not xs:
        return 0.0
    return max(0.0, min(1.0, max(xs)) - max(0.0, min(xs)))


def silhouette_report(states, min_corners: int = 4) -> dict:
    """Share of frames showing at least `min_corners` truck corners, and the longest run without that."""
    path = world_path(states)
    ok = [truck_corners_in_frame(p, nose_y(states, FIRST_FRAME + i)) >= min_corners for i, p in enumerate(path)]
    run = longest = 0
    for v in ok:
        run = 0 if v else run + 1
        longest = max(longest, run)
    half = [v for i, v in enumerate(ok) if FIRST_FRAME + i >= 61]
    widths = [truck_width_fraction(p, nose_y(states, FIRST_FRAME + i)) for i, p in enumerate(path)]
    late = sorted(w for i, w in enumerate(widths) if FIRST_FRAME + i >= 61)
    return {"share_all": round(sum(ok) / len(ok), 3), "share_from_frame_61": round(sum(half) / len(half), 3),
            "longest_run_without_s": round(longest / FPS, 2), "min_corners": min_corners,
            "truck_width_fraction_median_from_61": round(late[len(late) // 2], 3),
            "truck_width_fraction_p10_from_61": round(late[len(late) // 10], 3)}


# ---------------------------------------------------------------------------------------------------------------
# What fills the picture (round 3): ray casting from the camera into a simplified scene (truck boxes, wheels, gravel bed, earth, sky)

TRAILER_BOX = ((-1.275, 1.275), (-13.65, -3.05), (1.10, 4.00))
CAB_BOX = ((-1.225, 1.225), (-3.10, -0.10), (1.05, 3.25))
CHASSIS_BOX = ((-1.05, 1.05), (-14.4, -0.4), (0.80, 1.10))
BUMPER_BOX = ((-1.25, 1.25), (-0.075, 0.275), (0.875, 1.225))
BED_HALF_WIDTH = 3.6
COMPOSITION_GRID = (36, 47)       # columns x rows over the picture area (1080 x 1400)
LABELS = ("trailer", "body", "wheel", "gravel", "earth", "sky")


def _box_hit(origin, dirs, box):
    """Distance along each ray to an axis-aligned box (inf where missed)."""
    import numpy as np
    t0 = np.full(dirs.shape[0], -np.inf)
    t1 = np.full(dirs.shape[0], np.inf)
    for axis in range(3):
        d = dirs[:, axis]
        with np.errstate(divide="ignore", invalid="ignore"):
            a = (box[axis][0] - origin[axis]) / d
            b = (box[axis][1] - origin[axis]) / d
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        parallel = np.abs(d) < 1e-12
        inside = (origin[axis] >= box[axis][0]) & (origin[axis] <= box[axis][1])
        lo = np.where(parallel, np.where(inside, -np.inf, np.inf), lo)
        hi = np.where(parallel, np.where(inside, np.inf, -np.inf), hi)
        t0, t1 = np.maximum(t0, lo), np.minimum(t1, hi)
    return np.where((t1 >= t0) & (t1 > 0), np.where(t0 > 0, t0, t1), np.inf)


def composition(pose: "cam.Pose", ny: float) -> dict:
    """Share of the picture area (rows 0-1400) showing each of LABELS for this pose (truck-relative coordinates, nose at the origin)."""
    import numpy as np
    from benchmarks.road_safety import runaway_ramp_motion as m
    nx, nr = COMPOSITION_GRID
    right, up, fwd = cam.basis(pose)
    fx = pose.lens / cam.SENSOR_WIDTH
    xs = (np.arange(nx) + 0.5) / nx
    rows = (np.arange(nr) + 0.5) / nr * cam.PICTURE_ROWS[1]
    X, R = np.meshgrid(xs, rows)
    dirs = (np.array(fwd)[None, :] + np.array(right)[None, :] * ((X.ravel() - 0.5) / fx)[:, None]
            + np.array(up)[None, :] * ((cam.PICTURE_CENTER_ROW - R.ravel()) / (fx * cam.FRAME[0]))[:, None])
    o = np.array(pose.position, dtype=float)
    best = np.full(dirs.shape[0], np.inf)
    label = np.full(dirs.shape[0], 5)             # sky
    with np.errstate(divide="ignore", invalid="ignore"):
        tg = -o[2] / dirs[:, 2]
    ground = np.where(tg > 0, tg, np.inf)
    hx = o[0] + dirs[:, 0] * ground
    hy = o[1] + dirs[:, 1] * ground
    on_bed = (np.abs(hx) <= BED_HALF_WIDTH) & (hy >= -ny)
    best = ground
    label = np.where(np.isfinite(ground), np.where(on_bed, 3, 4), 5)
    boxes = [(0, TRAILER_BOX), (1, CAB_BOX), (1, CHASSIS_BOX), (1, BUMPER_BOX)]
    for ax in m.AXLES_Y:
        for wx in m.WHEEL_X:
            boxes.append((2, ((wx - 0.17, wx + 0.17), (ax - m.WHEEL_R, ax + m.WHEEL_R), (0.0, 2 * m.WHEEL_R))))
    for lab, box in boxes:
        t = _box_hit(o, dirs, box)
        closer = t < best
        best = np.where(closer, t, best)
        label = np.where(closer, lab, label)
    return {name: round(float((label == i).mean()), 3) for i, name in enumerate(LABELS)}


def composition_report(states, first: int, last: int) -> dict:
    """Median shares over a frame range, and how many frames show a wheel, gravel and truck body together."""
    import numpy as np
    path = relative_path()          # truck-relative poses: the boxes are in truck coordinates
    rows = [composition(path[f - FIRST_FRAME], nose_y(states, f)) for f in range(first, last + 1)]
    med = {k: round(float(np.median([r[k] for r in rows])), 3) for k in LABELS}
    together = [r["wheel"] >= 0.02 and r["gravel"] >= 0.20 and (r["trailer"] + r["body"]) >= 0.15 for r in rows]
    return {"frames": len(rows), "median": med, "wheel_gravel_body_together": round(sum(together) / len(rows), 3),
            "max_trailer": round(max(r["trailer"] for r in rows), 3), "max_earth": round(max(r["earth"] for r in rows), 3)}


def aim_point(states, t: float) -> tuple:
    """What the camera claims to look at, in the world, at film time t (the keyed aim point riding the truck)."""
    f = min(LAST_FRAME, FIRST_FRAME + int(round(t * FPS)))
    rel = relative_path()[f - FIRST_FRAME]
    return world_pose(rel, nose_y(states, f)).aim


def audit(states) -> "cam.Audit":
    path = world_path(states)
    limits = cam.Limits(max_speed=40.0, max_accel=120.0, max_aim_rate=120.0, max_hold_seconds=1.0, min_subject_visible=0.9)
    return cam.audit(path, FPS, subject=lambda t: aim_point(states, t), obstacles=(), limits=limits, moving_start=True)
