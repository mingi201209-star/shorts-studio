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
# Load the standalone motion modules without importing the package's optional
# production dependencies (Blender's bundled Python has no pydantic).
import importlib.util
import types
factory_name = "shorts_studio.factory"
sys.modules.setdefault("shorts_studio", types.ModuleType("shorts_studio"))
factory = types.ModuleType(factory_name)
factory.__path__ = [str(ROOT / "shorts_studio" / "factory")]
sys.modules[factory_name] = factory
for module_name in ("motion_recipes", "blender_motion_adapter"):
    qualified = f"{factory_name}.{module_name}"
    spec = importlib.util.spec_from_file_location(qualified, ROOT / "shorts_studio" / "factory" / f"{module_name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
BlenderMotionDriver = sys.modules[f"{factory_name}.blender_motion_adapter"].BlenderMotionDriver

p = argparse.ArgumentParser()
p.add_argument("--out", type=Path, required=True)
p.add_argument("--full-900", action="store_true", help="Render 900 frames at 1080x1920; demonstration, not final film")
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
    recipe = dict(kind=kind, object_id=root.name, start_frame=1 if args.full_900 else 2, end_frame=900 if args.full_900 else 8,
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
engines = {item.identifier for item in scene.render.bl_rna.properties["engine"].enum_items}
scene.render.engine = next((e for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE") if e in engines), "BLENDER_WORKBENCH")
scene.render.resolution_x = 1080 if args.full_900 else 640
scene.render.resolution_y = 1920 if args.full_900 else 360
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
proof = []
frames = range(1, 901) if args.full_900 else (1, 3, 5, 7, 9)
for frame in frames:
    motion = {driver.recipe["kind"]: driver.apply(frame) for driver in drivers}
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    path = args.out / f"motion_{frame:04d}.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    proof.append(dict(frame=frame, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), motion=motion))
active = [p for p in proof if (1 <= p["frame"] <= 900 if args.full_900 else 2 <= p["frame"] <= 8)]
if len({p["sha256"] for p in active}) < (50 if args.full_900 else len(active)):
    raise RuntimeError("active motion preview has insufficient unique frames")
if args.full_900 and len(proof) != 900:
    raise RuntimeError("900-frame render incomplete")
(args.out / "motion-proof.json").write_text(json.dumps(proof, indent=2))
print("MULTI_TOPIC_900_FRAME_RENDER_PASS" if args.full_900 else "MULTI_TOPIC_NATIVE_MOTION_PREVIEW_PASS", flush=True)
