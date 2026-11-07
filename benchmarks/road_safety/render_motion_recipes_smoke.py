"""Render a genuine multi-topic Blender motion smoke test (no source assets).

Run: blender -b -t 4 --python-exit-code 1 -P benchmarks/road_safety/render_motion_recipes_smoke.py -- --out /tmp/motion-smoke
Produces PNGs and a JSON proof. No upload, production approval or paid API.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shorts_studio.factory.blender_motion_adapter import BlenderMotionDriver

p = argparse.ArgumentParser()
p.add_argument("--out", type=Path, required=True)
args = p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
args.out.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def pivot(name, location, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    if parent:
        obj.parent = parent
    return obj

def cube(name, parent, scale):
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    ob.name = name
    ob.parent = parent
    ob.scale = scale
    return ob

scenes = [
    ("vehicle_suspension", ["wheel_z", "body_z", "body_roll"]),
    ("aircraft_wing_flex", ["wing_tip_z"]),
    ("mechanical_rotation", ["angle_rad"]),
    ("structure_sway", ["sway_angle_rad"]),
]
drivers = []
for i, (kind, channels) in enumerate(scenes):
    root = pivot(f"subject-{i}", ((i-1.5)*3, 0, 0))
    controls = {}
    parent = root
    for channel in channels:
        control = pivot(f"{root.name}/{channel}", (0, 0, 0), parent)
        controls[channel] = control
        parent = control
    cube(f"{kind}-visible-geometry", parent, (0.65, 0.20, 0.20))
    recipe = dict(kind=kind, object_id=root.name, start_frame=2, end_frame=8,
                  frequency_hz=3, amplitude=0.10)
    driver = BlenderMotionDriver(bpy.data.objects, recipe, fps=30)
    driver.capture_rest()
    drivers.append(driver)

bpy.ops.object.camera_add(location=(0, -16, 9))
camera = bpy.context.object
from mathutils import Vector
camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.camera = camera
bpy.ops.object.light_add(type="AREA", location=(0, -4, 10))
bpy.context.object.data.energy = 1700
bpy.context.object.data.size = 12
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
proof = []
for frame in (1, 3, 5, 7, 9):
    motion = {driver.recipe["kind"]: driver.apply(frame) for driver in drivers}
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    path = args.out / f"motion_{frame:04d}.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    proof.append(dict(frame=frame, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), motion=motion))
active = [p for p in proof if 2 <= p["frame"] <= 8]
if len({p["sha256"] for p in active}) != len(active):
    raise RuntimeError("active motion preview produced duplicate images")
(args.out / "motion-proof.json").write_text(json.dumps(proof, indent=2))
print("MULTI_TOPIC_NATIVE_MOTION_PREVIEW_PASS", flush=True)
