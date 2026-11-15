"""EP.03 speed bumps: 100 % 3D renderer. The picture contains ONLY the 3D scene: the CC0 sedan, the two bumps, the road and the sky. No graphs, no text, no
overlay plates; the explanation is the 3D model plus the narration (and the burned-in captions of the narration).

One real car model is posed twice per frame (long-hump simulation, short-bump simulation): literally the same car at the same speed. Five camera set-ups
(rear 3/4, side, front 3/4, front-wheel close-up, top) give real cuts. Layout "stack": hump above, short bump below (1080x700 each); layout "side": hump left,
short bump right (540x1400 each). Poses come from speed_bump_motion with the car's MEASURED wheelbase; not calibrated ("physically_calibrated": False).
Slow motion is a property of the shot.
"""
from __future__ import annotations

import argparse
import hashlib
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
from benchmarks.speed_bump.speed_bump_timeline import Timeline  # noqa: E402

material, cube = base.material, base.cube
SIZES = {"stack": (1080, 700), "side": (540, 1400)}


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--end", type=int, default=0)
    p.add_argument("--frames", type=str, default="")
    p.add_argument("--preview", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def pose_car(root, body, wheels, geom, rec, idx):
    y_front = float(rec["x"][idx])
    root.location = (0.0, y_front - geom["front_axle"], 0.0)
    body.location = (0, 0, float(0.5 * (rec["zf"][idx] + rec["zr"][idx])))
    body.rotation_euler = (float(rec["pitch"][idx]), 0, 0)
    for wkey, w in wheels.items():
        road_z = float(rec["wf"][idx] if wkey.startswith("front") else rec["wr"][idx])
        w["node"].location = (w["base"].x, w["base"].y, w["base"].z + road_z)
        w["node"].rotation_euler = (-(y_front - geom["front_axle"] + w["base"].y) / geom["tyre_radius"], 0, 0)
    return y_front


def place_camera(cam, kind, y):
    """y: the front axle's position along the road. Travel is +Y."""
    d = cam.data
    d.sensor_fit, d.sensor_width = "HORIZONTAL", 36
    if kind == "side":                      # low side view, travel left to right
        d.lens = 42
        base.set_camera(cam, (6.2, y - 1.0, 0.95), (0.0, y - 1.0, 0.62))
    elif kind == "rear3q":                  # behind and to the left, looking ahead along the bump
        d.lens = 40
        base.set_camera(cam, (-3.0, y - 4.9, 1.5), (0.35, y + 0.1, 0.5))
    elif kind == "front3q":                 # ahead of the car, looking back at it
        d.lens = 38
        base.set_camera(cam, (2.0, y + 3.7, 0.95), (0.0, y - 0.5, 0.5))
    elif kind == "wheel":                   # close on the front wheel
        d.lens = 45
        base.set_camera(cam, (3.6, y - 0.1, 0.5), (0.5, y + 0.35, 0.3))
    elif kind == "top":                     # straight down, travel up the screen
        d.lens = 45
        cam.location = (0.0, y - 0.6, 8.5)
        cam.rotation_euler = (0.0, 0.0, 0.0)
    else:
        raise ValueError(kind)


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    root, body, wheels, geom = base.load_source_car(args.source)
    scene = bpy.context.scene
    scene.name = "panels"
    k = 3 if args.preview else 1
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 7 if args.preview else 24
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = -1.3
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    sun_to = cinematic.sun_vector((-0.5, -0.8), 36.0)
    cinematic.apply_sky(scene, sun_to, strength=0.25, dust=0.5)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 3.4, 0.03
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    road = material("Asphalt", (0.07, 0.07, 0.075), rough=0.85)
    base.asphalt_grain(road)
    cube("Road", (0, 10, -0.05), (12.0, 80, 0.1), road)
    cube("Verge L", (-7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge", (0.22, 0.2, 0.14), rough=1.0))
    cube("Verge R", (7.2, 10, -0.06), (2.4, 80, 0.1), material("Verge2", (0.22, 0.2, 0.14), rough=1.0))
    cube("Centre line", (-3.0, 10, 0.002), (0.12, 80, 0.004), material("Line", (0.8, 0.8, 0.78), rough=0.6))
    yellow = material("Bump paint", (0.9, 0.62, 0.05), rough=0.5)
    bumps = {}
    for kb, b in sim.BUMPS.items():
        n = 40
        pts = [(i / n * b["length"], b["height"] * math.sin(math.pi * i / n)) for i in range(n + 1)] + [(b["length"], 0.0)]
        ob = base.extruded_profile(f"Bump {kb}", pts, -1.4, 1.4, yellow)
        ob.rotation_euler = (0, 0, math.pi / 2)
        bumps[kb] = ob
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    tl = Timeline(geom["wheelbase"])
    frames = [int(x) for x in args.frames.split(",")] if args.frames else list(range(args.start, args.end + 1))
    result, checks = [], []
    for f in frames:
        t_start = time.time()
        seg, t_sim = sim.frame_to_pass(f)
        kind, layout = sim.shot_at(f)
        w, h = SIZES[layout]
        scene.render.resolution_x, scene.render.resolution_y = w // k, h // k
        info = {"frame": f, "segment": seg["id"], "camera": kind, "layout": layout, "sim_time": round(t_sim, 4)}
        for panel in ("hump", "short"):
            for kb, ob in bumps.items():
                base.set_visible(ob, kb == panel)
            rec = tl.recs[(seg["id"], panel)]
            idx = min(int(t_sim * sim.FPS), len(rec["t"]) - 1)
            y_front = pose_car(root, body, wheels, geom, rec, idx)
            place_camera(cam, kind, y_front)
            path = args.out / f"frame_{f:04d}_{panel}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            checks.append({"frame": f, "panel": panel, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            info[panel] = {"y_front": round(y_front, 3), "body_rise_cm": round(100 * float(0.5 * (rec["zf"][idx] + rec["zr"][idx])), 2),
                           "pitch_deg": round(math.degrees(float(rec["pitch"][idx])), 2), "accel_g": round(float(rec["gf"][idx]), 3)}
        info["render_seconds"] = round(time.time() - t_start, 1)
        result.append(info)
        print("BUMP_FRAME " + json.dumps(info), flush=True)
    proof = {"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "geometry": geom, "preview": bool(args.preview),
             "checksums": checks, "telemetry": result, "physically_calibrated": False, "all_3d": True, "overlays": "none"}
    (args.out / "bump-proof.json").write_text(json.dumps(proof, indent=1))


main()
