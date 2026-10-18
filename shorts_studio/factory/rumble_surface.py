"""Native Blender fixed-camera road-surface rumble strip motion preview.

One parametric road and tyre rig. This is a stylized, kinematic visual demonstration,
not a calibrated tire/suspension model and never upload-authorized by itself.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector


def arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--shot", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--persistent-data", action="store_true", help="Experimental Cycles acceleration; no visual changes")
    p.add_argument("--frames", type=int, default=None)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def material(name, color, metal=0, rough=0.55):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    s = m.node_tree.nodes.get("Principled BSDF")
    s.inputs["Base Color"].default_value = (*color, 1)
    s.inputs["Metallic"].default_value = metal
    s.inputs["Roughness"].default_value = rough
    return m


def cube(name, center, dimensions, mat, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    ob = bpy.context.object
    ob.name = name
    ob.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)
    if bevel:
        mod = ob.modifiers.new("Soft edge", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        ob.modifiers.new("Corner normals", "WEIGHTED_NORMAL")
    return ob


def cylinder(name, center, radius, depth, mat, n=96):
    bpy.ops.mesh.primitive_cylinder_add(vertices=n, radius=radius, depth=depth,
                                        location=center, rotation=(math.pi / 2, 0, 0))
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    mod = ob.modifiers.new("Rim chamfer", "BEVEL")
    mod.width = 0.03
    mod.segments = 2
    ob.modifiers.new("Corner normals", "WEIGHTED_NORMAL")
    return ob


def grooves_at(x, depth):
    # Raised surface = 0, recessed pocket = -depth. Multiple close samples
    # allow true depressions; do not render an elevated "speed bump".
    for i in range(-7, 8):
        d = abs(x - i * 0.55)
        if d < 0.105:
            return -depth
        if d < 0.14:
            return -depth * (0.14 - d) / 0.035
    return 0.0


def recessed_road(depth, asphalt, dark):
    coords = {-6.0, 6.0}
    for i in range(-7, 8):
        c = i * 0.55
        for delta in (-0.141, -0.140, -0.106, -0.105, 0, 0.105, 0.106, 0.140, 0.141):
            coords.add(c + delta)
    xs = sorted(x for x in coords if -6 <= x <= 6)
    verts = []
    for x in xs:
        z = grooves_at(x, depth)
        verts += [(x, -1.45, z), (x, 0.75, z)]
    faces = []
    for k in range(len(xs) - 1):
        faces.append((2*k, 2*k+2, 2*k+3, 2*k+1))
    mesh = bpy.data.meshes.new("Actual recessed road surface")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(asphalt)
    mesh.materials.append(dark)
    mesh.update()
    road = bpy.data.objects.new("Recessed transverse rumble strip surface", mesh)
    bpy.context.collection.objects.link(road)
    for k, p in enumerate(road.data.polygons):
        mid = (xs[k] + xs[k+1]) / 2
        p.material_index = 1 if grooves_at(mid, depth) < -depth*0.5 else 0
    cube("Surrounding asphalt", (0, 0, -0.23), (12, 5.4, 0.38), asphalt)
    cube("Roadway lane stripe", (0, 1.5, .003), (12, .055, .005), material("warm road stripe", (.78, .73, .48)))
    return road


def main():
    args = arg_parser()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf8"))
    shot = next((s for s in manifest["shots"] if s["shot_id"] == args.shot), None)
    if shot is None or shot["rig_id"] != "road_surface":
        raise ValueError("unknown shot or unsupported rig")
    parameters = shot.get("params", {})
    groove_mm = float(parameters.get("groove_depth_mm", 16))
    if not 5 <= groove_mm <= 24:
        raise ValueError("groove depth outside demonstration bounds")
    depth = groove_mm / 1000
    start_x = float(parameters.get("start_x", -2.6))
    end_x = float(parameters.get("end_x", 2.6))
    frames = args.frames or int(shot["frames"])
    if frames < 2 or frames > int(shot["frames"]):
        raise ValueError("frame subset must fit shot")
    sample = 6 if args.preview else 32
    width, height = (360, 640) if args.preview else (1080, 1920)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = sample
    sc.cycles.use_denoising = True
    sc.render.use_persistent_data = args.persistent_data
    sc.render.resolution_x = width
    sc.render.resolution_y = height
    sc.render.resolution_percentage = 100
    sc.render.threads_mode = "FIXED"
    sc.render.threads = 4
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"

    asphalt = material("coarse graphite asphalt", (.092, .098, .104), rough=.9)
    shadow = material("groove interior", (.025, .029, .033), rough=1.0)
    rubber = material("tire matte rubber", (.019, .024, .029), rough=.94)
    sidewall = material("rubber shoulder", (.05, .055, .06), rough=.9)
    aluminium = material("machined wheel", (.36, .43, .49), metal=.84, rough=.28)
    car = material("satin charcoal suspension", (.15, .21, .27), metal=.4, rough=.32)
    recessed_road(depth, asphalt, shadow)
    root = bpy.data.objects.new("Wheel rolling across shoulder", None)
    bpy.context.collection.objects.link(root)
    tire = cylinder("Pneumatic tire rubber", (0, 0, 0), .49, .40, rubber)
    tire.parent = root
    # Sidewalls and wheel disc rotate with the tire; no fake stationary wheel.
    rim = cylinder("Wheel rim", (0, -.225, 0), .30, .04, aluminium)
    rim.parent = root
    center = cylinder("Axle hub", (0, -.26, 0), .095, .06, sidewall)
    center.parent = root
    for j in range(10):
        a = j * math.tau / 10
        x = .23 * math.cos(a)
        z = .23 * math.sin(a)
        spoke = cube("Spoke", (x, -.258, z), (.24, .04, .053), aluminium, .015)
        spoke.rotation_euler[1] = -a
        spoke.parent = root
    fixed_car = cube("Wheel well and suspension housing", (0, .19, .91), (1.9, .80, .52), car, .13)
    # Parent the single wheel-well to the vehicle travel, not wheel spin.
    # This is an isolated wheel mechanism, not a whole automobile model.
    floor = material("world dark blue", (.067, .093, .13), rough=1)
    sc.world.color = (.08, .08, .10)
    cube("Surrounding ground", (0, 0, -.52), (14, 12, .08), floor)
    bpy.ops.object.camera_add(location=(2.25, -5.85, 4.1))
    camera = bpy.context.object
    direction = Vector((0, 0, .22)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 7.35
    sc.camera = camera
    bpy.ops.object.light_add(type="AREA", location=(-3.2, -2.2, 7))
    bpy.context.object.data.energy = 1250
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 5
    bpy.ops.object.light_add(type="AREA", location=(3.2, 1.4, 5))
    bpy.context.object.data.energy = 700
    bpy.context.object.data.size = 4

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    render_seconds = []
    for f in range(frames):
        t = f / (frames - 1)
        x = start_x + (end_x - start_x) * t
        tire_z = 0.49 + 0.011 * math.sin(t * 65) + grooves_at(x, depth) * .35
        root.location = (x, -.45, tire_z)
        root.rotation_euler[1] = (x - start_x) / .49
        fixed_car.location.x = x
        fixed_car.location.z = tire_z + .42
        sc.frame_set(f + 1)
        sc.render.filepath = str(out / f"frame_{f+1:04d}.png")
        start_time = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        render_seconds.append(round(time.perf_counter() - start_time, 3))
        paths.append(sc.render.filepath)
        print(f"NATIVE_FRAME_COMPLETE {f+1}/{frames}", flush=True)

    metadata = {
        "subject": "recessed rumble strip",
        "preview_only": bool(args.preview),
        "native_1080x1920_30fps": not args.preview,
        "actual_frames": len(paths),
        "requested_shot_frames": int(shot["frames"]),
        "groove_depth_mm": groove_mm,
        "fixed_camera": True,
        "samples": sample,
        "persistent_data": bool(args.persistent_data),
        "render_seconds_per_frame": render_seconds,
        "note": "Demonstration kinematics only, not impact or suspension measurements",
    }
    (out / "motion-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf8")
    print("RUMBLE_SURFACE_RENDER_DONE " + json.dumps(metadata), flush=True)


if __name__ == "__main__":
    main()
