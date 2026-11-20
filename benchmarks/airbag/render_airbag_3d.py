"""EP.08 airbag: 100 % 3D renderer (Blender, Cycles CPU). The EP.04/EP.05 crash (same sedan, wall, crumple, cabin set, belted driver,
modern belt) with the driver airbag added: hub cover with tear seam, folded bag, inflator and igniter, the deploying and venting cushion,
and the crash sensor. Two cars in the same crash: "on" (airbag) and "off" (none). The head follows airbag_motion (it swings on the neck
after the belt holds the chest); colour = head load (green -> yellow -> red). Pieces come from render_belt_3d (EP.05), untouched.
No scene text."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.airbag import airbag_motion as am  # noqa: E402
from benchmarks.airbag import airbag_parts as parts  # noqa: E402
from benchmarks.airbag import human  # noqa: E402
from benchmarks.belt_limiter import belt_motion as bm  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.crumple_zone import crumple_motion as cm  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

material, cube = base.material, base.cube
FRAME, HALF = (1080, 1920), (1080, 960)
NECK_L = 0.22


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--shots", default="all")
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--film", action="store_true")
    p.add_argument("--frames", default="0-0")
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
    cube("Road", (0, -10, -0.05), (14.0, 60, 0.1), road)
    cube("Barrier", (0, 0.5, 1.0), (9.0, 1.0, 2.0), material("Barrier", (0.12, 0.12, 0.115), rough=0.9))
    cube("Barrier stripe", (0, -0.002, 0.5), (9.0, 0.004, 0.18), material("Stripe", (0.9, 0.62, 0.05), rough=0.5))
    nose = geom["nose"]
    car_len = geom["nose"] + geom["tail"]
    wheel_nodes = {w["node"] for w in wheels.values()}
    body_parts = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))]
    bpy.context.view_layer.update()
    deformables = [rb.Deformable(o, nose) for o in body_parts]
    ghost = rb.Ghost(list(body_parts))
    dummy = human.Human(root)
    interior = rb.build_interior(root)
    belt = rb.Belt(root)
    module = parts.AirbagModule(root, rb.Dummy.WHEEL)
    sensor = parts.CrashSensor(root)
    wheel_objs = [o for w in wheels.values() for o in [w["node"], *w["node"].children_recursive]]
    all_body = list(body_parts) + wheel_objs
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    rec = bm._crash()
    wheel_r = geom["tyre_radius"]
    tc = am.contact_time_s()

    def render(sh, variant, path, size):
        t = tc + sh["dt"]
        scene.render.resolution_x, scene.render.resolution_y = round(size[0] * args.res_scale), round(size[1] * args.res_scale)
        ps = cm.sample(rec, t)
        d, s = ps["d"], ps["s"]
        root.location = (0.0, -cm.LEAD_SIM + d - nose, 0.0)
        for dm in deformables:
            dm.apply(s, nose)
        for key, wh in wheels.items():
            y_new = cm.wheel_y(float(wh["base"].y), s, nose, wheel_r) if key.startswith("front") else float(wh["base"].y)
            wh["node"].location = (wh["base"].x, y_new, wh["base"].z)
            wh["node"].rotation_euler = (-d / wheel_r, 0, 0)
        st = dummy.pose("modern", t)
        a = am.at(variant, t)
        bend = math.atan2(max(0.0, a["neck_bend_m"]), NECK_L)
        dummy.neck.rotation_euler = (-min(1.25, 1.35 * bend), 0.0, 0.0)
        dummy.colour(a["injury"])
        bpy.context.view_layer.update()
        belt.update(dummy.pivot, st["payout_m"], st["chest_g"])
        fired = variant == "on" and t >= tc + am.FIRE_DELAY_S
        module.update(a["fill"], a["bag"], a["bag_press_m"], fired)
        car_g = float(np.interp(t, rec["t"], rec["g"]))
        sensor.update(car_g, t >= tc + am.FIRE_DELAY_S and variant == "on")
        inside = bool(sh.get("interior"))
        xf = 1.0 if sh.get("xray") else 0.0
        ghost.set_factor(xf, root.location.y + nose, car_len, root.location.y + nose - car_len - 0.8 - xf * (car_len + 0.8))
        ghost.set_tint((1.0, 1.0, 1.0))
        for ob in all_body:
            ob.hide_render = inside
        for ob in interior:
            ob.hide_render = not inside
        module.set_visible(variant == "on")
        if variant == "on":
            module.update(a["fill"], a["bag"], a["bag_press_m"], fired)
            module.cutaway(bool(sh.get("cutaway")))
        sensor.set_visible(bool(sh.get("sensor")))
        c = sh["cam"]
        off = Vector(root.location)
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.01
        base.set_camera(cam, Vector(c["loc"]) + off, Vector(c["target"]) + off)
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": variant, "dt": round(sh["dt"], 6), "head_m": round(a["head_m"], 4), "head_g": round(a["head_g"], 2), "peak_head_g": round(a["peak_head_g"], 1),
                "fill": round(a["fill"], 3), "bag": round(a["bag"], 3), "torso_m": round(a["torso_m"], 4), "stroke_m": round(s, 4), "fired": fired,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    out = []
    if args.film:
        from benchmarks.airbag import airbag_timeline as tl
        segs = tl.segments()
        a0, b0 = (int(x) for x in args.frames.split("-"))
        for f in range(a0, b0 + 1):
            t0 = time.time()
            sh = tl.frame_state(f, segs)
            if sh.get("split"):
                prts = [render(sh, "on", args.out / f"frame_{f:05d}_top.png", HALF), render(sh, "off", args.out / f"frame_{f:05d}_bot.png", HALF)]
            else:
                prts = [render(sh, sh["variant"], args.out / f"frame_{f:05d}.png", FRAME)]
            info = {"frame": f, "segment": sh["segment"], "split": bool(sh.get("split")), "parts": prts, "render_seconds": round(time.time() - t0, 1)}
            out.append(info)
            print("AIRBAG_FRAME " + json.dumps(info), flush=True)
        (args.out / f"airbag-frames-{a0:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "frames": out}, indent=1))
        return
    from benchmarks.airbag import airbag_shots as shots
    names = list(shots.SHOTS) if args.shots == "all" else args.shots.split(",")
    for name in names:
        t0 = time.time()
        sh = shots.SHOTS[name]
        info = {"shot": name, **render(sh, sh["variant"], args.out / f"{name}.png", sh.get("frame", FRAME)), "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("AIRBAG_SHOT " + json.dumps(info), flush=True)


if __name__ == "__main__":
    main()
