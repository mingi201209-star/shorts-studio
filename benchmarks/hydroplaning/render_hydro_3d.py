"""EP.09 hydroplaning: 100 % 3D renderer (Blender, Cycles CPU). Same CC0 sedan on a wet two-lane road with a bend and a puddle; spray from
tyres in water; the stylised driver (EP.08) whose steering wheel turns with the model's steering; a lab set with tread sections, water,
the wedge cutaway and a coin. Everything that moves comes from hydro_motion. No scene text (labels and numbers are added in assembly)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from benchmarks.airbag import human  # noqa: E402
from benchmarks.belt_limiter import render_belt_3d as rb  # noqa: E402
from benchmarks.hydroplaning import hydro_motion as hm  # noqa: E402
from benchmarks.hydroplaning import hydro_scene as hs  # noqa: E402
from benchmarks.hydroplaning import hydro_timeline as tl  # noqa: E402
from benchmarks.road_safety import cinematic  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

FRAME, HALF = (1080, 1920), (1080, 960)


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--film", action="store_true", help="accepted for the shared workflow; this renderer always renders film frames")
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
    sun_to = cinematic.sun_vector((-0.5, -0.8), 28.0)
    cinematic.apply_sky(scene, sun_to, strength=0.22, dust=2.0)
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 2.6, 0.08
    sun.rotation_euler = Vector(cinematic.light_direction(sun_to)).to_track_quat("-Z", "Y").to_euler()
    world = hs.build_world()
    spray = hs.Spray()
    lab = hs.Lab()
    interior = rb.build_interior(root)
    driver = human.Human(root)
    wheel_ob = bpy.data.objects["Steering wheel"]
    wheel_ob.rotation_mode = "ZYX"
    wheel_nodes = {w["node"] for w in wheels.values()}
    car_body = [o for o in root.children_recursive if o.type == "MESH" and not any(p in wheel_nodes for p in rb._ancestors(o))
                and o not in interior and not o.name.startswith(("Driver", "Steering"))]
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam

    def render(sh, tread, path, size):
        st = hm.at(tread, sh["t"])
        scene.render.resolution_x, scene.render.resolution_y = round(size[0] * args.res_scale), round(size[1] * args.res_scale)
        root.location = (st["x"], st["y"], 0.0)
        root.rotation_euler = (0, 0, st["heading"])
        body.rotation_euler = (0, -0.02 * max(-1.5, min(1.5, st["yaw_rate"])), 0)
        for key, wh in wheels.items():
            wh["node"].rotation_mode = "ZXY"
            wh["node"].rotation_euler = (-st["wheel_angle"], 0, st["steer"] if key.startswith("front") else 0.0)
        wheel_ob.rotation_euler = (math.radians(-58), 0, -st["steer"] * 15.0)
        lab_mode = sh.get("lab")
        in_lab = lab_mode is not None
        inside = bool(sh.get("interior"))
        if not in_lab:
            spray.update(tread, sh["t"])
        for ob in world + [spray.ob] + list(root.children_recursive):
            ob.hide_render = in_lab
        if not in_lab:
            for ob in car_body:
                ob.hide_render = inside
            for ob in interior:
                ob.hide_render = not inside
        lab.set_visible(in_lab)
        float_frac = sh.get("float", 0.0)
        if in_lab:
            lab.update(sh["film_t"], float_frac, lab_mode if lab_mode in ("flow", "pool") else None)
            coin = sh.get("coin")
            for ob in lab.coin.children:
                ob.hide_render = coin is None
            if coin:
                lab.place_coin(coin[0], coin[1])
        sun.hide_render = False
        c = sh["cam"]
        if c["rel"] == "follow":
            o = Vector((st["x"], st["y"], 0.0))
            loc, tgt = o + Vector(c["loc"]), o + Vector(c["target"])
        elif c["rel"] == "car":
            o, rot = Vector((st["x"], st["y"], 0.0)), Matrix.Rotation(st["heading"], 3, "Z")
            loc, tgt = o + rot @ Vector(c["loc"]), o + rot @ Vector(c["target"])
        elif c["rel"] == "lab":
            loc, tgt = hs.LAB + Vector(c["loc"]), hs.LAB + Vector(c["target"])
        else:
            loc, tgt = Vector(c["loc"]), Vector(c["target"])
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start = "HORIZONTAL", 36.0, c["lens"], 0.01
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"variant": tread, "t": round(sh["t"], 5), "x": round(st["x"], 3), "y": round(st["y"], 3), "speed_kmh": round(st["speed"] * 3.6, 1),
                "grip_front": round(st["grip_front"], 3), "lane_offset": round(st["lane_offset"], 3), "steer_deg": round(math.degrees(st["steer"]), 2),
                "heading_deg": round(math.degrees(st["heading"]), 2), "float": round(float_frac, 3), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    segs = tl.segments()
    a0, b0 = (int(x) for x in args.frames.split("-"))
    out = []
    for f in range(a0, b0 + 1):
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        if sh.get("split"):
            prts = [render(sh, "new", args.out / f"frame_{f:05d}_top.png", HALF), render(sh, "worn", args.out / f"frame_{f:05d}_bot.png", HALF)]
        else:
            prts = [render(sh, sh["variant"], args.out / f"frame_{f:05d}.png", FRAME)]
        info = {"frame": f, "segment": sh["segment"], "split": bool(sh.get("split")), "parts": prts, "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("HYDRO_FRAME " + json.dumps(info), flush=True)
    (args.out / f"hydro-frames-{a0:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "frames": out}, indent=1))


if __name__ == "__main__":
    main()
