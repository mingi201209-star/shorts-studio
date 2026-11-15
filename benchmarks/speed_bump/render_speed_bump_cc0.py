"""EP.03 speed bumps: split side-camera preview with the pinned CC0 sedan (the same rigged car used in the jersey-barrier episode).

One real car model is posed twice per frame (once from the hump simulation, once from the short-bump simulation): literally the same car, same speed,
same camera distance. Travel is along +Y, lanes along X (the car's own frame). Poses come from speed_bump_motion with the car's MEASURED wheelbase.
The model is not calibrated ("physically_calibrated": False); slow motion (SLOW) is a property of the shot.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402
from benchmarks.speed_bump import speed_bump_motion as sim  # noqa: E402

material, cube = base.material, base.cube
SLOW = 0.25


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--frames", type=str, required=True)
    p.add_argument("--width", type=int, default=360)
    p.add_argument("--height", type=int, default=640)
    p.add_argument("--samples", type=int, default=7)
    p.add_argument("--t0", type=float, default=0.0)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.height // 2
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.0
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    key = bpy.context.object
    key.data.energy, key.data.angle = 3.4, 0.03
    key.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()

    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, 10, -0.05), (12.0, 80, 0.1), road)
    cube("Verge L", (-7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge", (0.22, 0.2, 0.14), rough=1.0))
    cube("Verge R", (7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge2", (0.22, 0.2, 0.14), rough=1.0))
    yellow = material("Bump paint", (0.9, 0.62, 0.05), rough=0.5)
    bumps = {}
    for k, b in sim.BUMPS.items():
        n = 40
        pts = [(i / n * b["length"], b["height"] * math.sin(math.pi * i / n)) for i in range(n + 1)] + [(b["length"], 0.0)]
        ob = base.extruded_profile(f"Bump {k}", pts, -1.4, 1.4, yellow)
        ob.rotation_euler = (0, 0, math.pi / 2)   # profile x -> world +Y, lane width along X
        bumps[k] = ob

    car_params = dict(sim.CAR, wheelbase=geom["wheelbase"])
    recs = {k: sim.simulate(b, car=car_params) for k, b in sim.BUMPS.items()}
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam_data.lens, cam_data.sensor_fit, cam_data.sensor_width = 42, "HORIZONTAL", 36

    LANE_X = 0.0
    result = []
    for f in [int(s) for s in args.frames.split(",")]:
        t_sim = args.t0 + f / 30.0 * SLOW
        info = {"frame": f, "sim_time": round(t_sim, 4)}
        t_start = time.time()
        for panel in ("hump", "short"):
            for k, ob in bumps.items():
                base.set_visible(ob, k == panel)
            rec = recs[panel]
            idx = min(int(t_sim * sim.FPS), len(rec["t"]) - 1)
            y_front = float(rec["x"][idx])
            root.location = (LANE_X, y_front - geom["front_axle"], 0.0)
            body.location = (0, 0, float(0.5 * (rec["zf"][idx] + rec["zr"][idx])))
            body.rotation_euler = (float(rec["pitch"][idx]), 0, 0)
            for wkey, w in wheels.items():
                front = wkey.startswith("front")
                road_z = float(rec["wf"][idx] if front else rec["wr"][idx])
                w["node"].location = (w["base"].x, w["base"].y, w["base"].z + road_z)
                w["node"].rotation_euler = (-(y_front - geom["front_axle"] + w["base"].y) / geom["tyre_radius"], 0, 0)
            cy = y_front - 1.0
            base.set_camera(cam, (LANE_X - 6.2, cy, 0.95), (LANE_X, cy, 0.62))
            scene.render.filepath = str(args.out / f"frame_{f:04d}_{panel}.png")
            bpy.ops.render.render(write_still=True)
            info[panel] = {"y_front": round(y_front, 3), "body_rise_cm": round(100 * float(0.5 * (rec["zf"][idx] + rec["zr"][idx])), 2),
                           "pitch_deg": round(math.degrees(float(rec["pitch"][idx])), 2)}
        info["render_seconds"] = round(time.time() - t_start, 1)
        result.append(info)
        print("BUMP_FRAME " + json.dumps(info), flush=True)
    (args.out / "frames.json").write_text(json.dumps(result, indent=1))


main()
