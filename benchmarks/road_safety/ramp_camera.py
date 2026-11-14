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
KEYS = (
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


def relative_path() -> list:
    keys = [cam.Key(t=k[0], position=k[1], aim=k[2], lens=k[3]) for k in KEYS]
    return cam.plan(keys, FPS)


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


def aim_point(states, t: float) -> tuple:
    """What the camera claims to look at, in the world, at film time t (the keyed aim point riding the truck)."""
    f = min(LAST_FRAME, FIRST_FRAME + int(round(t * FPS)))
    rel = relative_path()[f - FIRST_FRAME]
    return world_pose(rel, nose_y(states, f)).aim


def audit(states) -> "cam.Audit":
    path = world_path(states)
    limits = cam.Limits(max_speed=40.0, max_accel=120.0, max_aim_rate=120.0, max_hold_seconds=1.0, min_subject_visible=0.9)
    return cam.audit(path, FPS, subject=lambda t: aim_point(states, t), obstacles=(), limits=limits, moving_start=True)
