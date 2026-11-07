"""Reusable, explicit visual motion recipes for Shorts Studio.

No Blender dependency. A shot must declare its phenomenon and object binding;
never infer motion from arbitrary narration or silently animate unrelated objects.
These are explanatory kinematics, not physically calibrated simulations.
"""
from __future__ import annotations
import math

SUPPORTED = ("vehicle_suspension", "aircraft_wing_flex", "mechanical_rotation", "structure_sway")


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def evaluate_motion(recipe: dict, *, frame: int, fps: int = 30) -> dict:
    if not isinstance(recipe, dict) or type(frame) is not int or frame < 1:
        raise ValueError("invalid motion recipe/frame")
    if type(fps) is not int or fps <= 0:
        raise ValueError("invalid fps")
    kind = recipe.get("kind")
    if kind not in SUPPORTED:
        raise ValueError("unknown motion kind; do not fake a visual")
    allowed = {"kind", "start_frame", "end_frame", "frequency_hz", "amplitude", "phase", "lag", "object_id"}
    if set(recipe) - allowed:
        raise ValueError("unknown motion parameter")
    obj = recipe.get("object_id")
    if not isinstance(obj, str) or not obj.strip():
        raise ValueError("explicit object_id required")
    start = recipe.get("start_frame", 1)
    end = recipe.get("end_frame")
    if type(start) is not int or start < 1 or type(end) is not int or end < start:
        raise ValueError("explicit valid start/end required")
    freq = _number(recipe.get("frequency_hz"), "frequency_hz")
    amp = _number(recipe.get("amplitude"), "amplitude")
    phase = _number(recipe.get("phase", 0.0), "phase")
    lag = _number(recipe.get("lag", 0.65), "lag")
    if not 0 < freq <= fps / 2 or not 0 < amp <= 0.25 or not 0 <= lag <= math.pi:
        raise ValueError("unsafe or aliased animation parameters")
    active = start <= frame <= end
    t = (frame - start) / fps
    wave = math.sin(2 * math.pi * freq * t + phase) if active else 0.0
    delayed = math.sin(2 * math.pi * freq * t + phase - lag) if active else 0.0
    if kind == "vehicle_suspension":
        return {"object_id": obj, "wheel_z": amp * (1 + wave) if active else 0.0,
                "body_z": amp * 0.6 * delayed, "body_roll": amp * 0.4 * delayed}
    if kind == "aircraft_wing_flex":
        return {"object_id": obj, "wing_tip_z": amp * wave}
    if kind == "mechanical_rotation":
        return {"object_id": obj, "angle_rad": 2 * math.pi * freq * t if active else 0.0}
    return {"object_id": obj, "sway_angle_rad": amp * wave}


def validate_motion_bindings(recipe: dict, available_object_ids) -> None:
    obj = recipe.get("object_id") if isinstance(recipe, dict) else None
    if obj not in available_object_ids:
        raise ValueError("motion target absent from scene; fail closed")
