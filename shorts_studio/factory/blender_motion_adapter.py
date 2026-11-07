"""Bind cross-topic motion recipes to actual Blender objects, without bpy at import.

Usage from a Blender scene builder:
    driver = BlenderMotionDriver(bpy.data.objects, recipe, fps=30)
    driver.capture_rest()
    for frame in frames:
        driver.apply(frame)
        scene.frame_set(frame)
        bpy.context.view_layer.update()

The object_id is an exact Blender object name; no guessed targets or overlays.
The calling scene remains responsible for visible framing and full render QA.
"""
from __future__ import annotations
from .motion_recipes import evaluate_motion, validate_motion_bindings

CHANNELS = {
    "vehicle_suspension": {"wheel_z": ("wheel_z", "location", 2),
                           "body_z": ("body_z", "location", 2),
                           "body_roll": ("body_roll", "rotation_euler", 0)},
    "aircraft_wing_flex": {"wing_tip_z": ("wing_tip_z", "location", 2)},
    "mechanical_rotation": {"angle_rad": ("angle_rad", "rotation_euler", 2)},
    "structure_sway": {"sway_angle_rad": ("sway_angle_rad", "rotation_euler", 1)},
}


class BlenderMotionDriver:
    """A named root object with exact named child controls.

    vehicle_suspension requires root/wheel_z, root/body_z, root/body_roll;
    other kinds require root/<single-channel>. Each control is an Empty or
    dedicated pivot. Never deform arbitrary mesh vertices.
    """

    def __init__(self, objects, recipe, fps=30):
        self.objects, self.recipe, self.fps = objects, dict(recipe), fps
        kind = self.recipe.get("kind")
        if kind not in CHANNELS:
            raise ValueError("unsupported motion kind")
        root = self.recipe.get("object_id")
        if not isinstance(root, str) or not root:
            raise ValueError("missing root")
        self.bindings = {channel: f"{root}/{channel}" for channel in CHANNELS[kind]}
        validate_motion_bindings(self.recipe, objects.keys())
        for target in self.bindings.values():
            if target not in objects:
                raise ValueError(f"missing explicit Blender motion control: {target}")
        self.rest = None

    def capture_rest(self):
        self.rest = {}
        for channel, name in self.bindings.items():
            _, attr, axis = CHANNELS[self.recipe["kind"]][channel]
            self.rest[channel] = float(getattr(self.objects[name], attr)[axis])

    def apply(self, frame):
        if self.rest is None:
            raise RuntimeError("capture_rest must precede animation")
        values = evaluate_motion(self.recipe, frame=frame, fps=self.fps)
        for channel, name in self.bindings.items():
            _, attr, axis = CHANNELS[self.recipe["kind"]][channel]
            getattr(self.objects[name], attr)[axis] = self.rest[channel] + values[channel]
        return values
