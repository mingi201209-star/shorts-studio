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
    (0.00, (2.7, 18.0, 0.45), (0.2, 0.0, 0.9), 24.0),     # the established opening: ground level, head-on
    (0.80, (2.9, 3.5, 0.60), (0.3, -2.0, 1.2), 24.0),     # swept alongside the entrance as the truck arrives
    (2.00, (3.3, -1.5, 0.60), (1.05, -1.4, 0.5), 26.0),   # beside the front tyre as it bites
    (4.00, (3.4, -5.0, 0.70), (1.05, -6.0, 0.45), 28.0),  # gliding rearward along the sinking wheels
    (6.00, (3.4, -8.5, 1.00), (1.05, -9.5, 0.45), 30.0),
    (8.00, (3.3, -11.0, 2.20), (1.0, -12.0, 0.3), 30.0),
    (9.4667, (3.3, -12.0, 3.60), (1.0, -12.2, 0.2), 30.0),  # rising over the rear tandem
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


def aim_point(states, t: float) -> tuple:
    """What the camera claims to look at, in the world, at film time t (the keyed aim point riding the truck)."""
    f = min(LAST_FRAME, FIRST_FRAME + int(round(t * FPS)))
    rel = relative_path()[f - FIRST_FRAME]
    return world_pose(rel, nose_y(states, f)).aim


def audit(states) -> "cam.Audit":
    path = world_path(states)
    limits = cam.Limits(max_speed=40.0, max_accel=120.0, max_aim_rate=120.0, max_hold_seconds=1.0, min_subject_visible=0.9)
    return cam.audit(path, FPS, subject=lambda t: aim_point(states, t), obstacles=(), limits=limits, moving_start=True)
