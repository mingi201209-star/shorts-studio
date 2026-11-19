"""EP.03 X-ray feasibility test: what is inside the CC0 sedan, can the body be made translucent, can a spring + damper be drawn between body and wheel and
follow the quarter-car simulation (spring length = body-to-wheel distance). A built-in, simplified suspension (the sedan has no suspension parts)."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.speed_bump import speed_bump_motion as sim  # noqa: E402
from benchmarks.speed_bump.speed_bump_timeline import Timeline  # noqa: E402

material, cube = base.material, base.cube


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames", type=str, default="40,95")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def spring(name, bottom, top, turns=7, radius=0.07, mat=None):
    """Helical spring as a beveled curve between two points (z up)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.011, 2
    sp = cu.splines.new("POLY")
    n = turns * 16
    sp.points.add(n)
    for i, p in enumerate(sp.points):
        t = i / n
        a = 2 * math.pi * turns * t
        z = bottom[2] + (top[2] - bottom[2]) * t
        p.co = (bottom[0] + radius * math.cos(a), bottom[1] + radius * math.sin(a), z, 1)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    if mat:
        ob.data.materials.append(mat)
    return ob


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    meshes = [o for o in root.children_recursive if o.type == "MESH"]
    print("XRAY_PARTS " + json.dumps({"count": len(meshes), "sample": sorted(o.name for o in meshes)[:70],
                                       "materials": sorted({m.name for o in meshes for m in o.data.materials if m})[:40]}), flush=True)
    print("XRAY_GEOMETRY " + json.dumps(geom), flush=True)
    scene = bpy.context.scene
    scene.render.engine, scene.cycles.device, scene.cycles.samples = "CYCLES", "CPU", 24
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 16
    scene.render.resolution_x, scene.render.resolution_y = 1080, 700
    scene.view_settings.view_transform, scene.view_settings.exposure = "Standard", -1.3
    scene.world = scene.world or bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.14, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy = 3.0
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, 10, -0.05), (12.0, 80, 0.1), road)
    yellow = material("Bump", (0.9, 0.62, 0.05), rough=0.5)
    b = sim.BUMPS["short"]
    pts = [(i / 40 * b["length"], b["height"] * math.sin(math.pi * i / 40)) for i in range(41)] + [(b["length"], 0.0)]
    bump = base.extruded_profile("Bump", pts, -1.4, 1.4, yellow)
    bump.rotation_euler = (0, 0, math.pi / 2)

    # translucent body: copy each material with low alpha; wheels/tyres stay solid
    wheel_names = set()
    for w in wheels.values():
        wheel_names.update(o.name for o in w["node"].children_recursive)
    seen = {}
    for o in meshes:
        if o.name in wheel_names:
            continue
        for i, m in enumerate(o.data.materials):
            if m is None:
                continue
            if m.name not in seen:
                c = m.copy()
                c.name = m.name + " xray"
                if c.use_nodes:
                    bsdf = c.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        bsdf.inputs["Alpha"].default_value = 0.22
                        # edge glow: a fresnel-weighted blue emission keeps the silhouette readable while the inside shows through
                        lw = c.node_tree.nodes.new("ShaderNodeLayerWeight")
                        lw.inputs["Blend"].default_value = 0.35
                        mul = c.node_tree.nodes.new("ShaderNodeMath")
                        mul.operation = "MULTIPLY"
                        mul.inputs[1].default_value = 3.0
                        c.node_tree.links.new(lw.outputs["Facing"], mul.inputs[0])
                        c.node_tree.links.new(mul.outputs[0], bsdf.inputs["Emission Strength"])
                        bsdf.inputs["Emission Color"].default_value = (0.25, 0.65, 1.0, 1.0)
                seen[m.name] = c
            o.data.materials[i] = seen[m.name]

    steel = material("Steel", (0.75, 0.76, 0.8), metal=0.9, rough=0.3)
    red = material("Spring", (1.0, 0.25, 0.1), rough=0.4, emission=0.6)
    cyan = material("Damper", (0.2, 0.8, 1.0), rough=0.4, emission=0.4)
    tl = Timeline(geom["wheelbase"])
    rec = tl.recs[("A", "short")]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens, cam.data.sensor_fit, cam.data.sensor_width = 42, "HORIZONTAL", 36
    live = []
    for f in [int(x) for x in args.frames.split(",")]:
        for ob in live:
            bpy.data.objects.remove(ob, do_unlink=True)
        live = []
        idx = min(int(f / 30.0 * 0.25 * 30 + 0.288 * 30), len(rec["t"]) - 1)
        y_front = float(rec["x"][idx])
        root.location = (0.0, y_front - geom["front_axle"], 0.0)
        body.location = (0, 0, float(0.5 * (rec["zf"][idx] + rec["zr"][idx])))
        body.rotation_euler = (float(rec["pitch"][idx]), 0, 0)
        for wkey, w in wheels.items():
            rz = float(rec["wf"][idx] if wkey.startswith("front") else rec["wr"][idx])
            w["node"].location = (w["base"].x, w["base"].y, w["base"].z + rz)
            w["node"].rotation_euler = (-(y_front - geom["front_axle"] + w["base"].y) / geom["tyre_radius"], 0, 0)
        bpy.context.view_layer.update()
        # spring + damper for the two near-side wheels (x > 0 side faces the camera): from a body mount above the wheel to the wheel hub
        for wkey, w in wheels.items():
            if w["base"].x < 0:
                continue
            hub = w["node"].matrix_world.translation
            mount = body.matrix_world @ Vector((w["base"].x - 0.05, w["base"].y, w["base"].z + 0.42))
            live.append(spring(f"spring {wkey}", (hub.x + 0.12, hub.y, hub.z + 0.05), (mount.x + 0.12, mount.y, mount.z), mat=red))
            bpy.ops.mesh.primitive_cylinder_add(radius=0.022, depth=1.0, location=((hub.x + mount.x) / 2 + 0.12, hub.y + 0.1, (hub.z + mount.z) / 2))
            rod = bpy.context.object
            rod.scale = (1, 1, max(0.05, (mount.z - hub.z)))
            rod.data.materials.append(cyan)
            live.append(rod)
        base.set_camera(cam, (6.2, y_front - 1.0, 0.95), (0.0, y_front - 1.0, 0.62))
        scene.render.filepath = str(args.out / f"xray_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("XRAY_SPRING " + json.dumps({"frame": f, "sim_zs_minus_zu_cm": round(100 * float(rec["zf"][idx]) - 100 * float(rec["wf"][idx]), 2),
              "drawn_hub_z": round(float(wheels["front_right"]["node"].matrix_world.translation.z), 3), "drawn_mount_z": round(float((body.matrix_world @ Vector((0, 0, wheels["front_right"]["base"].z + 0.42))).z), 3)}), flush=True)
        print("XRAY_FRAME " + json.dumps({"frame": f, "y_front": round(y_front, 3), "wheel_rise_cm": round(100 * float(rec["wf"][idx]), 2),
                                         "body_rise_cm": round(100 * float(0.5 * (rec["zf"][idx] + rec["zr"][idx])), 2)}), flush=True)


main()
