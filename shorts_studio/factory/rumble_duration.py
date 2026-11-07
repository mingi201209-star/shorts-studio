"""Opt-in duration and cut validation, isolated from SHA-pinned native timelines."""
import math


def expected_frame_count(seconds, fps=30):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("invalid episode duration")
    if isinstance(fps, bool) or not isinstance(fps, int) or fps <= 0:
        raise ValueError("invalid fps")
    frames = seconds * fps
    if not math.isclose(frames, round(frames), abs_tol=1e-7):
        raise ValueError("duration does not align to a whole frame")
    return int(round(frames))


def progressive_cuts(ends, roles, *, total_frames=900):
    if (type(total_frames) is not int or total_frames < 30
            or not isinstance(ends, list) or not ends or len(ends) != len(roles)
            or any(type(n) is not int for n in ends)
            or ends[-1] != total_frames or ends[0] < 30
            or any(b-a < 30 for a,b in zip(ends, ends[1:]))):
        raise ValueError("invalid progressive native shot coverage")
    return list(zip(ends, roles))
