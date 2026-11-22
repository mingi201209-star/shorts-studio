"""Opening ("hook") rules from the channel's own numbers (owner's Studio, analysed 2026-11-22).

What the data says: "viewed" (the share of viewers who did not swipe away) is decided in the first second or two, and the low-level
picture statistics (motion, brightness, colour, detail, loudness of the first 1.5 s) do not explain it: EP.13 (69.2 % viewed) has
less motion than EP.15 (13.7 %). What EP.13 and Road Signs (69.9 %) do have is ONE opening shot, held through the whole first line
(EP.13: 3.26 s), that shows the whole car and the road hardware in the middle of the strange event, readable at phone size. From
EP.14 on the openings followed the competitor research's "first cut by 1.5 s" and cut away at 1.3 s, from a close-up or abstract view
to a weaker one (a distant car, an empty road).

Rules (gate):
1. The opening shot is held until the second line starts, at least 2.0 s (or until line 2 if that comes sooner), at most 3.6 s.
2. During the first second the subject (the car, or the machine) is in frame and readable: at least 85 % of its projected box inside
   the picture, or, when it fills the picture (at least 70 % of the width), at least 60 % of it inside; and never less than 30 % of
   the width. An extreme close-up (EP.19 v1: one wheel filling the frame) fails: most of the car is outside the picture.
The renderers report the subject's projected box per frame ("subject_box": [x0, x1, y0, y1] in 0..1 view coordinates)."""
from __future__ import annotations


def project_box(scene, cam, matrix_world, lo, hi) -> list[float]:
    """The subject's local bounding box (lo, hi corners) projected into the camera view: [x0, x1, y0, y1] in 0..1 (Blender only)."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    pts = [matrix_world @ Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    uv = [world_to_camera_view(scene, cam, p) for p in pts]
    if any(p.z <= 0 for p in uv):                       # part of the subject is behind the camera: treat it as cut off
        return [-1.0, 2.0, -1.0, 2.0]
    xs, ys = [p.x for p in uv], [p.y for p in uv]
    return [round(min(xs), 4), round(max(xs), 4), round(min(ys), 4), round(max(ys), 4)]


def box_metrics(box: list[float]) -> tuple[float, float]:
    """(share of the box inside the picture, visible width as a share of the picture width)."""
    x0, x1, y0, y1 = box
    area = max(1e-9, (x1 - x0) * (y1 - y0))
    ix0, ix1, iy0, iy1 = max(0.0, x0), min(1.0, x1), max(0.0, y0), min(1.0, y1)
    inside = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0) / area
    return inside, max(0.0, ix1 - ix0)


def opening_rule(segs: list[dict], line2_start: float) -> list[str]:
    first_cut = segs[1]["t0"]
    lo = min(2.0, line2_start)
    if first_cut < lo - 1e-6 or first_cut > 3.6 + 1e-6:
        return [f"the opening shot lasts {first_cut:.2f} s (rule: hold it through the first line, {lo:.2f}-3.6 s)"]
    return []


def opening_hook(frames: list[dict], segs: list[dict], line2_start: float, fps: int, first_seconds: float = 1.0) -> dict:
    problems = opening_rule(segs, line2_start)
    worst_inside, worst_width, cut_off = 1.0, 1.0, []
    for fr in frames:
        if fr["frame"] >= first_seconds * fps:
            continue
        box = fr["parts"][0].get("subject_box")
        if box is None:
            problems.append(f"frame {fr['frame']}: no subject box in the telemetry")
            break
        inside, width = box_metrics(box)
        worst_inside, worst_width = min(worst_inside, inside), min(worst_width, width)
        if not (inside >= 0.85 or (inside >= 0.6 and width >= 0.7)):
            cut_off.append(fr["frame"])
    if cut_off:
        problems.append(f"the subject is cut off in the first second (frames {cut_off[0]}..{cut_off[-1]}; {worst_inside:.0%} of it in frame)")
    if worst_width < 0.30:
        problems.append(f"the subject is too small in the first second ({worst_width:.0%} of the width)")
    return {"status": "FAIL" if problems else "PASS", "problems": problems, "opening_shot_s": round(segs[1]["t0"], 2),
            "subject_in_frame_min": round(worst_inside, 3), "subject_width_min": round(worst_width, 3)}
