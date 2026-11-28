"""EP.37 elevator safety gear: 100 % 3D renderer (Blender, Cycles CPU). Started with EP.36 for its opening only (EP.36's teaser);
the rest of the film is added later without changing the opening's code path. A concrete hoistway cut away on one side, lit like
a set: a cool key through the cutaway, the car's own ceiling light behind its glass, warm light at the landing doors' seams, and
the sparks. Everything that moves comes from car_motion. No text anywhere."""
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
from benchmarks import hook_gate  # noqa: E402
from benchmarks.elevator_safety import car_motion as m  # noqa: E402
from benchmarks.elevator_safety import car_parts as cp  # noqa: E402
from benchmarks.elevator_safety import car_timeline as tl  # noqa: E402
from benchmarks.identity import dummy  # noqa: E402
from benchmarks.road_safety import render_jersey_barrier as base  # noqa: E402

FRAME = (1080, 1920)


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--res-scale", type=float, default=0.5)
    p.add_argument("--samples", type=int, default=16)
    p.add_argument("--frames", default="0-0")
    p.add_argument("--list", default="")
    p.add_argument("--source", type=Path, default=None)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


def area(name, loc, target, size, energy, colour):
    bpy.ops.object.light_add(type="AREA", location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.data.size = size
    ob.data.energy = energy
    ob.data.color = colour
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


def main():
    args = arguments()
    args.out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 16
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.0
    scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.02, 0.025, 0.035, 1)
    bg.inputs["Strength"].default_value = 1.0

    mt = cp.mats()
    shaft = cp.hoistway(mt)
    cw_root = cp.counterweight(mt, 5.5)
    car = cp.car(mt)
    gov = cp.governor_rope(mt)
    spark_obs = cp.sparks(mt)
    key = area("Key", (5.5, -3.0, 3.5), (0.5, 0.0, 0.5), 4.0, 2200.0, (0.82, 0.9, 1.0))
    fill = area("Fill", (3.5, 2.5, -2.5), (0.0, 0.0, 0.5), 3.0, 500.0, (1.0, 0.75, 0.5))
    top = area("Top", (0.0, 0.0, 9.0), (0.0, 0.0, 0.0), 2.0, 900.0, (1.0, 0.95, 0.9))
    bpy.ops.object.light_add(type="POINT", location=(0.0, 0.0, cp.CAB_H - 0.25))
    cab_light = bpy.context.object
    cab_light.parent = car["root"]
    cab_light.data.energy = 120.0
    cab_light.data.color = (1.0, 0.9, 0.75)
    cab_light.data.shadow_soft_size = 0.4
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    wedge_rest = [w.location.copy() for w in car["wedges"]]

    def render(sh, path):
        scene.render.resolution_x, scene.render.resolution_y = round(FRAME[0] * args.res_scale), round(FRAME[1] * args.res_scale)
        t = sh["t"]
        st = m.state(t)
        cz = st["car_z"]
        car["root"].location = (0.0, 0.0, cz)
        for w, rest in zip(car["wedges"], wedge_rest):
            w.location = (rest.x, rest.y, rest.z + 0.07 * st["wedge"])
        slack = min(1.0, max(0.0, t / 0.35))
        for ob in car["stubs"]:
            cp.set_stub(ob, t, slack)
        lean = 0.12 * st["decel_g"] / m.DECEL_G if st["gripping"] else 0.0
        dummy.pose(car["bumper"], lean=-lean, seated=False)
        for k, p in enumerate(car["people"]):
            torso = next(o for o in p.children if o.name.startswith("Crew torso"))
            torso.rotation_euler = (lean * (0.8 + 0.3 * k), 0.0, 0.0)
        n = 0
        on = st["gripping"] or (st["phase"] == "grip" and t < m.stop_time() + 0.08)
        for ob in spark_obs:
            if not on:
                ob.location = (0, 0, -50)
                continue
            age = ((ob["phase"] + t * 3.1) % 1.0) * 0.3
            sx = ob["side"]
            p0 = Vector((sx * (cp.SHAFT_X - 0.02 - 0.0775), 0.0, cz - 0.55))
            v = Vector(ob["v"])
            v.x *= -sx
            ob.location = p0 + v * age + Vector((0, 0, -4.9 * age * age))
            n += 1
        c = sh["cam"]
        loc, tgt = Vector(c["loc"]), Vector(c["target"])
        if c["rel"] == "car":
            loc.z += cz
            tgt.z += cz
        dd = cam.data
        dd.sensor_fit, dd.sensor_width, dd.lens, dd.clip_start, dd.clip_end = "HORIZONTAL", 36.0, c["lens"], 0.03, 400.0
        dd.dof.use_dof = True
        dd.dof.focus_distance = (tgt - loc).length
        dd.dof.aperture_fstop = c.get("fstop", 8.0)
        base.set_camera(cam, loc, tgt)
        bpy.context.view_layer.update()
        info = {"variant": sh["variant"], "t": round(t, 6), "car_z": round(cz, 4), "speed": round(st["speed"], 4), "decel_g": round(st["decel_g"], 4),
                "phase": st["phase"], "wedge": round(st["wedge"], 4), "gripping": bool(st["gripping"]), "sparks": n,
                "subject_box": hook_gate.project_box(scene, cam, Matrix.Identity(4), (-cp.SHAFT_X, -0.7, cz - 0.7), (cp.SHAFT_X, 0.7, cz + cp.CAB_H + 0.9))}
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return info

    segs = tl.segments()
    a0, b0 = (int(v) for v in args.frames.split("-"))
    frames = [int(v) for v in args.list.split(",")] if args.list else list(range(a0, b0 + 1))
    out = []
    for f in frames:
        t0 = time.time()
        sh = tl.frame_state(f, segs)
        part = render(sh, args.out / f"frame_{f:05d}.png")
        info = {"frame": f, "segment": sh["segment"], "split": False, "parts": [part], "render_seconds": round(time.time() - t0, 1)}
        out.append(info)
        print("CAR_FRAME " + json.dumps(info), flush=True)
    (args.out / f"car-frames-{frames[0]:05d}.json").write_text(json.dumps({"renderer_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                                                          "frames": out}, indent=1))


if __name__ == "__main__":
    main()
