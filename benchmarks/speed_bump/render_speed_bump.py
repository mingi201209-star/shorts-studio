"""EP.03 speed bumps: preview renderer (Blender). Two identical primitive cars, same speed, same bump height; only the bump length differs.
Poses come from speed_bump_motion (assumed car, not calibrated). Slow motion is a property of the shot (SLOW), not of the physics."""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.speed_bump import speed_bump_motion as sim  # noqa: E402

material, cube = base.material, base.cube
SLOW = 0.25            # film plays the simulation at 1/4 speed in the comparison shot
LANE_Y = {"short": 0.0, "hump": 3.4}
R = 0.32               # tyre radius (m)
BODY_Z0 = 0.30


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames", type=str, required=True, help="comma list of film frames of the comparison shot")
    p.add_argument("--width", type=int, default=360)
    p.add_argument("--height", type=int, default=640)
    p.add_argument("--samples", type=int, default=7)
    p.add_argument("--t0", type=float, default=0.0, help="sim time (s) shown at film frame 0")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def build_car(name, paint):
    root = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(root)
    body = bpy.data.objects.new(name + " body", None)
    bpy.context.collection.objects.link(body)
    body.parent = root
    black = material(name + " glass", (0.02, 0.03, 0.04), rough=0.1)
    rubber = material(name + " rubber", (0.025, 0.025, 0.025), rough=0.9)
    hub = material(name + " hub", (0.7, 0.7, 0.72), metal=0.8, rough=0.3)
    parts = [cube(name + " lower", (0, 0, 0.30), (4.4, 1.8, 0.55), paint),
             cube(name + " cabin", (-0.2, 0, 0.78), (2.4, 1.55, 0.50), black),
             cube(name + " roof", (-0.2, 0, 1.04), (2.1, 1.5, 0.06), paint)]
    for ob in parts:
        ob.parent = body
        mod = ob.modifiers.new("Bevel", "BEVEL")
        mod.width, mod.segments = 0.05, 2
    wheels = {}
    for key, (wx, wy) in {"fl": (1.35, -0.82), "fr": (1.35, 0.82), "rl": (-1.35, -0.82), "rr": (-1.35, 0.82)}.items():
        bpy.ops.mesh.primitive_cylinder_add(radius=R, depth=0.24, location=(0, 0, 0), rotation=(math.pi / 2, 0, 0))
        w = bpy.context.object
        w.name = f"{name} wheel {key}"
        w.data.materials.append(rubber)
        bpy.ops.mesh.primitive_cylinder_add(radius=R * 0.55, depth=0.26, location=(0, 0, 0), rotation=(math.pi / 2, 0, 0))
        h = bpy.context.object
        h.data.materials.append(hub)
        h.parent = w
        node = bpy.data.objects.new(f"{name} wheel node {key}", None)
        bpy.context.collection.objects.link(node)
        node.parent = root
        w.parent = node
        wheels[key] = (node, w, wx)
    return root, body, wheels


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.4

    scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.4, -0.9), 38.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    key = bpy.context.object
    key.data.energy, key.data.angle = 3.4, 0.03
    key.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()

    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, 1.7, -0.05), (80, 7.4, 0.1), road)
    verge = material("Verge", (0.22, 0.2, 0.14), rough=1.0)
    cube("Verge near", (0, -3.2, -0.06), (80, 2.4, 0.1), verge)
    cube("Verge far", (0, 6.6, -0.06), (80, 2.4, 0.1), verge)
    paint_white = material("Line", (0.8, 0.8, 0.78), rough=0.6)
    cube("Centre line", (0, 1.7, 0.002), (80, 0.12, 0.004), paint_white)
    yellow = material("Bump paint", (0.9, 0.62, 0.05), rough=0.5)
    for key_, bump in sim.BUMPS.items():
        n = 40
        pts = [(i / n * bump["length"], bump["height"] * math.sin(math.pi * i / n)) for i in range(n + 1)]
        profile = pts + [(bump["length"], 0.0)]
        base.extruded_profile(f"Bump {key_}", profile, LANE_Y[key_] - 1.4, LANE_Y[key_] + 1.4, yellow)

    paints = {"short": material("Car A", (0.12, 0.28, 0.65), metal=0.3, rough=0.3),
              "hump": material("Car B", (0.12, 0.28, 0.65), metal=0.3, rough=0.3)}   # identical paint: same car
    recs = {k: sim.simulate(b) for k, b in sim.BUMPS.items()}
    cars = {k: build_car(f"Car {k}", paints[k]) for k in sim.BUMPS}

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam_data.lens, cam_data.sensor_fit, cam_data.sensor_width = 40, "HORIZONTAL", 36

    result = []
    for f in [int(s) for s in args.frames.split(",")]:
        t_sim = args.t0 + f / 30.0 * SLOW
        info = {"frame": f, "sim_time": round(t_sim, 4)}
        for k, (root, body, wheels) in cars.items():
            rec = recs[k]
            idx = min(int(t_sim * sim.FPS), len(rec["t"]) - 1)
            x_front, zf, zr = rec["x"][idx], rec["zf"][idx], rec["zr"][idx]
            wf, wr = rec["wf"][idx], rec["wr"][idx]
            wb = sim.CAR["wheelbase"]
            root.location = (x_front - wb / 2, LANE_Y[k], 0.0)
            body.location = (0, 0, 0.5 * (zf + zr))
            body.rotation_euler = (0, -float(rec["pitch"][idx]), 0)
            for wkey, (node, w, wx) in wheels.items():
                road_z = wf if wx > 0 else wr
                node.location = (wx, 0.82 * (1 if wkey[1] == "r" else -1), R + float(road_z))
                w.rotation_euler = (math.pi / 2, 0, 0)
                node.rotation_euler = (0, -(x_front - wb / 2 + wx) / R, 0)
            info[k] = {"x_front": round(float(x_front), 3), "body_rise_cm": round(100 * 0.5 * float(zf + zr), 2),
                       "pitch_deg": round(math.degrees(float(rec["pitch"][idx])), 2), "accel_g": round(float(rec["gf"][idx]), 3)}
        cam_x = -11.0 + 0.55 * float(recs["short"]["x"][min(int(t_sim * sim.FPS), len(recs["short"]["t"]) - 1)])
        base.set_camera(cam, (cam_x, 1.7, 2.3), (cam_x + 10.0, 1.7, 0.45))
        scene.render.filepath = str(args.out / f"frame_{f:04d}.png")
        t_start = time.time()
        bpy.ops.render.render(write_still=True)
        info["render_seconds"] = round(time.time() - t_start, 1)
        result.append(info)
        print("BUMP_FRAME " + json.dumps(info), flush=True)
    (args.out / "frames.json").write_text(json.dumps(result, indent=1))


main()
